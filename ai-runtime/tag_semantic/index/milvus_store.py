"""Milvus 适配：无 pymilvus 时明确不可用，禁止静默降级。"""

from __future__ import annotations

from typing import Any

from tag_semantic.index.store import IndexStore


class MilvusUnavailable(RuntimeError):
    pass


class MilvusStore(IndexStore):
    def __init__(self, uri: str = "http://127.0.0.1:19530", collection: str | None = None) -> None:
        self.uri = uri
        self.collection = collection
        try:
            import pymilvus  # noqa: F401
        except ImportError as exc:
            raise MilvusUnavailable("未安装 pymilvus，不能把本地基线当作 Milvus 集成验收") from exc

    def build(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        raise MilvusUnavailable("Milvus 构建需在 Standalone PoC 锁定补丁后启用")

    def search(self, channel: str, query: str, filters: dict[str, Any], k: int) -> list[dict[str, Any]]:
        raise MilvusUnavailable("Milvus 检索不可用")
