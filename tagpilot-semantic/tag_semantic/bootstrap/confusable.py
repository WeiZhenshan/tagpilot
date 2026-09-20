"""同族时间面易混淆对。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def build_time_facet_pairs(tags: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        if tag.get("kind") and tag.get("kind") != "tag_semantic":
            continue
        if tag.get("semantic_type") == "ID_KEY":
            continue
        family = tag.get("family_key")
        if not family:
            continue
        groups[family].append(tag)
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for family, members in groups.items():
        if len(members) < 2:
            continue
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                a = int(left["tag_id"])
                b = int(right["tag_id"])
                first, second = left, right
                if a > b:
                    a, b = b, a
                    first, second = right, left
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                la = (first.get("caliber_struct") or {}).get("time_anchor_label") or "无时间"
                lb = (second.get("caliber_struct") or {}).get("time_anchor_label") or "无时间"
                pairs.append(
                    {
                        "kind": "confusable",
                        "tag_id_a": a,
                        "tag_id_b": b,
                        "confusion_type": "TIME_FACET",
                        "difference_note": f"两者仅统计时点不同：{la} vs {lb}",
                        "disambiguation_hint": f"用户提到{la}选{first.get('name')}；提到{lb}选{second.get('name')}",
                        "source": "RULE",
                        "review_status": "DRAFT",
                        "family_key": family,
                    }
                )
    return pairs


def build_source_pairs(tags: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        code = tag.get("concept_code")
        if not code or tag.get("semantic_type") == "ID_KEY":
            continue
        by_concept[code].append(tag)
    pairs: list[dict[str, Any]] = []
    for members in by_concept.values():
        sources = {(m.get("caliber_struct") or {}).get("source_system") for m in members}
        if len(sources) < 2:
            continue
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                sa = (left.get("caliber_struct") or {}).get("source_system") or "NONE"
                sb = (right.get("caliber_struct") or {}).get("source_system") or "NONE"
                if sa == sb:
                    continue
                a, b = int(left["tag_id"]), int(right["tag_id"])
                if a > b:
                    a, b = b, a
                    left, right = right, left
                    sa, sb = sb, sa
                pairs.append(
                    {
                        "kind": "confusable",
                        "tag_id_a": a,
                        "tag_id_b": b,
                        "confusion_type": "SOURCE",
                        "difference_note": f"同一业务概念，来源不同：{sa} vs {sb}",
                        "disambiguation_hint": f"用户提到{sa}选{left.get('name')}；提到{sb}选{right.get('name')}",
                        "source": "RULE",
                        "review_status": "DRAFT",
                    }
                )
    return pairs
