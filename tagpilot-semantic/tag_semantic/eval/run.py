"""评测运行与契约回归。"""

from __future__ import annotations

from tag_semantic.eval.coverage import coverage_report
from tag_semantic.eval.gold import GOLD_DEV, hit_at_k
from tag_semantic.retrieve.family import interval_covers
from tag_semantic.retrieve.service import RetrieveService


def run_dev_eval(service: RetrieveService, eligible: set[int] | None = None) -> dict:
    hits = 0
    clarify_ok = 0
    total = 0
    failures = []
    for case in GOLD_DEV:
        if case.get("inexpressible_approx"):
            continue
        total += 1
        result = service.retrieve(case["query"], eligible, k=20)
        ok = hit_at_k(result["candidates"], case["accept_tag_ids"], 20)
        family = result.get("family") or {}
        if case.get("must_clarify"):
            if str(family.get("status") or "").startswith("clarify"):
                clarify_ok += 1
            elif ok:
                hits += 1
            else:
                failures.append(case["id"])
        elif ok:
            hits += 1
        else:
            failures.append(case["id"])
    return {
        "hit_at_20": hits,
        "clarify_ok": clarify_ok,
        "total": total,
        "failures": failures,
        "coverage_note": "开发集 20 条，不是封存 600 条验收",
        "gold_dev_size": len(GOLD_DEV),
    }


def contract_empty_eligible(service: RetrieveService) -> None:
    result = service.retrieve("女性", set(), k=20)
    if result["candidates"]:
        raise AssertionError("空白名单必须返回空候选")


def contract_partial_eligible(service: RetrieveService, visible: set[int]) -> None:
    result = service.retrieve("行外资产", visible, k=20)
    for item in result["candidates"]:
        tag_id = int((item.get("doc") or {}).get("tag_id") or -1)
        if tag_id > 0 and tag_id not in visible:
            raise AssertionError("越权引用必须为 0")


def contract_cross_bucket() -> None:
    codes = [{"code": "03", "lower_bound": 1_000_000, "upper_bound": 3_000_000, "lower_inclusive": 1, "upper_inclusive": 0}]
    check = interval_covers(codes, 1_000_000, None, ">")
    if check["expressible"]:
        raise AssertionError("超过100万不得用 100万(含) 档近似")


def snapshot_coverage(published_tags: int, reviewed: int, draft: int = 0) -> dict:
    return coverage_report(published_tags=published_tags, reviewed=reviewed, draft=draft)
