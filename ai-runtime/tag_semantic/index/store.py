"""IndexStore 抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IndexStore(ABC):
    @abstractmethod
    def build(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def search(self, channel: str, query: str, filters: dict[str, Any], k: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def activate(self, build_id: str) -> None:
        return None

    def drop(self, build_id: str) -> None:
        return None
