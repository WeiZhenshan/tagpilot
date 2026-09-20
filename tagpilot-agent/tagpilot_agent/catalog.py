"""检索层返回的目录切片；Agent 不加载快照或索引。"""

from __future__ import annotations

from typing import Any


class SliceCatalog:
    def __init__(self, payload: dict[str, Any] | None = None):
        payload = payload or {}
        self.tags = {int(tag["tag_id"]): tag for tag in payload.get("tags") or []}
        self.code_values = list(payload.get("code_values") or [])
