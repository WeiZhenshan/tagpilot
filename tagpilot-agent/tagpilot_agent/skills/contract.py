"""Skill 执行契约：上下文与产出对象。

执行器只依赖本模块与 metrics / insight / chartspec：
输入是已经过权限与数据就绪检查的确定性数据，输出是指标、证据、洞察卡与图表规范。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tagpilot_agent.skills.chartspec import ChartSpec
from tagpilot_agent.skills.insight import Evidence, InsightCard
from tagpilot_agent.skills.manifest import SkillManifest


@dataclass
class SkillContext:
    manifest: SkillManifest
    audience_id: str
    audience_name: str
    as_of_date: str
    benchmark_type: str
    benchmark_name: str
    benchmark_id: str
    trace_id: str
    params: dict = field(default_factory=dict)
    audience_rows: list[dict] = field(default_factory=list)
    benchmark_rows: list[dict] = field(default_factory=list)

    @property
    def audience_count(self) -> int:
        return len(self.audience_rows)

    @property
    def benchmark_count(self) -> int:
        return len(self.benchmark_rows)

    def param_int(self, key: str, default: int) -> int:
        try:
            return int(self.params.get(key, default))
        except (TypeError, ValueError):
            return default

    def param_float(self, key: str, default: float) -> float:
        try:
            return float(self.params.get(key, default))
        except (TypeError, ValueError):
            return default


@dataclass
class SkillOutcome:
    metrics: dict[str, dict] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    insight_cards: list[InsightCard] = field(default_factory=list)
    charts: list[ChartSpec] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    # 图表数据对账：chart_id -> {metric_id: 期望合计}（仅当该图表 rows 确实是对指标的完整分组时声明）
    chart_expectations: dict[str, dict[str, float]] = field(default_factory=dict)
    payload: dict = field(default_factory=dict)

    def expect(self, chart: ChartSpec, metric_id: str, expected: float) -> ChartSpec:
        """声明“该图表的 rows 在 metric_id 维度上应合计等于 expected”，供对账校验使用。"""
        self.chart_expectations.setdefault(chart.chart_id, {})[metric_id] = float(expected)
        return chart

    def add_metric(
        self,
        metric_id: str,
        value,
        unit: str = "",
        numerator: str = "",
        denominator: str = "",
        dimensions: list[str] | None = None,
    ) -> dict:
        from tagpilot_agent.skills.metrics import metric

        entry = metric(
            {
                "metric_id": metric_id,
                "value": value,
                "unit": unit,
                "numerator": numerator,
                "denominator": denominator,
                "dimensions": dimensions or [],
            }
        )
        self.metrics[metric_id] = entry
        return entry

    def value_of(self, metric_id: str, default=0):
        entry = self.metrics.get(metric_id)
        return entry["value"] if entry else default


class SkillBlocked(Exception):
    """Skill 因权限、数据就绪或样本量不足而阻止执行（对齐方案 4.7 与 4.13）。"""

    def __init__(
        self,
        reason: str,
        code: str = "data_not_ready",
        status_code: int = 422,
        validations: list | None = None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.status_code = status_code
        self.validations = validations or []
