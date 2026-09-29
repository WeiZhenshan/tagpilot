"""P0 共享协议。所有模型拒绝额外字段；不提供 SQL、明细或任意 ECharts option。"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")]
Version = Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=500)]
Number = Annotated[float, Field(allow_inf_nan=False, strict=True)]
Unit = Literal["人", "元", "%", "pp", "分"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CohortSnapshot(Contract):
    audience_id: Text
    audience_name: Text
    library_id: int = Field(gt=0)
    revision: int = Field(ge=1)
    plan_hash: Hash
    snapshot_id: Text
    count: int = Field(ge=0)
    data_as_of: date
    # Java 注入的运行日期；不允许用模型猜测当前日期。
    reference_date: date
    binding_version: Version
    declared_context: str = Field(default="", max_length=2000)
    synthetic: bool = False


class InputSpec(Contract):
    type: Literal["integer", "number", "enum", "string_list"]
    default: int | float | str | list[str]
    minimum: Number | None = None
    maximum: Number | None = None
    choices: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def default_valid(self):
        if self.type == "enum" and self.default not in self.choices:
            raise ValueError("默认值不属于枚举")
        if self.type in {"integer", "number"}:
            if isinstance(self.default, bool) or not isinstance(self.default, (int, float)):
                raise ValueError("数值默认值非法")
            if self.type == "integer" and not isinstance(self.default, int):
                raise ValueError("整数默认值非法")
            if self.minimum is not None and self.default < self.minimum:
                raise ValueError("默认值低于范围")
            if self.maximum is not None and self.default > self.maximum:
                raise ValueError("默认值高于范围")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("参数范围颠倒")
        if self.type == "string_list" and not isinstance(self.default, list):
            raise ValueError("列表默认值非法")
        return self


class Preconditions(Contract):
    min_sample: int = Field(default=20, ge=20)
    max_stale_days: int = Field(default=2, ge=0, le=30)
    suppression_threshold: int = Field(default=20, ge=20)
    dependencies: list[Identifier] = Field(min_length=1, max_length=40)


class QueryBase(Contract):
    id: Identifier
    population: Literal["cohort", "benchmark"] = "cohort"
    dimensions: list[Identifier] = Field(default_factory=list, max_length=2)


class AggregateQuery(QueryBase):
    node: Literal["aggregate"]
    metric: Identifier
    operation: Literal["count", "sum", "avg", "median", "percentile"]
    percentile: Number | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def percentile_required(self):
        if (self.operation == "percentile") != (self.percentile is not None):
            raise ValueError("percentile 仅用于百分位聚合且必须提供")
        return self


class BandQuery(QueryBase):
    node: Literal["band"]
    metric: Identifier
    cuts: list[Number] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def ordered(self):
        if self.cuts != sorted(set(self.cuts)):
            raise ValueError("分箱边界必须严格递增")
        return self


class FlagRateQuery(QueryBase):
    node: Literal["flag_rate"]
    metric: Identifier
    # 机会计算中的治理条件由 Java 编译；不能提交任意 SQL。
    exclusions: list[Identifier] = Field(default_factory=list, max_length=8)
    suitability_category: Identifier | None = None


class ScoreBand(Contract):
    upper: Number | None
    points: Number = Field(ge=-100, le=100)


class ScoreComponent(Contract):
    metric: Identifier
    weight: Number = Field(gt=0, le=100)
    bands: list[ScoreBand] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def ordered(self):
        cuts = [b.upper for b in self.bands[:-1]]
        if any(c is None for c in cuts) or cuts != sorted(set(cuts)) or self.bands[-1].upper is not None:
            raise ValueError("评分分档必须递增，以无上限档结束")
        return self


class ScoreQuery(QueryBase):
    node: Literal["score"]
    profile: Identifier
    assumption: Literal[True]
    exclusions: list[Identifier] = Field(min_length=4, max_length=8)
    components: list[ScoreComponent] = Field(min_length=1, max_length=8)
    tier_cuts: list[Number] = Field(min_length=2, max_length=2)
    reason_top_k: Literal[2] = 2

    @model_validator(mode="after")
    def ordered(self):
        if self.tier_cuts != sorted(set(self.tier_cuts)):
            raise ValueError("评分层级边界必须严格递增")
        required = {"risk_mismatch", "do_not_disturb", "recent_contact", "no_channel"}
        if not required <= set(self.exclusions):
            raise ValueError("评分必须先执行全部硬排除")
        return self


MetricQuery = Annotated[AggregateQuery | BandQuery | FlagRateQuery | ScoreQuery, Field(discriminator="node")]


class MetricBinding(Contract):
    metric: Identifier
    version: Version
    category: Identifier | None = None
    tag_id: int = Field(gt=0)
    snapshot_id: Text
    unit: Unit
    # v1 首先绑定已发布标签，不允许浏览器传入表名、列名或 SQL。
    status: Literal["DRAFT", "REVIEWED", "PUBLISHED", "RETIRED"] = "DRAFT"


class FindingRule(Contract):
    id: Identifier
    basis: Literal["RULE", "STAT", "HYPOTHESIS"]
    description: Text
    min_comparison_sample: int = Field(default=30, ge=30)
    threshold_parameter: Identifier | None = None
    requires_nonoverlapping_ci: bool = False


class CardTemplate(Contract):
    facts: Text
    comparison: Text
    diagnosis: Text
    action: Text
    boundary: Text


class Manifest(Contract):
    id: Identifier
    name: Text
    version: Version
    layer: Literal["L1", "L2", "L3"]
    owner: Text
    status: Literal["DRAFT", "REVIEWED", "PUBLISHED", "RETIRED"]
    question: Text
    applicable_objects: list[Literal["personal_customer_audience"]] = Field(default_factory=lambda: ["personal_customer_audience"])
    scenarios: list[Identifier] = Field(default_factory=lambda: ["large_inflow_conversion"])
    required_permissions: list[Text] = Field(default_factory=lambda: ["taglibrary:insight:run"])
    executor: Literal["java_aggregate_python_compose"] = "java_aggregate_python_compose"
    output_schema: Literal["InsightReportV1"] = "InsightReportV1"
    validators: list[Identifier] = Field(default_factory=lambda: ["metric_reconciliation","small_sample_suppression","evidence_completeness","chart_spec_validation"])
    inputs: dict[Identifier, InputSpec]
    metrics: list[Identifier] = Field(min_length=1, max_length=40)
    preconditions: Preconditions
    queries: list[MetricQuery] = Field(min_length=1, max_length=40)
    findings: list[FindingRule] = Field(min_length=1, max_length=10)
    card_templates: list[CardTemplate] = Field(min_length=1, max_length=10)
    dashboard: Literal["compose.audience_overview", "compose.product_gap", "compose.opportunity_board"]
    blocks: dict[Identifier, Text]
    fixtures: list[str] = Field(min_length=1, max_length=10)
    eval: dict[Identifier, Text]

    @model_validator(mode="after")
    def declared_metrics(self):
        if len(set(self.metrics)) != len(self.metrics) or len({q.id for q in self.queries}) != len(self.queries):
            raise ValueError("指标或查询标识重复")
        if not set(self.preconditions.dependencies) <= set(self.metrics):
            raise ValueError("前置依赖必须是已声明指标")
        for query in self.queries:
            used = {query.metric} if not isinstance(query, ScoreQuery) else {c.metric for c in query.components}
            if not used <= set(self.metrics) or not set(query.dimensions) <= set(self.metrics):
                raise ValueError("查询使用未声明指标")
        return self


class Fact(Contract):
    id: Identifier
    metric: Identifier
    label: Text
    value: Number | None
    unit: Unit
    sample_size: int | None = Field(default=None, ge=0)
    status: Literal["AVAILABLE", "SUPPRESSED", "MISSING"] = "AVAILABLE"
    query_id: Identifier
    evidence: list[Text] = Field(min_length=1, max_length=10)
    denominator_id: Identifier | None = None
    derived_from: list[Identifier] = Field(default_factory=list, max_length=50)
    role: Literal["OBSERVED", "BENCHMARK", "POST_EXCLUSION", "DERIVED"] = "OBSERVED"
    exclusions_applied: list[Identifier] = Field(default_factory=list, max_length=8)
    calculation: Literal["DIRECT", "RATIO", "WEIGHTED"] = "DIRECT"
    weights: dict[Identifier, Number] = Field(default_factory=dict, max_length=144)

    @model_validator(mode="after")
    def availability(self):
        if self.status == "AVAILABLE" and (self.value is None or self.sample_size is None):
            raise ValueError("可用事实必须有数值及样本量")
        if self.status != "AVAILABLE" and (self.value is not None or self.sample_size is not None):
            raise ValueError("缺失或抑制事实不得携带数值或精确小样本量")
        if self.role == "POST_EXCLUSION" and not self.exclusions_applied:
            raise ValueError("行动事实必须记录排除规则")
        return self


class Statement(Contract):
    # 数字用 {fact:xxx} 引用，禁止模型自由生成数字。
    text: Text
    fact_ids: list[Identifier] = Field(default_factory=list, max_length=20)


class Comparison(Statement):
    benchmark_fact_ids: list[Identifier] = Field(default_factory=list, max_length=10)
    difference_fact_ids: list[Identifier] = Field(default_factory=list, max_length=10)


class StatisticalEvidence(Contract):
    method: Literal["wilson_bonferroni"] = "wilson_bonferroni"
    cohort_rate_id: Identifier
    benchmark_rate_id: Identifier
    cohort_interval: tuple[Number, Number]
    benchmark_interval: tuple[Number, Number]
    threshold_pp: Number = Field(ge=0, le=100)


class Diagnosis(Statement):
    basis: Literal["RULE", "STAT", "HYPOTHESIS"]
    statistical_evidence: StatisticalEvidence | None = None


class Action(Statement):
    population_fact_id: Identifier | None = None
    priority: Literal["HIGH", "MEDIUM", "LOW", "NONE"] = "NONE"


class EvidenceBoundary(Contract):
    text: Text
    data_as_of: date
    skill_version: Version
    sample_fact_id: Identifier
    metric_definitions: list[Text] = Field(min_length=1, max_length=20)


class InsightCard(Contract):
    id: Identifier
    title: Text
    facts: Statement
    comparison: Comparison
    diagnosis: Diagnosis
    action: Action
    boundary: EvidenceBoundary


ChartKind = Literal["kpi", "table", "bar", "stacked_bar", "heatmap", "funnel"]
ChartIntent = Literal["single_value", "compare_categories", "show_composition", "show_distribution", "show_matrix", "show_conversion"]


class ChartPoint(Contract):
    category: Annotated[str, Field(min_length=1, max_length=24)]
    fact_id: Identifier
    value: Number | None
    column: Annotated[str, Field(min_length=1, max_length=24)] | None = None


class ChartSeries(Contract):
    name: Annotated[str, Field(min_length=1, max_length=24)]
    fact_ids: list[Identifier] = Field(min_length=1, max_length=100)
    points: list[ChartPoint] = Field(min_length=1, max_length=100)


class Annotation(Contract):
    text: Text
    fact_ids: list[Identifier] = Field(min_length=1, max_length=10)


class Reconcile(Contract):
    kind: Literal["sum", "percentage", "funnel"]
    fact_ids: list[Identifier] = Field(min_length=1, max_length=100)
    total_fact_id: Identifier | None = None
    # pp 合计仅允许舍入误差，不能由模型扩大容差。
    tolerance: Number = Field(default=0.01, ge=0, le=0.05)


class InsightChartSpec(Contract):
    schema_version: Literal[1] = 1
    id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=80)]
    kind: ChartKind
    intent: ChartIntent
    unit: Unit
    metric_label: Annotated[str, Field(min_length=1, max_length=40)]
    series: list[ChartSeries] = Field(min_length=1, max_length=8)
    annotations: list[Annotation] = Field(default_factory=list, max_length=8)
    reconcile: list[Reconcile] = Field(default_factory=list, max_length=12)
    zero_baseline: Literal[True] = True
    orientation: Literal["horizontal", "vertical"] = "horizontal"


class SkillResult(Contract):
    registry_version: Version | None = None
    definition_hash: Hash | None = None
    skill_id: Identifier
    skill_version: Version
    pack_hash: Hash
    status: Literal["COMPLETE", "PARTIAL", "BLOCKED"]
    level: Literal["L2", "L3", "L4"] | None = None
    reasons: list[Text] = Field(default_factory=list, max_length=10)
    facts: list[Fact] = Field(default_factory=list, max_length=300)
    cards: list[InsightCard] = Field(default_factory=list, max_length=20)
    charts: list[InsightChartSpec] = Field(default_factory=list, max_length=30)


class InsightReport(Contract):
    level: Literal["L2", "L3", "L4"] | None = None
    schema_version: Literal[1] = 1
    run_id: Text
    cohort: CohortSnapshot
    results: list[SkillResult] = Field(min_length=1, max_length=3)

    def is_stale(self, revision: int, plan_hash: str) -> bool:
        return self.cohort.revision != revision or self.cohort.plan_hash != plan_hash
