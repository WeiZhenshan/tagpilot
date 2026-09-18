"""族解析：明确时间则选中；无时间多成员则澄清。"""

from __future__ import annotations

from typing import Any


def resolve_family(members: list[dict[str, Any]], time_facet: dict[str, Any]) -> dict[str, Any]:
    if not members:
        return {"status": "empty", "selected": None, "confusable_shown": []}
    if len(members) == 1:
        return {"status": "selected", "selected": members[0], "confusable_shown": []}
    wanted = (time_facet or {}).get("time_anchor_type")
    window = (time_facet or {}).get("time_window_value")
    unit = (time_facet or {}).get("time_window_unit")
    if wanted and wanted != "NONE":
        matched = []
        for member in members:
            caliber = member.get("caliber_struct") or {}
            if caliber.get("time_anchor_type") != wanted:
                continue
            if wanted == "WINDOW" and window is not None:
                if caliber.get("time_window_value") != window or caliber.get("time_window_unit") != unit:
                    continue
            matched.append(member)
        if len(matched) == 1:
            others = [m for m in members if m is not matched[0] and m.get("tag_id") != matched[0].get("tag_id")]
            return {"status": "selected", "selected": matched[0], "confusable_shown": others}
        if not matched:
            return {
                "status": "clarify_time",
                "selected": None,
                "confusable_shown": members,
                "reason": "明确时间在族内不存在",
            }
    return {"status": "clarify_time", "selected": None, "confusable_shown": members, "reason": "无时间表达且族内多成员"}


def expand_ordinal_codes(codes: list[dict[str, Any]], operator: str, threshold_rank: int | None) -> list[str] | None:
    if threshold_rank is None:
        return None
    selected = []
    for row in codes:
        rank = row.get("rank_no")
        if rank is None:
            continue
        if operator == ">=" and rank >= threshold_rank:
            selected.append(str(row["code"]))
        elif operator == ">" and rank > threshold_rank:
            selected.append(str(row["code"]))
        elif operator == "<=" and rank <= threshold_rank:
            selected.append(str(row["code"]))
        elif operator == "<" and rank < threshold_rank:
            selected.append(str(row["code"]))
    return selected


def interval_covers(codes: list[dict[str, Any]], lower: float | None, upper: float | None, op: str) -> dict[str, Any]:
    """分档必须能精确表达，否则不可自动近似。"""
    if op == ">" and lower is not None:
        for row in codes:
            if row.get("lower_bound") == lower and row.get("lower_inclusive") == 1:
                return {"expressible": False, "reason": "超过下界切穿闭区间，不能用该档近似"}
    return {"expressible": True}
