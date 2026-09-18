"""快照规范化与内容哈希。信封字段不参与哈希。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

ENVELOPE_KEYS = {"snapshot_id", "snapshot_no", "generated_at", "content_hash", "status"}


def sort_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        if value and all(isinstance(x, dict) for x in value):
            return [sort_value(x) for x in sorted(value, key=lambda x: json.dumps(sort_value(x), ensure_ascii=False))]
        if value and all(not isinstance(x, (dict, list)) for x in value):
            # 有序路径/区间保留；无序标量集合排序
            return value
        return [sort_value(x) for x in value]
    return value


def canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in row.items() if k not in ENVELOPE_KEYS and k != "hit_count"}
    return sort_value(cleaned)


def row_sort_key(row: dict[str, Any]) -> tuple:
    kind = row.get("kind") or ""
    if kind == "meta":
        return (0, "", "")
    if kind == "domain":
        return (1, str(row.get("dir_id") or ""), "")
    if kind == "concept":
        return (2, str(row.get("concept_id") or row.get("concept_code") or ""), "")
    if kind == "tag":
        return (3, str(row.get("tag_id") or ""), "")
    if kind == "code_value":
        return (4, str(row.get("tag_id") or ""), str(row.get("code") or ""))
    if kind == "term":
        return (5, str(row.get("term_id") or row.get("term_norm") or ""), "")
    return (9, kind, json.dumps(row, ensure_ascii=False, sort_keys=True))


def dumps_row(row: dict[str, Any]) -> str:
    return json.dumps(canonical_row(row), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def content_hash(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=row_sort_key)
    payload = "\n".join(dumps_row(r) for r in ordered) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dumps_jsonl(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=row_sort_key)
    return "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"), sort_keys=True) for r in ordered) + "\n"
