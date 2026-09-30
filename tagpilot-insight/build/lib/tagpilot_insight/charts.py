"""聚合事实 → DataProfile → 意图 → 白名单 ChartSpec；不做任何客户查询。"""
from __future__ import annotations

from collections.abc import Mapping

from .contracts import ChartSeries, Fact, InsightChartSpec, Reconcile
from .guards import validate_chart
from .registry import DASHBOARDS, INTENTS


def data_profile(series: list[ChartSeries], facts: Mapping[str, Fact]) -> dict:
    return {"categories": len({p.category for s in series for p in s.points}),
            "series": len(series), "has_matrix": any(p.column for s in series for p in s.points),
            "suppressed": sum(facts[p.fact_id].status != "AVAILABLE" for s in series for p in s.points),
            "units": sorted({facts[p.fact_id].unit for s in series for p in s.points})}


def select_chart(intent: str, profile: dict) -> str:
    if intent not in INTENTS:
        raise ValueError("图表意图未登记")
    if profile["categories"] > 12 or len(profile["units"]) != 1:
        raise ValueError("请先统一口径或聚合类别；选图不能改数据")
    if intent == "show_matrix" and not profile["has_matrix"]:
        raise ValueError("矩阵意图缺少列维度")
    return INTENTS[intent]


def compose_chart(*, chart_id: str, title: str, intent: str, metric_label: str,
                  series: list[ChartSeries], facts: Mapping[str, Fact], reconcile: list[Reconcile] | None = None,
                  as_table: bool = False) -> InsightChartSpec:
    profile = data_profile(series, facts)
    kind = select_chart(intent, profile)
    spec = InsightChartSpec(id=chart_id, title=title, kind="table" if as_table else kind,
                            intent=intent, metric_label=metric_label, unit=profile["units"][0],
                            series=series, reconcile=reconcile or [])
    validate_chart(spec, facts)
    return spec


def compose_dashboard(composition_id: str, specs: list[InsightChartSpec], facts: Mapping[str, Fact], *, partial: bool = False) -> list[InsightChartSpec]:
    """按登记的图表意图排序并校验默认仪表板；不增删或重算事实。"""
    if composition_id not in DASHBOARDS:
        raise ValueError("仪表板编排未登记")
    order = DASHBOARDS[composition_id]
    intents = {"table" if spec.kind == "table" else spec.intent for spec in specs}
    if not intents <= set(order) or (not partial and intents != set(order)) or len({spec.id for spec in specs}) != len(specs):
        raise ValueError("仪表板缺少必需意图、包含未登记意图或重复图表")
    for spec in specs:
        validate_chart(spec, facts)
    return [spec.model_copy(deep=True) for spec in sorted(specs, key=lambda s: order.index("table" if s.kind == "table" else s.intent))]
