"""进程内 AC 别名词典：长词优先。"""

from __future__ import annotations

from typing import Any, Iterable


class AliasIndex:
    def __init__(self) -> None:
        self._entries: dict[str, list[dict[str, Any]]] = {}

    def build(self, aliases: Iterable[dict[str, Any]]) -> None:
        self._entries = {}
        for alias in aliases:
            if alias.get("review_status") != "REVIEWED":
                continue
            if alias.get("alias_type") == "NEGATIVE":
                continue
            norm = alias.get("alias_norm") or ""
            if not norm:
                continue
            self._entries.setdefault(norm, []).append(alias)
        self._sorted = sorted(self._entries.keys(), key=len, reverse=True)

    def lookup(self, text: str) -> list[dict[str, Any]]:
        query = (text or "").strip().lower().replace(" ", "")
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in getattr(self, "_sorted", []):
            if key and key in query and key not in seen:
                if len(key) == 1 and len(query) > 1:
                    continue
                seen.add(key)
                hits.extend(self._entries[key])
        return hits
