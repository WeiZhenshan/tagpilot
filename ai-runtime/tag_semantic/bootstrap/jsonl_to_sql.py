"""把 rule_init_result.jsonl 转成幂等 SQL。REVIEWED 跳过由 Java import 负责。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sql_str(value) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def sql_num(value) -> str:
    if value is None:
        return "NULL"
    return str(value)


def sql_json(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "CAST(" + sql_str(raw) + " AS JSON)"


def convert(result_path: Path, sql_path: Path) -> tuple[int, int]:
    tags = []
    codes = []
    with result_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("kind") == "tag_semantic":
                tags.append(row)
            elif row.get("kind") == "code_value_semantic":
                codes.append(row)
    parts = ["SET NAMES utf8mb4;", "USE ry;"]
    for row in tags:
        parts.append(
            "INSERT INTO ts_tag_semantic ("
            "tag_id, concept_id, family_key, caliber_variant, semantic_type, allowed_operators, "
            "default_operator, unit, unit_scale, caliber_struct, definition_long, sensitivity, "
            "basis_hash, source, review_status, semantic_version, source_ref, create_by, create_time, remark"
            ") VALUES ("
            f"{int(row['tag_id'])}, NULL, {sql_str(row.get('family_candidate') or 'UNNAMED|NONE|ALL|NONE|NONE|BASE')}, "
            f"{sql_str(row.get('caliber_variant') or 'BASE')}, {sql_str(row.get('semantic_type'))}, "
            f"{sql_str(json.dumps(row.get('allowed_operators') or [], ensure_ascii=False))}, "
            f"{sql_str(row.get('default_operator'))}, {sql_str(row.get('unit') or 'NONE')}, "
            f"{sql_num(row.get('unit_scale') if row.get('unit_scale') is not None else 1)}, "
            f"{sql_json(row.get('caliber_struct') or {})}, {sql_str(row.get('definition_long'))}, "
            f"{sql_str(row.get('sensitivity') or 'UNKNOWN')}, {sql_str(row.get('basis_hash'))}, "
            "'RULE', 'DRAFT', 1, 'rule_init', 'rule_init', NOW(), "
            f"{sql_str(row.get('concept_candidate'))}"
            ") ON DUPLICATE KEY UPDATE "
            "family_key=VALUES(family_key), caliber_variant=VALUES(caliber_variant), "
            "semantic_type=VALUES(semantic_type), allowed_operators=VALUES(allowed_operators), "
            "default_operator=VALUES(default_operator), unit=VALUES(unit), unit_scale=VALUES(unit_scale), "
            "caliber_struct=VALUES(caliber_struct), definition_long=VALUES(definition_long), "
            "sensitivity=VALUES(sensitivity), basis_hash=VALUES(basis_hash), source='RULE', "
            "review_status=IF(review_status='REVIEWED', review_status, 'DRAFT'), "
            "remark=VALUES(remark), update_by='rule_init', update_time=NOW();"
        )
    for row in codes:
        parts.append(
            "INSERT INTO ts_code_value_semantic ("
            "tag_id, code, rank_no, lower_bound, upper_bound, lower_inclusive, upper_inclusive, bound_unit, "
            "is_unknown_bucket, basis_hash, source, review_status, source_ref, create_by, create_time"
            ") VALUES ("
            f"{int(row['tag_id'])}, {sql_str(row.get('code'))}, {sql_num(row.get('rank_no'))}, "
            f"{sql_num(row.get('lower_bound'))}, {sql_num(row.get('upper_bound'))}, "
            f"{sql_num(row.get('lower_inclusive'))}, {sql_num(row.get('upper_inclusive'))}, "
            f"{sql_str(row.get('bound_unit'))}, 0, {sql_str(row.get('basis_hash'))}, "
            "'RULE', 'DRAFT', 'rule_init', 'rule_init', NOW()"
            ") ON DUPLICATE KEY UPDATE "
            "rank_no=VALUES(rank_no), lower_bound=VALUES(lower_bound), upper_bound=VALUES(upper_bound), "
            "lower_inclusive=VALUES(lower_inclusive), upper_inclusive=VALUES(upper_inclusive), "
            "bound_unit=VALUES(bound_unit), basis_hash=VALUES(basis_hash), source='RULE', "
            "review_status=IF(review_status='REVIEWED', review_status, 'DRAFT'), "
            "update_by='rule_init', update_time=NOW();"
        )
    sql_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {sql_path} tags={len(tags)} codes={len(codes)}")
    return len(tags), len(codes)


def main() -> None:
    out = ROOT / "ai-runtime/tag_semantic/out"
    convert(out / "rule_init_result.jsonl", out / "rule_init_import.sql")


if __name__ == "__main__":
    main()
