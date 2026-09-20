"""从 S0 清单与仓库内码表 SQL 组装试点冻结 JSONL。不连接业务库。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
S0 = ROOT / "docs/design/s0_source_inventory.json"
SQL_FILES = [
    ROOT / "sql/indiv_cust/03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql",
    ROOT / "sql/indiv_cust/04_insert_L_INDVCST_LABEL_CODE_MAP_OPTION.sql",
    ROOT / "sql/indiv_cust/05_insert_L_INDVCST_LABEL_CODE_MAP_BRANCH.sql",
]
ROW_RE = re.compile(
    r"\('([^']+)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*(\d+),"
)


def parse_codes(field_names: set[str]) -> list[dict]:
    rows: list[dict] = []
    for path in SQL_FILES:
        text = path.read_text(encoding="utf-8")
        for match in ROW_RE.finditer(text):
            field, code, label, definition, sort = match.groups()
            if field not in field_names:
                continue
            rows.append(
                {
                    "kind": "code_value",
                    "field_name": field,
                    "code": code,
                    "label": label,
                    "definition": definition,
                    "code_sort": int(sort),
                    "sources": [{"source_table_name": "L_INDVCST_LABEL_CODE_MAP"}],
                }
            )
    return rows


def build_freeze() -> list[dict]:
    inventory = json.loads(S0.read_text(encoding="utf-8"))
    tags = []
    for item in inventory["pilot_fields"]:
        tags.append(
            {
                "kind": "tag",
                "tag_id": item["tag_id"],
                "library_id": inventory["pilot_scope"]["library_id"],
                "field_name": item["field_name"],
                "name": item["tag_name"],
                "data_type": item["data_type"],
                "tag_type": item["tag_type"],
                "is_object_key": item.get("is_object_key", "0"),
                "business_candidate": item.get("is_object_key") != "1",
                "status": item["status"],
                "source_status": item["source_status"],
                "version": item["version"],
                "business_caliber": "",
                "tech_caliber": "",
                "binding": {"table": "L_INDVCST_LABEL", "column": item["field_name"]},
            }
        )
    field_names = {t["field_name"] for t in tags}
    by_field = {t["field_name"]: t["tag_id"] for t in tags}
    codes = parse_codes(field_names)
    for code in codes:
        code["tag_id"] = by_field[code["field_name"]]
    meta = {
        "kind": "meta",
        "library_id": 107,
        "schema_version": "v1",
        "source": "s0_inventory+repo_sql",
        "counts": {"tag": len(tags), "code_value": len(codes), "domain": 0},
    }
    return [meta] + tags + codes


def main() -> None:
    rows = build_freeze()
    out = ROOT / "tagpilot-semantic/tag_semantic/out/pilot_freeze.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {out} lines={len(rows)}")


if __name__ == "__main__":
    main()
