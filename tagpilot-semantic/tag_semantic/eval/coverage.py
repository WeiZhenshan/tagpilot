"""S10 覆盖率报告：必须带真实分母。"""

from __future__ import annotations

from typing import Any


def coverage_report(*, published_tags: int, library_tags: int = 969, reviewed: int, draft: int) -> dict[str, Any]:
    if library_tags <= 0:
        raise ValueError("分母必须为正")
    return {
        "scope": "PILOT" if published_tags < library_tags else "FULL",
        "published_tags": published_tags,
        "library_tags": library_tags,
        "coverage": f"{published_tags}/{library_tags}",
        "coverage_pct": round(100.0 * published_tags / library_tags, 1),
        "reviewed": reviewed,
        "draft": draft,
        "note": "不得把范围内覆盖写成全库 100%",
    }
