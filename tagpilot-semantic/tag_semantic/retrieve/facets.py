"""时间锚点 / 边界 / 否定解析，与 ts_business_term 同源。"""

from __future__ import annotations

from typing import Any

from tag_semantic.bootstrap.time_lexicon import parse_time_anchor
from tag_semantic.bootstrap.terms import seed_terms

BOUNDARY_MAP = {"以上": ">=", "及以上": ">=", "至少": ">=", "超过": ">", "高于": ">", "以下": "<=", "及以下": "<=", "不到": "<", "不足": "<"}
NEGATIONS = {"未", "没有", "不", "无", "排除", "非", "不是"}

def matched_terms(text, terms, resolution='legacy'):
    """更具体的已复核字段词仅覆盖其词面内的模糊词，不给裸业务词默认口径。"""
    matched=[t for t in terms if t.get('term') and t['term'] in text]
    if resolution!='specific-v1':return matched
    resolved=[]
    for term in matched:
        if (term.get('policy') or term.get('default_policy')) not in {'ASK','CLARIFY'}:
            resolved.append(term);continue
        word=term['term'];positions=[i for i in range(len(text)) if text.startswith(word,i)]
        covers=[]
        for specific in matched:
            s=specific['term']
            if (specific.get('policy') or specific.get('default_policy'))!='RESOLVE_BY_FIELD' or len(s)<=len(word):continue
            covers.extend((i,i+len(s)) for i in range(len(text)) if text.startswith(s,i))
        if not all(any(a<=i and i+len(word)<=b for a,b in covers) for i in positions):resolved.append(term)
    return resolved


def parse_facets(text: str, terms: list[dict[str, Any]] | None = None, resolution='legacy') -> dict[str, Any]:
    terms = seed_terms() if terms is None else terms
    time = parse_time_anchor(text)
    boundary = None
    for word, op in BOUNDARY_MAP.items():
        if word in text:
            boundary = {"word": word, "operator": op}
            break
    fuzzy = []
    for term in matched_terms(text,terms,resolution):
        if term.get("term") and term["term"] in text and (term.get("default_policy") or term.get("policy")) in {"ASK", "CLARIFY"}:
            fuzzy.append(term["term"])
    negated = any(word in text for word in NEGATIONS)
    return {
        "time": time,
        "boundary": boundary,
        "unresolved_fuzzy_terms": fuzzy,
        "negated": negated,
    }
