"""内置业务 Skill 的 Manifest 与执行器注册。

三个核心 Skill（对齐方案 4.5 / 7.4）：
  1. audience_asset_structure      客群资产结构透视（L1 事实）
  2. product_holding_gap           产品持仓缺口诊断（L2 诊断）
  3. marketing_opportunity_priority 营销机会优先级排序（L3 行动）
"""

from __future__ import annotations

from tagpilot_agent.skills.builtins import asset_structure, opportunity_priority, product_gap
from tagpilot_agent.skills.manifest import ExecutorSpec, Preconditions, SkillManifest, VisualizationSpec

MANIFESTS: tuple[SkillManifest, ...] = (
    SkillManifest(
        skill_id="audience_asset_structure",
        version="1.0.0",
        name="客群资产结构透视",
        category="fact",
        layer="L1",
        owner="零售金融部",
        status="draft",
        description="回答这群客户是什么样：规模、AUM 总量与分层、九类产品持有结构、活期沉淀与渠道可达性。",
        applicable_objects=["personal_customer_audience"],
        scenario_packs=["large_inflow_conversion", "dormant_reactivation"],
        required_inputs=["audience_id", "as_of_date", "benchmark_type"],
        required_metrics=[
            "customer_count",
            "total_aum",
            "avg_aum",
            "median_aum",
            "aum_band_share",
            "product_holding_rate",
            "product_coverage_avg",
            "liquid_heavy_share",
            "channel_reachable_rate",
        ],
        preconditions=Preconditions(
            min_customer_count=20,
            max_data_age_days=2,
            required_permissions=["audience:read", "insight:asset_structure"],
        ),
        executor=ExecutorSpec(type="builtin", operation="audience_asset_structure", timeout_seconds=30),
        output_schema="AssetStructureResultV1",
        default_benchmark="ALL_BRANCH",
        allowed_benchmarks=["ALL_BRANCH", "SAME_AUM_BAND", "SAME_RISK_LEVEL"],
        visualizations=[
            VisualizationSpec(chart_skill="chart.compose.audience_overview", preferred_mark="kpi"),
            VisualizationSpec(chart_skill="chart.intent.show_composition", preferred_mark="stacked_bar"),
            VisualizationSpec(chart_skill="chart.intent.compare_categories", preferred_mark="bar"),
        ],
        validators=[
            "metric_reconciliation",
            "small_sample_suppression",
            "evidence_completeness",
            "chart_spec_validation",
            "accessibility_validation",
        ],
        evaluation_suite="asset_structure_eval_v1",
        human_review_required=False,
    ),
    SkillManifest(
        skill_id="product_holding_gap",
        version="1.0.0",
        name="产品持仓缺口诊断",
        category="diagnostic",
        layer="L2",
        owner="零售金融部",
        status="draft",
        description="与同价值、同风险层级客户基准比较，识别明显低配或空白的产品类别，并在风险适配与排除规则校验后给出机会客户范围。",
        applicable_objects=["personal_customer_audience"],
        scenario_packs=["large_inflow_conversion"],
        required_inputs=["audience_id", "as_of_date", "benchmark_type"],
        required_metrics=[
            "customer_count",
            "aum_band_share",
            "product_holding_rate",
            "product_gap_rate",
            "opportunity_customer_count",
            "risk_unsuitable_share",
            "excluded_customer_share",
        ],
        preconditions=Preconditions(
            min_customer_count=20,
            max_data_age_days=2,
            required_permissions=["audience:read", "insight:product_gap"],
        ),
        executor=ExecutorSpec(type="builtin", operation="product_holding_gap", timeout_seconds=30),
        output_schema="ProductHoldingGapResultV1",
        default_benchmark="SAME_AUM_BAND",
        allowed_benchmarks=["ALL_BRANCH", "SAME_AUM_BAND", "SAME_RISK_LEVEL"],
        visualizations=[
            VisualizationSpec(chart_skill="chart.intent.compare_categories", preferred_mark="bar"),
            VisualizationSpec(chart_skill="chart.intent.show_composition", preferred_mark="heatmap"),
            VisualizationSpec(chart_skill="chart.compose.product_gap", preferred_mark="table"),
        ],
        validators=[
            "metric_reconciliation",
            "small_sample_suppression",
            "risk_suitability_check",
            "exclusion_rule_check",
            "evidence_completeness",
            "chart_spec_validation",
            "accessibility_validation",
        ],
        evaluation_suite="product_holding_gap_eval_v1",
        human_review_required=False,
    ),
    SkillManifest(
        skill_id="marketing_opportunity_priority",
        version="1.0.0",
        name="营销机会优先级排序",
        category="action",
        layer="L3",
        owner="零售金融部",
        status="draft",
        description="用可解释加权规则把客群分入高/中/低三档机会，给出入档原因、建议渠道与排除原因，形成可落地的触达优先级。",
        applicable_objects=["personal_customer_audience"],
        scenario_packs=["large_inflow_conversion", "dormant_reactivation"],
        required_inputs=["audience_id", "as_of_date", "benchmark_type"],
        required_metrics=[
            "customer_count",
            "opportunity_customer_count",
            "high_priority_opportunity_count",
            "channel_reachable_rate",
        ],
        preconditions=Preconditions(
            min_customer_count=20,
            max_data_age_days=2,
            required_permissions=["audience:read", "insight:opportunity_priority"],
        ),
        executor=ExecutorSpec(type="builtin", operation="marketing_opportunity_priority", timeout_seconds=45),
        output_schema="MarketingOpportunityResultV1",
        default_benchmark="ALL_BRANCH",
        allowed_benchmarks=["ALL_BRANCH", "SAME_AUM_BAND", "SAME_RISK_LEVEL"],
        visualizations=[
            VisualizationSpec(chart_skill="chart.intent.show_conversion", preferred_mark="funnel"),
            VisualizationSpec(chart_skill="chart.compose.marketing_funnel", preferred_mark="bar"),
            VisualizationSpec(chart_skill="chart.intent.show_ranking", preferred_mark="table"),
        ],
        validators=[
            "metric_reconciliation",
            "small_sample_suppression",
            "risk_suitability_check",
            "exclusion_rule_check",
            "evidence_completeness",
            "chart_spec_validation",
            "accessibility_validation",
        ],
        evaluation_suite="marketing_opportunity_eval_v1",
        human_review_required=True,
    ),
)

EXECUTORS = {
    "audience_asset_structure": asset_structure.run,
    "product_holding_gap": product_gap.run,
    "marketing_opportunity_priority": opportunity_priority.run,
}


def register_builtin_skills(registry) -> list[str]:
    """把三个内置 Skill 注册进注册表；返回注册成功的 skill_id 列表。"""
    registered: list[str] = []
    for manifest in MANIFESTS:
        executor = EXECUTORS.get(manifest.executor.operation)
        if executor is None:
            continue
        try:
            registry.register(manifest, executor)
            registered.append(manifest.skill_id)
        except Exception:  # 已注册（例如热重载）时跳过，不阻断启动
            continue
    return registered
