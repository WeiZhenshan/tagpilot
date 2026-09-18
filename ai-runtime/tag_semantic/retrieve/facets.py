"""时间锚点 / 边界 / 否定解析，与 ts_business_term 同源。"""

from __future__ import annotations

from typing import Any

from tag_semantic.bootstrap.time_lexicon import parse_time_anchor
from tag_semantic.bootstrap.terms import seed_terms

BOUNDARY_MAP = {"以上": ">=", "及以上": ">=", "至少": ">=", "超过": ">", "高于": ">", "以下": "<=", "及以下": "<=", "不到": "<", "不足": "<"}
NEGATIONS = {"未", "没有", "不", "无", "排除", "非", "不是"}


def parse_facets(text: str, terms: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    terms = terms or seed_terms()
    time = parse_time_anchor(text)
    boundary = None
    for word, op in BOUNDARY_MAP.items():
        if word in text:
            boundary = {"word": word, "operator": op}
            break
    fuzzy = []
    for term in terms:
        if term.get("term") and term["term"] in text and term.get("default_policy") == "ASK":
            fuzzy.append(term["term"])
    negated = any(word in text for word in NEGATIONS)
    return {
        "time": time,
        "boundary": boundary,
        "unresolved_fuzzy_terms": fuzzy,
        "negated": negated,
    }
