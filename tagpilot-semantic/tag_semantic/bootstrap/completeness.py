"""完整度评分 §9.1：0-100。"""

from __future__ import annotations

from typing import Any, Iterable


def score_tag(
    tag: dict[str, Any],
    *,
    aliases: Iterable[dict[str, Any]] = (),
    codes: Iterable[dict[str, Any]] = (),
    confusable: Iterable[dict[str, Any]] = (),
    examples: Iterable[dict[str, Any]] = (),
    concept: dict[str, Any] | None = None,
) -> int:
    score = 0
    semantic_type = tag.get("semantic_type")
    operators = tag.get("allowed_operators") or []
    if semantic_type and (semantic_type == "ID_KEY" or operators):
        score += 15
    caliber = tag.get("caliber_struct") or {}
    if caliber.get("statistic") is not None and caliber.get("scope") is not None:
        score += 20
    if (
        concept
        and concept.get("review_status") == "REVIEWED"
        and concept.get("status") == "0"
        and tag.get("concept_code")
    ):
        score += 10
    reviewed_aliases = [
        a
        for a in aliases
        if a.get("review_status") == "REVIEWED" and a.get("alias_type") != "NEGATIVE"
    ]
    alias_points = min(20, len(reviewed_aliases) * 7)
    if any(a.get("target_type") == "CONCEPT" for a in reviewed_aliases):
        alias_points = min(20, alias_points + 3)
    if len(reviewed_aliases) >= 3:
        alias_points = 20
    score += alias_points
    definition = (tag.get("definition_long") or "").strip()
    if tag.get("review_status") == "REVIEWED" and len(definition) >= 4:
        score += 10
    if semantic_type in {"BOOL", "ENUM_NOMINAL", "ENUM_ORDINAL", "ENUM_HIERARCHY"}:
        code_list = list(codes)
        if code_list and all(c.get("review_status") == "REVIEWED" for c in code_list):
            score += 10
    else:
        score += 10
    tag_id = tag.get("tag_id")
    notes = [
        c
        for c in confusable
        if c.get("review_status") == "REVIEWED"
        and tag_id in {c.get("tag_id_a"), c.get("tag_id_b")}
        and c.get("difference_note")
    ]
    if notes or semantic_type in {"ID_KEY", "TEXT_FREE"}:
        score += 10
    elif not any(True for c in confusable if tag_id in {c.get("tag_id_a"), c.get("tag_id_b")}):
        score += 10
    pos = [
        e
        for e in examples
        if e.get("review_status") == "REVIEWED" and e.get("example_type") == "POS"
    ]
    if pos:
        score += 5
    return min(100, score)


def gold_ready(score: int, gold: bool) -> bool:
    return score >= (90 if gold else 70)
