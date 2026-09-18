"""RRF 融合。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def rrf(rank_lists: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    payload: dict[str, dict[str, Any]] = {}
    features: dict[str, dict[str, Any]] = defaultdict(dict)
    for channel_hits in rank_lists:
        for hit in channel_hits:
            doc = hit["doc"]
            key = doc["doc_id"]
            rank = hit.get("rank") or 1
            scores[key] += 1.0 / (k + rank)
            payload[key] = doc
            features[key][hit.get("channel") or "x"] = rank
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for key, score in ranked:
        results.append({"doc": payload[key], "rrf_score": score, "rank_features": dict(features[key])})
    return results
