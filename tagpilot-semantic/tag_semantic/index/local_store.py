"""本地 BM25（Okapi）对照实现，不依赖外部包。"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

from tag_semantic.index.store import IndexStore

TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


class LocalStore(IndexStore):
    store_type = "LOCAL"
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self._name_index: dict[str, Any] = {}
        self._body_index: dict[str, Any] = {}

    def build(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        self.docs = list(docs)
        self._name_index = self._build_field("name_text")
        self._body_index = self._build_field("body_text")
        return {"doc_count": len(self.docs), "store_type": "LOCAL"}

    def _build_field(self, field: str) -> dict[str, Any]:
        df: Counter[str] = Counter()
        tf_list: list[Counter[str]] = []
        lengths = []
        for doc in self.docs:
            tokens = tokenize(doc.get(field) or "")
            tf = Counter(tokens)
            tf_list.append(tf)
            lengths.append(len(tokens) or 1)
            df.update(tf.keys())
        n = max(len(self.docs), 1)
        avgdl = sum(lengths) / n
        idf = {term: math.log((n - freq + 0.5) / (freq + 0.5) + 1) for term, freq in df.items()}
        return {"tf": tf_list, "idf": idf, "dl": lengths, "avgdl": avgdl}

    def _bm25(self, index: dict[str, Any], query: str, k: int = 30) -> list[tuple[int, float]]:
        q_tokens = tokenize(query)
        scores: dict[int, float] = defaultdict(float)
        k1, b = 1.5, 0.75
        for i, tf in enumerate(index["tf"]):
            dl = index["dl"][i]
            score = 0.0
            for term in q_tokens:
                if term not in tf:
                    continue
                idf = index["idf"].get(term, 0.0)
                freq = tf[term]
                score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / index["avgdl"]))
            if score:
                scores[i] = score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return ranked

    def search(self, channel: str, query: str, filters: dict[str, Any], k: int) -> list[dict[str, Any]]:
        index = self._name_index if channel == "bm25_name" else self._body_index
        eligible = filters.get("eligible_tag_ids")
        eligible_concepts = filters.get("eligible_concept_ids")
        results = []
        for idx, score in self._bm25(index, query, k=len(self.docs)):
            doc = self.docs[idx]
            if not _allowed(doc, eligible, eligible_concepts):
                continue
            results.append({"doc": doc, "score": score, "rank": len(results) + 1, "channel": channel})
            if len(results) >= k:
                break
        return results


def _allowed(doc: dict[str, Any], eligible: set[int] | None, eligible_concepts: set[Any] | None) -> bool:
    if doc.get("doc_type") == "concept":
        if eligible_concepts is not None and doc.get("concept_id") not in eligible_concepts:
            return False
        return True
    if eligible is not None and int(doc.get("tag_id") or -1) not in eligible:
        return False
    return True
