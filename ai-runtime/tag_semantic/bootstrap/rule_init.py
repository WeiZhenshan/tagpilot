"""S2 规则初始化：冻结 JSONL → DRAFT 语义 + unresolved。不连业务库。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

from tag_semantic.bootstrap.time_lexicon import (
    parse_scope,
    parse_source_system,
    parse_statistics,
    parse_time_anchor,
)

OPERATORS = {
    "BOOL": ["="],
    "ENUM_NOMINAL": ["=", "in", "not_in"],
    "ENUM_ORDINAL": ["=", "in", "not_in"],
    "ENUM_HIERARCHY": ["=", "in"],
    "TEXT_FREE": ["like", "contains"],
    "NUM_AMOUNT": [">", ">=", "<", "<=", "between"],
    "NUM_COUNT": [">", ">=", "<", "<=", "between"],
    "NUM_RATIO": [">", ">=", "<", "<=", "between"],
    "NUM_SCORE": [">", ">=", "<", "<=", "between"],
    "DATE": ["=", ">", "<", "between"],
    "ID_KEY": [],
}

INSTITUTION_FIELDS = {
    "CUR_CORE_CM_LEVEL1_BRANCH",
    "CUR_CORE_CM_LEVEL2_BRANCH",
    "CUR_CORE_CM_LEVEL3_BRANCH",
}

ORDINAL_TEXT_RE = re.compile(r"含|以下|及以上|以上")
LEADING_ZERO_CODE_RE = re.compile(r"^0\d+$")
RISK_LEVEL_RE = re.compile(r"^C[1-9]$")
AMOUNT_HINT_RE = re.compile(r"金额|余额|AUM|中收|收益|资产")
COUNT_HINT_RE = re.compile(r"次数|笔数|天数|数量")
RATIO_HINT_RE = re.compile(r"占比|比例|完整度")
SCORE_HINT_RE = re.compile(r"评分|意向分")


def load_freeze(path: Path) -> dict[str, Any]:
    meta = None
    domains: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    codes_by_tag: dict[int, list[dict[str, Any]]] = {}
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"冻结 JSONL 第 {line_no} 行无法解析: {exc}") from exc
            kind = row.get("kind")
            if kind == "meta":
                meta = row
            elif kind == "domain":
                domains.append(row)
            elif kind == "tag":
                tags.append(row)
            elif kind == "code_value":
                tag_id = int(row["tag_id"])
                codes_by_tag.setdefault(tag_id, []).append(row)
            else:
                raise ValueError(f"冻结 JSONL 第 {line_no} 行未知 kind={kind}")
    if meta is None:
        raise ValueError("冻结 JSONL 缺少 meta 行")
    return {"meta": meta, "domains": domains, "tags": tags, "codes_by_tag": codes_by_tag}


def _base_data_type(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return raw.split("(", 1)[0].strip().lower()


def _codes_are_bool(codes: list[dict[str, Any]]) -> bool:
    if not codes:
        return False
    values = {str(c.get("code", "")).strip() for c in codes}
    return values <= {"0", "1"} and len(values) >= 1


def _looks_ordinal(tag: dict[str, Any], codes: list[dict[str, Any]]) -> bool:
    name = str(tag.get("name") or "")
    if "分档" in name or "等级" in name:
        return True
    if not codes:
        return False
    labels = [str(c.get("definition") or c.get("label") or "") for c in codes]
    if any(ORDINAL_TEXT_RE.search(label) for label in labels):
        return True
    code_vals = [str(c.get("code") or "") for c in codes]
    if code_vals and all(LEADING_ZERO_CODE_RE.match(v) for v in code_vals):
        return True
    if code_vals and all(RISK_LEVEL_RE.match(v) for v in code_vals):
        return True
    return False


def classify_semantic_type(
    tag: dict[str, Any], codes: list[dict[str, Any]], unresolved: list[dict[str, Any]]
) -> str:
    field = tag.get("field_name")
    if tag.get("is_object_key") in (1, "1", True):
        return "ID_KEY"
    data_type = _base_data_type(tag.get("data_type"))
    name = str(tag.get("name") or "")
    if field in INSTITUTION_FIELDS:
        return "ENUM_NOMINAL"
    if data_type == "tinyint":
        if not codes or _codes_are_bool(codes):
            return "BOOL"
        unresolved.append(_issue(tag, "TYPE_AMBIGUOUS", "TINYINT 码值不是 0/1，无法判定 BOOL"))
        return "BOOL"
    if data_type in ("text", "varchar", "char"):
        if codes:
            if _looks_ordinal(tag, codes):
                return "ENUM_ORDINAL"
            return "ENUM_NOMINAL"
        return "TEXT_FREE"
    if data_type in ("date", "datetime", "timestamp"):
        return "DATE"
    if data_type in ("decimal", "numeric", "float", "double"):
        if RATIO_HINT_RE.search(name):
            return "NUM_RATIO"
        if SCORE_HINT_RE.search(name):
            return "NUM_SCORE"
        if AMOUNT_HINT_RE.search(name) or "aum" in str(field or "").lower():
            return "NUM_AMOUNT"
        unresolved.append(_issue(tag, "TYPE_AMBIGUOUS", f"DECIMAL 字段无法从名称判定金额或占比: {name}"))
        return "NUM_AMOUNT"
    if data_type in ("int", "integer", "bigint", "smallint"):
        if COUNT_HINT_RE.search(name):
            return "NUM_COUNT"
        unresolved.append(_issue(tag, "TYPE_AMBIGUOUS", f"INT 字段无次数/数量线索: {name}"))
        return "NUM_COUNT"
    unresolved.append(_issue(tag, "TYPE_AMBIGUOUS", f"未能识别 data_type={tag.get('data_type')}"))
    return "TEXT_FREE"


def _issue(tag: dict[str, Any], issue: str, message: str, code: Optional[str] = None) -> dict[str, Any]:
    row = {
        "tag_id": tag.get("tag_id"),
        "field_name": tag.get("field_name"),
        "issue": issue,
        "message": message,
    }
    if code is not None:
        row["code"] = code
    return row


def parse_interval(definition: str) -> Optional[dict[str, Any]]:
    """解析『100万(含)-300万』『50万以下』『1000万及以上』。失败返回 None。"""
    if not definition:
        return None
    text = definition.replace("（含）", "(含)").replace(" ", "")
    if "万" not in text:
        return None
    below = re.fullmatch(r"(\d+(?:\.\d+)?)万(以下|及以下)", text)
    if below:
        bound = float(below.group(1)) * 10000
        inclusive = 1 if below.group(2) == "及以下" else 0
        return {
            "lower_bound": None,
            "upper_bound": bound,
            "lower_inclusive": None,
            "upper_inclusive": inclusive,
            "bound_unit": "CNY",
        }
    above = re.fullmatch(r"(\d+(?:\.\d+)?)万(\(含\))?(及以上|以上)", text)
    if above:
        bound = float(above.group(1)) * 10000
        return {
            "lower_bound": bound,
            "upper_bound": None,
            "lower_inclusive": 1,
            "upper_inclusive": None,
            "bound_unit": "CNY",
        }
    ranged = re.fullmatch(
        r"(\d+(?:\.\d+)?)万(\(含\))?-(\d+(?:\.\d+)?)万(\(含\))?",
        text,
    )
    if ranged:
        lower = float(ranged.group(1)) * 10000
        upper = float(ranged.group(3)) * 10000
        lower_inc = 1 if ranged.group(2) else 0
        upper_inc = 1 if ranged.group(4) else 0
        return {
            "lower_bound": lower,
            "upper_bound": upper,
            "lower_inclusive": lower_inc,
            "upper_inclusive": upper_inc,
            "bound_unit": "CNY",
        }
    return None


def pick_statistic(name: str, semantic_type: str, unresolved: list[dict[str, Any]], tag: dict[str, Any]) -> str:
    hits = parse_statistics(name)
    unique = []
    for item in hits:
        if item not in unique:
            unique.append(item)
    if "MAX" in unique and "MIN" in unique:
        unresolved.append(_issue(tag, "CALIBER_CONFLICT", f"同时命中最高与最低: {name}"))
    if semantic_type == "BOOL":
        return "FLAG"
    if semantic_type == "NUM_COUNT":
        return "COUNT"
    if semantic_type == "NUM_RATIO":
        return "RATIO"
    if semantic_type == "NUM_SCORE":
        return "SCORE"
    if semantic_type == "DATE":
        return "LATEST"
    if "AVG_DAILY" in unique:
        return "AVG_DAILY"
    if "MAX" in unique:
        return "MAX"
    if "MIN" in unique:
        return "MIN"
    if "SUM" in unique:
        return "SUM"
    if "EOP" in unique:
        return "EOP"
    if semantic_type == "NUM_AMOUNT":
        return "EOP"
    return "NONE"


def concept_candidate(name: str) -> str:
    if not name:
        return "UNNAMED"
    text = name
    time = parse_time_anchor(text)
    span = time.get("matched_span")
    if span:
        text = text.replace(span, "", 1)
    _, source_span = parse_source_system(name)
    if source_span:
        text = text.replace(source_span, "", 1)
    text = re.sub(r"[（()）]", "", text)
    text = text.strip(" -_/")
    return text or name


def family_candidate(concept: str, statistic: str, scope: str, source: Optional[str], unit: str) -> str:
    source_part = source or "NONE"
    return f"{concept}|{statistic}|{scope}|{source_part}|{unit}|BASE"


def basis_hash(tag: dict[str, Any], codes: list[dict[str, Any]]) -> str:
    payload = {
        "field_name": tag.get("field_name"),
        "name": tag.get("name"),
        "data_type": tag.get("data_type"),
        "business_caliber": tag.get("business_caliber") or "",
        "tech_caliber": tag.get("tech_caliber") or "",
        "version": tag.get("version"),
        "source_fingerprint": tag.get("source_fingerprint") or "",
        "codes": [
            {
                "code": c.get("code"),
                "definition": c.get("definition") or "",
                "label": c.get("label") or "",
            }
            for c in sorted(codes, key=lambda x: str(x.get("code") or ""))
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def init_tag(tag: dict[str, Any], codes: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    unresolved: list[dict[str, Any]] = []
    semantic_type = classify_semantic_type(tag, codes, unresolved)
    name = str(tag.get("name") or "")
    time = parse_time_anchor(name)
    source, _ = parse_source_system(name)
    scope = parse_scope(name)
    statistic = pick_statistic(name, semantic_type, unresolved, tag)
    unit = "NONE"
    unit_scale = 1
    if semantic_type == "NUM_AMOUNT":
        unresolved.append(_issue(tag, "UNIT_UNKNOWN", "金额单位无法从来源口径确认，禁止自动换算"))
    if semantic_type == "NUM_RATIO":
        unresolved.append(_issue(tag, "RATIO_SCALE_UNKNOWN", "占比量纲 0-1 与 0-100 不自动判定"))
    if semantic_type == "NUM_COUNT":
        unit = "COUNT"
    if field_is_institution(tag):
        unresolved.append(_issue(tag, "HIERARCHY_SKIPPED", "机构字段先按 ENUM_NOMINAL，禁止用联行号前缀猜父子树"))

    caliber = {
        "time_anchor_type": time["time_anchor_type"],
        "time_anchor_label": time["time_anchor_label"],
        "time_offset_months": time["time_offset_months"],
        "time_offset_years": time["time_offset_years"],
        "time_window_value": time["time_window_value"],
        "time_window_unit": time["time_window_unit"],
        "calendar_mode": time["calendar_mode"],
        "period_edge": time["period_edge"],
        "statistic": statistic,
        "scope": scope,
        "source_system": source,
        "unit": unit,
        "unit_scale": unit_scale,
        "numerator": None,
        "denominator": None,
        "boundary_semantics": "inclusive_lower" if semantic_type == "ENUM_ORDINAL" else None,
    }
    concept = concept_candidate(name)
    family = family_candidate(concept, statistic, scope, source, unit)
    hashed = basis_hash(tag, codes)
    tag_row = {
        "kind": "tag_semantic",
        "tag_id": tag.get("tag_id"),
        "library_id": tag.get("library_id"),
        "field_name": tag.get("field_name"),
        "name": tag.get("name"),
        "semantic_type": semantic_type,
        "allowed_operators": OPERATORS.get(semantic_type, []),
        "default_operator": (OPERATORS.get(semantic_type) or [None])[0],
        "unit": unit,
        "unit_scale": unit_scale,
        "caliber_struct": caliber,
        "concept_candidate": concept,
        "family_candidate": family,
        "caliber_variant": "BASE",
        "definition_long": (tag.get("business_caliber") or tag.get("name") or "")[:2000],
        "sensitivity": "UNKNOWN",
        "source": "RULE",
        "review_status": "DRAFT",
        "semantic_version": 1,
        "basis_hash": hashed,
        "authority": {
            "field_name": tag.get("field_name"),
            "business_caliber": tag.get("business_caliber") or "",
            "tech_caliber": tag.get("tech_caliber") or "",
            "data_type": tag.get("data_type"),
            "version": tag.get("version"),
            "source_fingerprint": tag.get("source_fingerprint") or "",
        },
        "business_candidate": tag.get("business_candidate", True),
    }
    code_rows = init_codes(tag, codes, semantic_type, hashed, unresolved)
    return tag_row, code_rows, unresolved


def field_is_institution(tag: dict[str, Any]) -> bool:
    return tag.get("field_name") in INSTITUTION_FIELDS


def init_codes(
    tag: dict[str, Any],
    codes: list[dict[str, Any]],
    semantic_type: str,
    tag_hash: str,
    unresolved: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_codes = sorted(codes, key=lambda c: (c.get("code_sort") is None, c.get("code_sort") or 0, str(c.get("code"))))
    for idx, code in enumerate(sorted_codes, 1):
        interval = None
        rank_no = None
        if semantic_type == "ENUM_ORDINAL":
            rank_no = idx
            definition = str(code.get("definition") or code.get("label") or "")
            interval = parse_interval(definition)
            if interval is None:
                unresolved.append(
                    _issue(
                        tag,
                        "ORDINAL_INTERVAL_UNPARSED",
                        f"有序码值未能解析区间: {definition}",
                        code=str(code.get("code")),
                    )
                )
        row = {
            "kind": "code_value_semantic",
            "tag_id": tag.get("tag_id"),
            "field_name": tag.get("field_name"),
            "code": code.get("code"),
            "label": code.get("label"),
            "definition": code.get("definition"),
            "rank_no": rank_no,
            "lower_bound": None if interval is None else interval["lower_bound"],
            "upper_bound": None if interval is None else interval["upper_bound"],
            "lower_inclusive": None if interval is None else interval["lower_inclusive"],
            "upper_inclusive": None if interval is None else interval["upper_inclusive"],
            "bound_unit": None if interval is None else interval["bound_unit"],
            "parent_tag_id": None,
            "parent_code": None,
            "level_no": None,
            "is_unknown_bucket": 0,
            "source": "RULE",
            "review_status": "DRAFT",
            "basis_hash": hashlib.sha256(
                json.dumps(
                    {
                        "tag_id": tag.get("tag_id"),
                        "code": code.get("code"),
                        "definition": code.get("definition") or "",
                        "tag_basis": tag_hash,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        rows.append(row)
    return rows


def run_rule_init(freeze: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    codes_by_tag = freeze["codes_by_tag"]
    for tag in freeze["tags"]:
        tag_id = int(tag["tag_id"])
        codes = codes_by_tag.get(tag_id, [])
        tag_row, code_rows, issues = init_tag(tag, codes)
        results.append(tag_row)
        results.extend(code_rows)
        unresolved.extend(issues)
    return {"result": results, "unresolved": unresolved}


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="从冻结 JSONL 生成 RULE/DRAFT 语义草稿")
    parser.add_argument("freeze_jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    freeze = load_freeze(args.freeze_jsonl)
    output = run_rule_init(freeze)
    write_jsonl(args.out_dir / "rule_init_result.jsonl", output["result"])
    write_jsonl(args.out_dir / "rule_init_unresolved.jsonl", output["unresolved"])
    print(
        f"tags={sum(1 for r in output['result'] if r.get('kind')=='tag_semantic')} "
        f"codes={sum(1 for r in output['result'] if r.get('kind')=='code_value_semantic')} "
        f"unresolved={len(output['unresolved'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
