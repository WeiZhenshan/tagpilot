"""快照规范化与内容哈希。信封字段不参与哈希。"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any

ENVELOPE_KEYS = {"snapshot_id", "snapshot_no", "generated_at", "content_hash"}


def canonical_json(value):
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical_json(value[k]) for k in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    if isinstance(value, (float, Decimal)):
        if not math.isfinite(value):
            raise ValueError("非有限数值不能进入快照")
        number = Decimal(str(value))
        return "0" if not number else format(number.normalize(), "f")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sort_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        if value and all(isinstance(x, dict) for x in value):
            return [sort_value(x) for x in sorted(value, key=lambda x: canonical_json(sort_value(x)))]
        if value and all(not isinstance(x, (dict, list)) for x in value):
            # 有序路径/区间保留；无序标量集合排序
            return value
        return [sort_value(x) for x in value]
    return value


def canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    excluded = ENVELOPE_KEYS | {"status"} if row.get("kind") == "meta" else set()
    cleaned = {k: v for k, v in row.items() if k not in excluded and k != "hit_count"}
    if row.get("kind") == "meta" and isinstance(cleaned.get("source_manifest"), dict):
        cleaned["source_manifest"] = {k: v for k, v in cleaned["source_manifest"].items() if k not in {"frozen_at", "freeze_sha256"}}
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
    return canonical_json(canonical_row(row))


def content_hash(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=row_sort_key)
    payload = "\n".join(dumps_row(r) for r in ordered) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dumps_jsonl(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=row_sort_key)
    return "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"), sort_keys=True) for r in ordered) + "\n"
