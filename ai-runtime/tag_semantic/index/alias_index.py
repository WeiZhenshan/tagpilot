"""AC 自动机；以 JSON 数据安全持久化，不加载任意 pickle 代码。"""
from typing import Any, Iterable
from pathlib import Path
import json
import ahocorasick


class AliasIndex:
    def __init__(self):
        self._entries = {}
        self._automaton = None

    def build(self, aliases: Iterable[dict[str, Any]]) -> None:
        self._entries = {}
        for alias in aliases:
            if alias.get('review_status') != 'REVIEWED' or alias.get('alias_type') == 'NEGATIVE':
                continue
            norm = (alias.get('alias_norm') or '').lower().replace(' ', '')
            if norm:
                bucket = self._entries.setdefault(norm, [])
                if alias not in bucket:
                    bucket.append(alias)
        self._automaton = ahocorasick.Automaton()
        for key in self._entries:
            self._automaton.add_word(key, key)
        if self._entries:
            self._automaton.make_automaton()

    def lookup(self, text):
        query = (text or '').strip().lower().replace(' ', '')
        if not self._entries:
            return []
        keys = {key for _, key in self._automaton.iter(query) if len(key) > 1 or query == key}
        return [a for key in sorted(keys, key=lambda s: (-len(s), s)) for a in self._entries[key]]

    def save(self, path: Path):
        path.write_text(json.dumps([a for rows in self._entries.values() for a in rows], ensure_ascii=False, sort_keys=True), encoding='utf-8')

    @classmethod
    def load(cls, path):
        instance = cls()
        instance.build(json.loads(Path(path).read_text(encoding='utf-8')))
        return instance
