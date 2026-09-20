"""族解析：明确时间则选中；无时间多成员则澄清。"""

from __future__ import annotations

from typing import Any


def resolve_family(members: list[dict[str, Any]], time_facet: dict[str, Any]) -> dict[str, Any]:
    if not members:
        return {"status": "empty", "selected": None, "confusable_shown": []}
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
    if len(members) == 1:
        return {"status": "selected", "selected": members[0], "confusable_shown": []}
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


def interval_covers(codes, lower, upper, op):
    """仅当完整桶的并集严格等于请求区间时返回码集，禁止跨桶近似。"""
    from decimal import Decimal
    def number(value):
        return None if value is None else Decimal(str(value))
    def inclusive(value):
        return value in (True, 1, "1")
    lo, hi = number(lower), number(upper)
    if op not in {">", ">=", "<", "<=", "between"}:
        return {"expressible": False, "reason": "区间操作符不支持"}
    qli, qui = op in {">=", "between"}, op in {"<=", "between"}
    selected = []
    for row in codes:
        if row.get("is_unknown_bucket") in (True, 1, "1"):
            continue
        if "lower_bound" not in row or "upper_bound" not in row:
            return {"expressible": False, "reason": "缺少已复核区间"}
        a, b = number(row.get("lower_bound")), number(row.get("upper_bound"))
        ai, bi = inclusive(row.get("lower_inclusive")), inclusive(row.get("upper_inclusive"))
        # 与目标区间不相交。
        if b is not None and lo is not None and (b < lo or (b == lo and not (bi and qli))):
            continue
        if a is not None and hi is not None and (a > hi or (a == hi and not (ai and qui))):
            continue
        contained_left = lo is None or (a is not None and (a > lo or (a == lo and (qli or not ai))))
        contained_right = hi is None or (b is not None and (b < hi or (b == hi and (qui or not bi))))
        if not contained_left or not contained_right:
            return {"expressible": False, "reason": "阈值切穿分档，不能近似为码值集合"}
        selected.append((a, b, ai, bi, row["code"]))
    if not selected:
        return {"expressible": False, "reason": "无完整区间可表达该条件"}
    selected.sort(key=lambda r: (r[0] is not None, r[0] or Decimal(0)))
    first, last = selected[0], selected[-1]
    if first[0] != lo or last[1] != hi or (lo is not None and first[2] != qli) or (hi is not None and last[3] != qui):
        return {"expressible": False, "reason": "码值区间未完整覆盖目标条件"}
    for left, right in zip(selected, selected[1:]):
        if left[1] != right[0] or left[3] == right[2]:
            return {"expressible": False, "reason": "区间存在缺口或重叠"}
    return {"expressible": True, "codes": [r[4] for r in selected]}
