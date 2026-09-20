"""时间锚点与来源词典：长词优先，不先删时间再解析统计。"""

from __future__ import annotations

import re
from typing import Any, Optional

# 与方案 §8 同源；顺序即优先级（长词在前）。
TIME_PATTERNS: list[tuple[str, str]] = [
    (r"T-(\d+)月末", "MONTH_OFFSET"),
    (r"上(\d+)个月", "MONTH_OFFSET_WHOLE"),
    (r"近(\d+)个月", "WINDOW_MONTH"),
    (r"近(\d+)天", "WINDOW_DAY"),
    (r"近(\d+)日", "WINDOW_DAY"),
    (r"近(\d+)月", "WINDOW_MONTH"),
    (r"未来(\d+)天", "FUTURE_DAY"),
    (r"近一年", "WINDOW_YEAR"),
    (r"上年末", "YEAR_END"),
    (r"上年", "YEAR_OFFSET"),
    (r"上月末", "MONTH_END"),
    (r"上月", "LAST_MONTH"),
    (r"本月", "MTD"),
    (r"本年", "YTD"),
    (r"历史", "HIST"),
    (r"当前时点", "POINT_NOW"),
    (r"当前", "POINT_NOW"),
    (r"最新", "LATEST"),
]

SOURCE_PATTERNS: list[tuple[str, str]] = [
    (r"[（(]企微标签[)）]", "WECOM"),
    (r"[（(]私银KYC[)）]", "PB_KYC"),
    (r"[（(]运营KYC[)）]", "OPS_KYC"),
    (r"[（(]理财风评[)）]", "RISK_EVAL"),
    (r"[（(]规则预测[)）]", "MODEL"),
    (r"[（(]财富价值潜力模型[)）]", "MODEL"),
    (r"[（(]本行[)）]", "OUR_BANK"),
    (r"[（(]KYC[)）]", "KYC"),
]

# 长词优先；单字「分/率」不在此表。
STAT_HINTS: list[tuple[str, str]] = [
    ("日均", "AVG_DAILY"),
    ("最高", "MAX"),
    ("最低", "MIN"),
    ("累计", "SUM"),
    ("次数", "COUNT"),
    ("笔数", "COUNT"),
    ("占比", "RATIO"),
    ("比例", "RATIO"),
    ("完整度", "RATIO"),
    ("评分", "SCORE"),
    ("标志", "FLAG"),
    ("余额", "EOP"),
]


def compile_time_regex() -> re.Pattern[str]:
    parts = [p[0] for p in TIME_PATTERNS]
    return re.compile("|".join(f"({p})" for p in parts))


TIME_REGEX = compile_time_regex()


def parse_time_anchor(name: str) -> dict[str, Any]:
    """从原始名称提取时间锚点；未命中则为 NONE。"""
    empty = {
        "time_anchor_type": "NONE",
        "time_anchor_label": None,
        "time_offset_months": None,
        "time_offset_years": None,
        "time_window_value": None,
        "time_window_unit": None,
        "calendar_mode": None,
        "period_edge": None,
        "matched_span": None,
    }
    if not name:
        return empty
    match = TIME_REGEX.search(name)
    if not match:
        return empty
    span = match.group(0)
    result = dict(empty)
    result["time_anchor_label"] = span
    result["matched_span"] = span
    for pattern, kind in TIME_PATTERNS:
        inner = re.fullmatch(pattern, span)
        if not inner:
            continue
        return _fill_time(result, kind, inner)
    return result


def _fill_time(result: dict[str, Any], kind: str, inner: re.Match[str]) -> dict[str, Any]:
    if kind == "MONTH_OFFSET":
        result.update(
            time_anchor_type="MONTH_OFFSET",
            time_offset_months=int(inner.group(1)),
            calendar_mode="CALENDAR",
            period_edge="END",
        )
    elif kind == "MONTH_OFFSET_WHOLE":
        result.update(
            time_anchor_type="MONTH_OFFSET",
            time_offset_months=int(inner.group(1)),
            calendar_mode="CALENDAR",
            period_edge="WHOLE",
        )
    elif kind == "WINDOW_MONTH":
        result.update(
            time_anchor_type="WINDOW",
            time_window_value=int(inner.group(1)),
            time_window_unit="MONTH",
            calendar_mode="ROLLING",
            period_edge="WHOLE",
        )
    elif kind == "WINDOW_DAY":
        result.update(
            time_anchor_type="WINDOW",
            time_window_value=int(inner.group(1)),
            time_window_unit="DAY",
            calendar_mode="ROLLING",
            period_edge="WHOLE",
        )
    elif kind == "WINDOW_YEAR":
        result.update(
            time_anchor_type="WINDOW",
            time_window_value=1,
            time_window_unit="YEAR",
            calendar_mode="ROLLING",
            period_edge="WHOLE",
        )
    elif kind == "FUTURE_DAY":
        result.update(
            time_anchor_type="FUTURE",
            time_window_value=int(inner.group(1)),
            time_window_unit="DAY",
            calendar_mode="ROLLING",
            period_edge="WHOLE",
        )
    elif kind == "YEAR_END":
        result.update(
            time_anchor_type="YEAR_OFFSET",
            time_offset_years=1,
            calendar_mode="CALENDAR",
            period_edge="END",
        )
    elif kind == "YEAR_OFFSET":
        result.update(
            time_anchor_type="YEAR_OFFSET",
            time_offset_years=1,
            calendar_mode="CALENDAR",
            period_edge="WHOLE",
        )
    elif kind == "MONTH_END":
        result.update(
            time_anchor_type="MONTH_OFFSET",
            time_offset_months=1,
            calendar_mode="CALENDAR",
            period_edge="END",
        )
    elif kind == "LAST_MONTH":
        result.update(
            time_anchor_type="MONTH_OFFSET",
            time_offset_months=1,
            calendar_mode="CALENDAR",
            period_edge="WHOLE",
        )
    elif kind == "MTD":
        result.update(time_anchor_type="MTD", calendar_mode="CALENDAR", period_edge="TO_DATE")
    elif kind == "YTD":
        result.update(time_anchor_type="YTD", calendar_mode="CALENDAR", period_edge="TO_DATE")
    elif kind == "HIST":
        result.update(time_anchor_type="HIST", calendar_mode=None, period_edge=None)
    elif kind == "POINT_NOW":
        result.update(time_anchor_type="POINT", calendar_mode=None, period_edge="END")
    elif kind == "LATEST":
        result.update(time_anchor_type="POINT", calendar_mode=None, period_edge="END")
    return result


def parse_source_system(name: str) -> tuple[Optional[str], Optional[str]]:
    if not name:
        return None, None
    for pattern, code in SOURCE_PATTERNS:
        match = re.search(pattern, name)
        if match:
            return code, match.group(0)
    return None, None


def parse_scope(name: str) -> str:
    if not name:
        return "ALL"
    if "本行" in name:
        return "OUR_BANK"
    if "私银" in name:
        return "PB"
    return "ALL"


def parse_statistics(name: str) -> list[str]:
    """在原始名称上独立提取统计线索，长词优先，可同时命中 HIST+MAX。"""
    if not name:
        return []
    hits: list[str] = []
    remaining = name
    for token, code in STAT_HINTS:
        if token in remaining:
            hits.append(code)
            remaining = remaining.replace(token, "", 1)
    return hits
