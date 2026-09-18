"""LLM 富化：只生成别名/定义/易混淆/正反例，禁止写事实字段。"""

from __future__ import annotations

import json
from typing import Any, Callable

FORBIDDEN_KEYS = {
    "rank_no",
    "lower_bound",
    "upper_bound",
    "unit",
    "unit_scale",
    "parent_code",
    "parent_tag_id",
    "statistic",
    "semantic_type",
}

SCHEMA_KEYS = {"aliases", "definition_long", "confusable", "positive_examples", "negative_examples"}


def validate_enrichment(payload: dict[str, Any]) -> dict[str, Any]:
    extra = set(payload) - SCHEMA_KEYS
    if extra:
        raise ValueError(f"LLM 输出含未允许字段: {sorted(extra)}")
    for key in FORBIDDEN_KEYS:
        dumped = json.dumps(payload, ensure_ascii=False)
        if f'"{key}"' in dumped:
            raise ValueError(f"禁止 LLM 生成事实字段 {key}")
    aliases = payload.get("aliases") or []
    if not isinstance(aliases, list):
        raise ValueError("aliases 必须是数组")
    return {
        "aliases": aliases,
        "definition_long": payload.get("definition_long") or "",
        "confusable": payload.get("confusable") or [],
        "positive_examples": payload.get("positive_examples") or [],
        "negative_examples": payload.get("negative_examples") or [],
        "source": "LLM",
        "review_status": "DRAFT",
    }


def enrich_concept(concept: dict[str, Any], generate: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    prompt = (
        "根据已审核概念生成检索别名和正反例 JSON。"
        "禁止编造金额区间、单位、机构树或统计口径。"
        f"概念:{concept.get('concept_code')} {concept.get('concept_name')} {concept.get('definition')}"
    )
    raw = generate(prompt)
    return validate_enrichment(raw)


def stub_generate(prompt: str) -> dict[str, Any]:
    if "AUM" in prompt:
        return {
            "aliases": ["管资规模", "资产规模"],
            "definition_long": "客户资产管理规模",
            "confusable": [],
            "positive_examples": ["当前AUM超过50万的客户"],
            "negative_examples": ["近12个月最高AUM"],
        }
    return {
        "aliases": [],
        "definition_long": "",
        "confusable": [],
        "positive_examples": [],
        "negative_examples": [],
    }
