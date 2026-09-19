"""受控聚合画像：禁止自由文本 Top 原值。"""

from __future__ import annotations

from typing import Any, Iterable


TEXT_FREE = "TEXT_FREE"
ID_KEY = "ID_KEY"


def aggregate_profile(tag: dict[str, Any], values: Iterable[Any], profile_date: str) -> dict[str, Any]:
    semantic_type = tag.get("semantic_type")
    data = list(values)
    total = len(data)
    nulls = sum(1 for v in data if v is None or v == "")
    present = [v for v in data if v is not None and v != ""]
    row = {
        "kind": "profile",
        "tag_id": tag.get("tag_id"),
        "profile_date": profile_date,
        "row_count": total,
        "null_rate": round(nulls / total, 4) if total else None,
        "distinct_count": len(set(map(str, present))),
        "sample_size": total,
        "sampled": 0,
        "top_values": None,
        "min_val": None,
        "max_val": None,
        "p50": None,
        "p90": None,
        "p99": None,
    }
    if semantic_type in {TEXT_FREE, ID_KEY, "UNKNOWN"} or tag.get("sensitivity") != "LOW" or len(present) < 20:
        return row
    if semantic_type in {"BOOL", "ENUM_NOMINAL", "ENUM_ORDINAL"}:
        freq: dict[str, int] = {}
        for value in present:
            key = str(value)
            freq[key] = freq.get(key, 0) + 1
        row["top_values"] = [{"code": k, "count": v} for k, v in sorted(freq.items(), key=lambda x: -x[1])[:20] if v >= 20 and k in set(map(str, tag.get("reviewed_codes") or []))]
        return row
    nums = []
    for value in present:
        try:
            nums.append(float(value))
        except (TypeError, ValueError):
            continue
    if not nums:
        return row
    nums.sort()
    row["min_val"] = nums[0]
    row["max_val"] = nums[-1]
    row["p50"] = _pct(nums, 0.50)
    row["p90"] = _pct(nums, 0.90)
    row["p99"] = _pct(nums, 0.99)
    return row


def _pct(sorted_nums: list[float], q: float) -> float:
    idx = min(len(sorted_nums) - 1, max(0, int(round((len(sorted_nums) - 1) * q))))
    return sorted_nums[idx]
