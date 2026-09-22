"""S3 概念归并：试点字段映射 + 字面归并，产出稳定 concept_code 与 family_key。

不使用 Embedding 当真理。单位/量纲仅在 PILOT_CONFIRMATIONS 书面确认后写入。
ID_KEY 不挂业务概念。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

from tag_semantic.bootstrap.rule_init import write_jsonl

# 试点 31 字段的稳定编码（人工确认后固化，不随中文名改写）
PILOT_FIELD_CONCEPTS: dict[str, dict[str, Any]] = {
    "GENDER": {"code": "GENDER", "name": "性别", "definition": "客户性别"},
    "ID_TYPE": {"code": "ID_TYPE", "name": "证件类型", "definition": "客户证件类型"},
    "OUTSIDE_ASSET_WAN_KYC": {
        "code": "OUTSIDE_ASSET",
        "name": "行外资产",
        "definition": "行外资产分档，来源不同须拆族",
    },
    "OUTSIDE_ASSET_OPS_KYC": {
        "code": "OUTSIDE_ASSET",
        "name": "行外资产",
        "definition": "行外资产分档，来源不同须拆族",
    },
    "OUTSIDE_ASSET_PB_KYC": {
        "code": "OUTSIDE_ASSET",
        "name": "行外资产",
        "definition": "行外资产分档，来源不同须拆族",
    },
    "DO_NOT_DISTURB_CUST_WECOM_TAG_FLAG": {
        "code": "DND_WECOM",
        "name": "勿扰客户",
        "definition": "企微勿扰标签",
    },
    "CHILD_COUNT_PB_KYC": {"code": "CHILD_COUNT_PB", "name": "子女数量", "definition": "私银KYC子女数量"},
    "HOUSEHOLD_ANNUAL_INCOME_PB_KYC": {
        "code": "HH_INCOME_PB",
        "name": "家庭年收入",
        "definition": "私银KYC家庭年收入分档",
    },
    "CUR_PB_KYC_COMPLETENESS": {
        "code": "PB_KYC_COMPLETENESS",
        "name": "私银KYC完整度",
        "definition": "私银KYC资料完整度",
    },
    "CUR_APP_DEVICE_TYPE": {"code": "APP_DEVICE", "name": "APP设备类型", "definition": "当前APP设备类型"},
    "CUR_MOBILE_MODEL": {"code": "MOBILE_MODEL", "name": "手机型号", "definition": "当前手机型号，自由文本"},
    "HIGHEST_EDUCATION": {"code": "EDUCATION", "name": "最高学历", "definition": "最高学历有序枚举，仅 rank_no"},
    "HIST_HOLDING_WMP_FLAG": {"code": "WMP_HOLDING", "name": "理财持有", "definition": "是否持有理财产品"},
    "CUR_HOLDING_WMP_FLAG": {"code": "WMP_HOLDING", "name": "理财持有", "definition": "是否持有理财产品"},
    "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG": {
        "code": "FUND_INFLOW_INTERBANK",
        "name": "异名跨行转入",
        "definition": "他行非同名账户向本行账户转入",
    },
    "LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG": {
        "code": "FUND_INFLOW_INTERBANK",
        "name": "异名跨行转入",
        "definition": "他行非同名账户向本行账户转入",
    },
    "LAST_7_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_COUNT": {
        "code": "FUND_INFLOW_INTERBANK",
        "name": "异名跨行转入",
        "definition": "他行非同名账户向本行账户转入",
    },
    "LAST_12_MONTHS_MAX_AUM": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "T3_MONTH_END_AUM": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "CUR_POINT_AUM": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "CUR_AUM_MONTH_AVG_DAILY_BALANCE": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "HIST_MAX_POINT_AUM": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "CUR_POINT_AUM_OUR_BANK": {"code": "AUM", "name": "AUM", "definition": "资产管理规模"},
    "CUR_FIXED_INCOME_AUM_RATIO": {
        "code": "AUM_FI_RATIO",
        "name": "固收类AUM占比",
        "definition": "当前固收类AUM占比",
    },
    "HIST_MATURED_TIME_DEPOSIT_LATEST_MAT_DATE": {
        "code": "TD_MATURITY",
        "name": "定期到期日",
        "definition": "定期存款到期日期",
    },
    "NEXT_TIME_DEPOSIT_LATEST_MAT_DATE": {
        "code": "TD_MATURITY",
        "name": "定期到期日",
        "definition": "定期存款到期日期",
    },
    "CUR_CORE_CM_LEVEL1_BRANCH": {
        "code": "CM_ORG",
        "name": "核心管户机构",
        "definition": "核心管户机构，保持普通枚举，不开子树",
    },
    "CUR_CORE_CM_LEVEL2_BRANCH": {
        "code": "CM_ORG",
        "name": "核心管户机构",
        "definition": "核心管户机构，保持普通枚举，不开子树",
    },
    "CUR_CORE_CM_LEVEL3_BRANCH": {
        "code": "CM_ORG",
        "name": "核心管户机构",
        "definition": "核心管户机构，保持普通枚举，不开子树",
    },
    "CUR_WMP_RISK_ASSESSMENT_LEVEL": {
        "code": "WMP_RISK",
        "name": "理财风评等级",
        "definition": "理财风险评测等级 C1-C5，仅 rank_no",
    },
}

# 试点书面确认（方案推荐默认值，记入复核包；不是规则自动推断）
PILOT_CONFIRMATIONS: dict[str, Any] = {
    "amount_unit": "CNY",
    "amount_unit_scale": 1,
    "ratio_unit": "RATIO",
    "ratio_unit_scale": 1,
    "ratio_scale_note": "0-1",
    "institution_hierarchy": False,
    "ordinal_interval_policy": "rank_only_if_unparsed",
    "source": "PILOT_DEFAULT_20260918",
}

_STRIP_HINTS = (
    "当前",
    "历史",
    "时点",
    "最高",
    "最低",
    "标志",
    "次数",
    "余额",
    "本行",
    "月日均",
)


def family_key(
    concept_code: str,
    statistic: str,
    scope: str,
    source_system: Optional[str],
    unit: str,
    caliber_variant: str = "BASE",
) -> str:
    source_part = source_system or "NONE"
    return f"{concept_code}|{statistic or 'NONE'}|{scope or 'ALL'}|{source_part}|{unit or 'NONE'}|{caliber_variant or 'BASE'}"


def _literal_code(candidate: str) -> str:
    text = candidate or "UNNAMED"
    for hint in _STRIP_HINTS:
        text = text.replace(hint, "")
    text = re.sub(r"[（()）\s\-_]+", "", text)
    if "AUM" in (candidate or "").upper() and "占比" not in (candidate or ""):
        return "AUM"
    if not text:
        text = candidate or "UNNAMED"
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", text).strip("_") or "UNNAMED"


def resolve_concept(tag: dict[str, Any]) -> Optional[dict[str, Any]]:
    if tag.get("semantic_type") == "ID_KEY" or tag.get("business_candidate") is False:
        return None
    field = str(tag.get("field_name") or "")
    if field in PILOT_FIELD_CONCEPTS:
        return dict(PILOT_FIELD_CONCEPTS[field])
    candidate = str(tag.get("concept_candidate") or tag.get("name") or "UNNAMED")
    code = _literal_code(candidate)
    return {"code": code, "name": candidate, "definition": candidate}


def apply_unit_confirmation(tag: dict[str, Any], confirmations: dict[str, Any]) -> dict[str, Any]:
    row = dict(tag)
    caliber = dict(row.get("caliber_struct") or {})
    semantic_type = row.get("semantic_type")
    if semantic_type == "NUM_AMOUNT":
        row["unit"] = confirmations["amount_unit"]
        row["unit_scale"] = confirmations["amount_unit_scale"]
        caliber["unit"] = row["unit"]
        caliber["unit_scale"] = row["unit_scale"]
    elif semantic_type == "NUM_RATIO":
        row["unit"] = confirmations["ratio_unit"]
        row["unit_scale"] = confirmations["ratio_unit_scale"]
        caliber["unit"] = row["unit"]
        caliber["unit_scale"] = row["unit_scale"]
    row["caliber_struct"] = caliber
    return row


def cluster_tags(
    tags: Iterable[dict[str, Any]],
    confirmations: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    confirmed = confirmations or {}
    clustered: list[dict[str, Any]] = []
    for tag in tags:
        if tag.get("kind") != "tag_semantic":
            clustered.append(tag)
            continue
        row = apply_unit_confirmation(tag, confirmed) if confirmed else dict(tag)
        caliber = dict(row.get("caliber_struct") or {})
        semantic_type = str(row.get("semantic_type") or "")
        if semantic_type.startswith("ENUM") or semantic_type in {"TEXT_FREE", "DATE", "ID_KEY"}:
            if caliber.get("statistic") in {"MAX", "MIN", "SUM", "AVG_DAILY", "EOP"}:
                caliber["statistic"] = "NONE"
                row["caliber_struct"] = caliber
        override = (confirmed.get("tag_concepts") or {}).get(row.get("field_name"))
        concept = resolve_concept(row)
        if override and semantic_type != "ID_KEY":
            if not override.get("concept_code") or not override.get("concept_name"):
                raise ValueError("概念复核配置缺少编码或名称")
            concept = {"code": override["concept_code"], "name": override["concept_name"], "definition": override.get("definition")}
            row["domain_dir_id"] = override.get("domain_dir_id")
            row["caliber_variant"] = override.get("caliber_variant") or row.get("caliber_variant") or "BASE"
        if concept is None:
            row["concept_code"] = None
            row["concept_name"] = None
            row["skip_concept"] = True
            row["family_key"] = family_key(
                "OBJECT_KEY",
                (row.get("caliber_struct") or {}).get("statistic") or "NONE",
                (row.get("caliber_struct") or {}).get("scope") or "ALL",
                (row.get("caliber_struct") or {}).get("source_system"),
                row.get("unit") or "NONE",
                row.get("caliber_variant") or "BASE",
            )
            clustered.append(row)
            continue
        caliber = row.get("caliber_struct") or {}
        row["concept_code"] = concept["code"]
        row["concept_name"] = concept["name"]
        row["concept_definition"] = concept.get("definition")
        row["skip_concept"] = False
        row["family_key"] = family_key(
            concept["code"],
            caliber.get("statistic") or "NONE",
            caliber.get("scope") or "ALL",
            caliber.get("source_system"),
            row.get("unit") or "NONE",
            row.get("caliber_variant") or "BASE",
        )
        clustered.append(row)
    return clustered


def build_concept_rows(clustered: list[dict[str, Any]], library_id: int, domain_dir_id: int, tag_object: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in clustered:
        if row.get("kind") != "tag_semantic" or row.get("skip_concept"):
            continue
        code = row["concept_code"]
        if code not in grouped:
            grouped[code] = {
                "kind": "concept",
                "library_id": library_id,
                "concept_code": code,
                "concept_name": row.get("concept_name") or code,
                "domain_dir_id": row.get("domain_dir_id") or domain_dir_id,
                "tag_object": tag_object,
                "definition": row.get("concept_definition") or row.get("concept_name"),
                "parent_id": 0,
                "status": "0",
                "source": "RULE",
                "review_status": "DRAFT",
                "members": [],
            }
        grouped[code]["members"].append(
            {
                "tag_id": row.get("tag_id"),
                "field_name": row.get("field_name"),
                "name": row.get("name"),
                "family_key": row.get("family_key"),
            }
        )
    return list(grouped.values())


def apply_cluster(result_rows: list[dict[str, Any]], confirmations: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    tags = [r for r in result_rows if r.get("kind") == "tag_semantic"]
    others = [r for r in result_rows if r.get("kind") != "tag_semantic"]
    clustered_tags = cluster_tags(tags, confirmations=confirmations)
    return clustered_tags + others


def review_pack(concepts: list[dict[str, Any]], clustered: list[dict[str, Any]], confirmations: dict[str, Any]) -> str:
    business_count = sum(r.get('kind') == 'tag_semantic' and r.get('semantic_type') != 'ID_KEY' for r in clustered)
    lines = [
        "# S3 概念复核包（候选草稿）",
        "",
        f"> 本包包含 {business_count} 个业务标签草稿、{len(concepts)} 个概念候选；生成数量不是已复核或已发布覆盖率。",
        "",
        "## 提供的口径依据（未提供项仍待业务确认）",
        "",
        f"- 金额单位：`{confirmations.get('amount_unit')}`，unit_scale=`{confirmations.get('amount_unit_scale')}`；缺失时不默认元或万元",
        f"- 占比量纲：`{confirmations.get('ratio_scale_note')}`，unit=`{confirmations.get('ratio_unit')}`",
        "- 学历 / 风评：只保留 rank_no，不伪造金额区间",
        "- 机构：ENUM_NOMINAL，不开 under / 不猜联行号树",
        f"- 依据：`{confirmations.get('source')}`",
        "",
        "## 概念与族",
        "",
    ]
    families: dict[str, list[str]] = defaultdict(list)
    for row in clustered:
        if row.get("kind") != "tag_semantic" or row.get("skip_concept"):
            continue
        families[row["family_key"]].append(f"{row.get('field_name')} {row.get('name')}")
    for concept in concepts:
        lines.append(f"### `{concept['concept_code']}` {concept['concept_name']}")
        lines.append("")
        lines.append(concept.get("definition") or "")
        lines.append("")
        for member in concept.get("members") or []:
            lines.append(f"- {member.get('field_name')} | {member.get('name')} | `{member.get('family_key')}`")
        lines.append("")
    lines.append("## Family 清单")
    lines.append("")
    for key, members in sorted(families.items()):
        lines.append(f"- `{key}`")
        for item in members:
            lines.append(f"  - {item}")
    lines.append("")
    return "\n".join(lines) + "\n"


def load_result_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="S3 概念归并")
    parser.add_argument("result_jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--library-id", type=int, default=107)
    parser.add_argument("--domain-dir-id", type=int, default=0)
    parser.add_argument("--tag-object", default="客户")
    parser.add_argument("--review-md", type=Path, default=None)
    parser.add_argument("--confirmations", type=Path, help="业务复核确认配置 JSON，不默认使用试点确认")
    args = parser.parse_args(argv)
    rows = load_result_jsonl(args.result_jsonl)
    confirmations = json.loads(args.confirmations.read_text()) if args.confirmations else {}
    clustered = apply_cluster(rows, confirmations=confirmations)
    concepts = build_concept_rows(clustered, args.library_id, args.domain_dir_id, args.tag_object)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "s3_clustered.jsonl", clustered)
    write_jsonl(args.out_dir / "s3_concepts.jsonl", concepts)
    md_path = args.review_md or (args.out_dir / "s3_concept_review_pack.md")
    md_path.write_text(review_pack(concepts, clustered, confirmations), encoding="utf-8")
    print(f"concepts={len(concepts)} tags={sum(1 for r in clustered if r.get('kind')=='tag_semantic')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
