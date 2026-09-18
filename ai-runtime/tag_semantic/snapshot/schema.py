"""快照 JSONL schema：Python loader 与 Java 发布共用 kind。"""

from __future__ import annotations

KINDS = ("meta", "domain", "concept", "tag", "code_value", "term")
SCHEMA_VERSION = "v1"
ENVELOPE_KEYS = {"snapshot_id", "snapshot_no", "generated_at", "content_hash", "status"}


def validate_row(row: dict) -> None:
    kind = row.get("kind")
    if kind not in KINDS:
        raise ValueError(f"未知 kind={kind}")
    if kind == "tag" and row.get("review_status") == "DRAFT":
        raise ValueError("DRAFT 不得进入快照")
