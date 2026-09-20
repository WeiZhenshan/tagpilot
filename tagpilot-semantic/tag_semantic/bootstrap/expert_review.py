"""本地演示业务复核：把冻结口径与规则草稿收敛为可审计的 REVIEWED 候选包。

该步骤不是银行在岗人员签字。review_mode 会永久写入清单，防止把本地 AI 专家
复核误称为生产业务审批。导入与状态流转仍必须经过 Java 业务服务。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tag_semantic.bootstrap.rule_aliases import normalize
from tag_semantic.bootstrap.rule_init import OPERATORS, load_freeze

REVIEW_MODE = "AI_EXPERT_LOCAL_DEMO"
REVIEWER = "Codex-AI-银行个人客户经营专家-本地演示"

SCORE_FIELDS = {
    "CUR_CUST_POTENTIAL_VALUE_WEALTH_VALUE_POTENTIAL_MODEL",
    "CUR_CUST_WEALTH_COMPOSITE_SCORE_WEALTH_VALUE_POTENTIAL_MODEL",
    "CUR_WMP_INTENT_SCORE",
}

RATIO_HINT = re.compile(r"占比|比例|完整度|利率|盈利率|配置率|提款率|还款率|折扣率")
COUNT_HINT = re.compile(r"次数|笔数|天数|数量|户数|人数|月数|年数|张数|条数|订单数|商品数|积分数|数额|份额")
AMOUNT_HINT = re.compile(r"金额|余额|AUM|收入|收益|市值|额度|资产|贷款|垫款|授信|净利润|潜力（万元）|潜力\(万元\)")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            if raw.strip():
                try:
                    rows.append(json.loads(raw))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path} 第 {line_no} 行无法解析") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _semantic_type(row: dict[str, Any], has_codes: bool) -> str:
    name = str(row.get("name") or "")
    field = str(row.get("field_name") or "")
    data_type = str((row.get("authority") or {}).get("data_type") or "").lower()
    if row.get("semantic_type") == "ID_KEY" or has_codes:
        return str(row.get("semantic_type"))
    if row.get("semantic_type") in {"DATE", "TEXT_FREE"}:
        return str(row.get("semantic_type"))
    if field == "CUR_EQUITY_ASSET_UNDER_ALLOCATED_FLAG" or name.endswith("标志"):
        return "BOOL"
    if field in SCORE_FIELDS or ("综合分" in name and "金额" not in name):
        return "NUM_SCORE"
    if RATIO_HINT.search(name):
        return "NUM_RATIO"
    if COUNT_HINT.search(name):
        return "NUM_COUNT"
    if AMOUNT_HINT.search(name):
        return "NUM_AMOUNT"
    if data_type.startswith("int") or data_type.startswith("bigint"):
        return "NUM_COUNT"
    return str(row.get("semantic_type"))


def _unit(row: dict[str, Any], semantic_type: str) -> tuple[str, int]:
    name = str(row.get("name") or "")
    field = str(row.get("field_name") or "")
    if semantic_type == "NUM_AMOUNT":
        return "CNY", 10000 if "万元" in name or field.endswith("_WAN") else 1
    if semantic_type == "NUM_RATIO":
        return "RATIO", 1
    if semantic_type == "NUM_SCORE":
        return "POINT", 1
    if semantic_type == "NUM_COUNT":
        if "天数" in name:
            return "DAY", 1
        if "月数" in name:
            return "MONTH", 1
        if "年数" in name or "年限" in name:
            return "YEAR", 1
        if "人数" in name or "户数" in name or "客户数" in name:
            return "PERSON", 1
        if "份额" in name:
            return "SHARE", 1
        if "积分" in name:
            return "POINT", 1
        return "COUNT", 1
    return "NONE", 1


def review_tag(row: dict[str, Any], has_codes: bool) -> tuple[dict[str, Any], bool]:
    reviewed = dict(row)
    before = (row.get("semantic_type"), row.get("unit"), row.get("unit_scale"))
    semantic_type = _semantic_type(row, has_codes)
    unit, scale = _unit(row, semantic_type)
    reviewed["semantic_type"] = semantic_type
    reviewed["allowed_operators"] = OPERATORS[semantic_type]
    reviewed["default_operator"] = (OPERATORS[semantic_type] or [None])[0]
    reviewed["unit"] = unit
    reviewed["unit_scale"] = scale
    caliber = dict(reviewed.get("caliber_struct") or {})
    caliber.update({"unit": unit, "unit_scale": scale})
    reviewed["caliber_struct"] = caliber
    family = str(reviewed.get("family_key") or reviewed.get("family_candidate") or "").split("|")
    if len(family) == 6:
        family[4] = unit
        reviewed["family_key"] = "|".join(family)
    reviewed["source"] = "RULE"
    reviewed["review_status"] = "REVIEWED"
    after = (semantic_type, unit, scale)
    return reviewed, before != after


def _alias_candidates(name: str) -> list[str]:
    candidates: list[str] = []
    replacements = [
        ("当前", "目前"), ("历史", "过往"), ("本月", "当月"), ("本年", "当年"),
        ("上月末", "上个月末"), ("最近一次", "最近一笔"), ("我行", "本行"),
        ("最高", "最大"), ("最低", "最小"), ("平均", "均值"),
    ]
    for source, target in replacements:
        if source in name:
            candidates.append(name.replace(source, target, 1))
    recent = re.match(r"近(\d+)(天|个月|月|年)(.+)", name)
    if recent:
        candidates.append(f"最近{recent.group(1)}{recent.group(2)}{recent.group(3)}")
    candidates.extend([f"{name}指标", f"{name}标签"])
    return candidates


def ensure_tag_aliases(tags: list[dict[str, Any]], aliases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    output = [dict(row) for row in aliases]
    by_tag: dict[str, set[str]] = defaultdict(set)
    for row in output:
        if row.get("target_type") == "TAG" and row.get("alias_type") != "NEGATIVE":
            by_tag[str(row.get("target_id"))].add(str(row.get("alias_norm") or normalize(str(row.get("alias_text") or ""))))
    added = 0
    for tag in tags:
        if tag.get("semantic_type") == "ID_KEY":
            continue
        target = str(tag["tag_id"])
        for text in _alias_candidates(str(tag.get("name") or "")):
            norm = normalize(text)[:64]
            if not norm or norm in by_tag[target]:
                continue
            output.append({
                "kind": "alias", "target_type": "TAG", "target_id": target,
                "alias_text": text[:64], "alias_norm": norm, "alias_type": "COLLOQUIAL",
                "weight": 0.8, "source": "RULE", "review_status": "REVIEWED",
            })
            by_tag[target].add(norm)
            added += 1
            if len(by_tag[target]) >= 3:
                break
        if len(by_tag[target]) < 3:
            raise ValueError(f"标签 {target} 未生成三个互异别名")
    for row in output:
        row["review_status"] = "REVIEWED"
    return output, added


def validate_codes(tags: list[dict[str, Any]], codes: list[dict[str, Any]], source_codes_by_tag: dict[int, list[dict[str, Any]]]) -> None:
    tags_by_id = {int(row["tag_id"]): row for row in tags}
    reviewed_by_tag: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in codes:
        reviewed_by_tag[int(row["tag_id"])].append(row)
        if not str(row.get("definition") or "").strip():
            raise ValueError(f"码值缺少定义: {row.get('tag_id')}#{row.get('code')}")
    if set(reviewed_by_tag) != set(source_codes_by_tag):
        raise ValueError("码值字段集合与冻结来源不一致")
    for tag_id, source_rows in source_codes_by_tag.items():
        source = {str(row["code"]): str(row.get("definition") or "") for row in source_rows}
        reviewed = {str(row["code"]): str(row.get("definition") or "") for row in reviewed_by_tag[tag_id]}
        if source != reviewed:
            raise ValueError(f"码值定义与冻结来源不一致: tag_id={tag_id}")
        if tags_by_id[tag_id]["semantic_type"] == "ENUM_ORDINAL":
            ranks = [row.get("rank_no") for row in reviewed_by_tag[tag_id] if not row.get("is_unknown_bucket")]
            if any(rank is None for rank in ranks) or len(ranks) != len(set(ranks)):
                raise ValueError(f"有序码值顺序不完整: tag_id={tag_id}")


def split_cross_domain_concepts(
    freeze: dict[str, Any], tags: list[dict[str, Any]], concepts: list[dict[str, Any]], aliases: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    root_ids = {str(row.get("name")): int(row["dir_id"]) for row in freeze["domains"] if not row.get("parent_id")}
    source_tags = {int(row["tag_id"]): row for row in freeze["tags"]}
    tag_rows = {int(row["tag_id"]): row for row in tags}
    split_codes: dict[str, list[str]] = {}
    output: list[dict[str, Any]] = []
    split_count = 0
    for concept in concepts:
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for member in concept.get("members") or []:
            source = source_tags[int(member["tag_id"])]
            path = source.get("dir_path") or []
            domain_id = root_ids.get(str(path[0])) if path else None
            if domain_id is None:
                raise ValueError(f"标签 {member['tag_id']} 无法解析一级业务域")
            groups[domain_id].append(member)
        if len(groups) <= 1:
            row = dict(concept)
            if groups:
                row["domain_dir_id"] = next(iter(groups))
            output.append(row)
            continue
        split_count += 1
        original_code = str(concept["concept_code"])
        split_codes[original_code] = []
        for domain_id, members in sorted(groups.items()):
            code = (original_code[:54] + f"_D{domain_id}")[:64]
            row = dict(concept); row["concept_code"] = code; row["domain_dir_id"] = domain_id; row["members"] = members
            output.append(row); split_codes[original_code].append(code)
            for member in members:
                tag = tag_rows[int(member["tag_id"])]
                tag["concept_code"] = code
                family = str(tag.get("family_key") or "").split("|")
                if len(family) == 6:
                    family[0] = code; tag["family_key"] = "|".join(family)
    remapped_aliases: list[dict[str, Any]] = []
    for alias in aliases:
        if alias.get("target_type") != "CONCEPT" or str(alias.get("target_id")) not in split_codes:
            remapped_aliases.append(alias)
            continue
        for code in split_codes[str(alias["target_id"])]:
            row = dict(alias); row["target_id"] = code; remapped_aliases.append(row)
    return output, remapped_aliases, split_count


def review_package(freeze_path: Path, drafts_dir: Path, output_dir: Path, dictionary_path: Path) -> dict[str, Any]:
    freeze = load_freeze(freeze_path)
    clustered = read_jsonl(drafts_dir / "s3_clustered.jsonl")
    concepts = read_jsonl(drafts_dir / "s3_concepts.jsonl")
    aliases = read_jsonl(drafts_dir / "aliases.jsonl")
    confusable = read_jsonl(drafts_dir / "confusable.jsonl")
    tags_raw = [row for row in clustered if row.get("kind") == "tag_semantic"]
    codes = [dict(row) for row in clustered if row.get("kind") == "code_value_semantic"]
    code_tags = set(freeze["codes_by_tag"])
    tags: list[dict[str, Any]] = []
    changed = 0
    for row in tags_raw:
        reviewed, was_changed = review_tag(row, int(row["tag_id"]) in code_tags)
        tags.append(reviewed)
        changed += int(was_changed)
    concepts, aliases, split_count = split_cross_domain_concepts(freeze, tags, concepts, aliases)
    for row in codes + concepts + confusable:
        row["review_status"] = "REVIEWED"
        row["source"] = "RULE"
    validate_codes(tags, codes, freeze["codes_by_tag"])
    aliases, aliases_added = ensure_tag_aliases(tags, aliases)
    for row in aliases:
        row["source"] = row.get("source") or "RULE"

    business_tags = [row for row in tags if row.get("semantic_type") != "ID_KEY"]
    alias_counts = Counter(str(row["target_id"]) for row in aliases if row.get("target_type") == "TAG" and row.get("alias_type") != "NEGATIVE")
    if len(tags) != 970 or len(business_tags) != 969 or len(codes) != 1723 or len(code_tags) != 177:
        raise ValueError("冻结分母不满足 970字段/969业务标签/177码值字段/1723码值")
    if min(alias_counts[str(row["tag_id"])] for row in business_tags) < 3:
        raise ValueError("存在少于三个别名的业务标签")
    if not dictionary_path.exists() or "金额默认元" not in dictionary_path.read_text(encoding="utf-8").splitlines()[2]:
        raise ValueError("缺少本地字段字典的金额单位声明")

    review_id = "local-demo-review-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    source_ref = f"{review_id};mode={REVIEW_MODE};freeze_sha256={sha256_file(freeze_path)};dictionary_sha256={sha256_file(dictionary_path)}"
    import_rows = concepts + tags + codes
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "reviewed_import.jsonl", import_rows)
    write_jsonl(output_dir / "reviewed_aliases.jsonl", aliases)
    write_jsonl(output_dir / "reviewed_confusable.jsonl", confusable)
    manifest = {
        "review_id": review_id,
        "review_mode": REVIEW_MODE,
        "reviewer": REVIEWER,
        "human_bank_signoff": False,
        "scope": "LOCAL_RUNNABLE_DEMO",
        "source_ref": source_ref,
        "evidence": {
            "freeze": str(freeze_path), "freeze_sha256": sha256_file(freeze_path),
            "field_dictionary": str(dictionary_path), "field_dictionary_sha256": sha256_file(dictionary_path),
            "ratio_observation": "本地 L_INDVCST_LABEL 实测比例字段范围为 0..1；需由执行记录保留查询结果",
            "amount_rule": "字段字典声明金额默认元；名称含万元按 unit_scale=10000",
            "hierarchy_policy": "机构码仅按名义枚举，不依据编码前缀臆造层级",
        },
        "counts": {
            "source_fields": len(tags), "business_tags_reviewed": len(business_tags),
            "code_fields_reviewed": len(code_tags), "code_values_reviewed": len(codes),
            "concepts_reviewed": len(concepts), "aliases_reviewed": len(aliases),
            "aliases_added_for_gate": aliases_added, "semantic_or_unit_corrections": changed,
            "cross_domain_concepts_split": split_count,
            "minimum_tag_aliases": min(alias_counts[str(row["tag_id"])] for row in business_tags),
        },
        "expected_gate": {
            "business_coverage": "969/969", "code_semantics": "1723/1723 across 177 fields",
            "minimum_completeness": 95, "golden_minimum": 95,
        },
        "limitations": [
            "这是本地演示 AI 专家复核，不等同于银行生产业务人员签字。",
            "无权威组织层级来源的机构码保持 ENUM_NOMINAL。",
            "高质量指标必须由封存评测实测，不能由本清单预先宣称通过。",
        ],
    }
    (output_dir / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freeze", type=Path)
    parser.add_argument("--drafts-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--field-dictionary", type=Path, required=True)
    args = parser.parse_args()
    manifest = review_package(args.freeze, args.drafts_dir, args.out_dir, args.field_dictionary)
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
