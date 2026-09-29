"""Skill 引擎回归测试：Manifest 契约、注册表生命周期、受控执行链与三个核心 Skill 的数值对账。

不依赖数据库：用 FakeSource 提供确定性数据，期望值在测试内手算。
数据库可用时额外跑一条真实链路冒烟测试。
"""

import pytest

from tagpilot_agent.skills.builtins import MANIFESTS, register_builtin_skills
from tagpilot_agent.skills.chartspec import ChartField, ChartProvenance, ChartSpec, ChartView, validate_chart_spec
from tagpilot_agent.skills.contract import SkillBlocked
from tagpilot_agent.skills.datasource import SkillDataNotReady
from tagpilot_agent.skills.manifest import (
    ExecutorSpec,
    Preconditions,
    SkillManifest,
    VisualizationSpec,
    validate_manifest,
)
from tagpilot_agent.skills.registry import SkillRegistry, SkillRegistryError
from tagpilot_agent.skills.runtime import SkillRuntime

PERMISSIONS = [
    "audience:read",
    "insight:asset_structure",
    "insight:product_gap",
    "insight:opportunity_priority",
]


def _customer(index, *, aum_level, aum, wealth, risk, blacklist=0, channel="线上"):
    return {
        "cust_id": f"C{index:05d}",
        "aum_balance": aum,
        "aum_level": aum_level,
        "avg_daily_deposit": aum * 0.85,
        "contribution_score": 60,
        "clv_score": 70,
        "cross_sell_index": 55,
        "has_deposit": 1,
        "has_wealth": wealth,
        "has_fund": 0,
        "has_insurance": 0,
        "has_credit_card": 1,
        "has_loan": 0,
        "has_forex": 0,
        "has_precious_metal": 0,
        "has_trust": 0,
        "total_products_count": 3 if wealth else 2,
        "risk_rating": risk,
        "risk_tolerance": "稳健型" if risk == "R2" else "进取型",
        "channel_preference": channel,
        "is_mobile_banking_user": 1,
        "is_online_banking_user": 0,
        "is_wechat_banking_user": 0,
        "transaction_frequency_monthly": 6,
        "transaction_amt_monthly": 20000 + index * 10,
        "online_login_freq_monthly": 8,
        "counter_visit_freq_quarterly": 1,
        "is_active_cust": 1,
        "is_salary_cust": 0,
        "cust_segment": "富裕",
        "branch_code": "B001" if index % 2 else "B002",
        "region": "华东",
        "age": 35,
        "age_group": "30-39",
        "occupation_type": "白领",
        "city_tier": 1,
        "annual_income_k": 300.0,
        "loyalty_years": 5.0,
        "loyalty_level": "中",
        "contribution_level": "中",
        "blacklist_flag": blacklist,
        "fraud_alert_flag": 0,
        "kyc_status": "完整",
        "last_transaction_date": "2026-09-20",
    }


def _audience_rows():
    """40 位客户：30 位 10-50万层级、10 位 100万以上；8 位持有理财；2 位黑名单。"""
    rows = []
    for index in range(1, 41):
        top = index > 30
        rows.append(
            _customer(
                index,
                aum_level="100万以上" if top else "10-50万",
                aum=1_200_000 if top else 10_000,
                wealth=1 if index <= 8 else 0,
                risk="R5" if top else "R2",
                blacklist=1 if index in {9, 10} else 0,
            )
        )
    return rows


def _benchmark_rows():
    """60 位基准客户：30 位持有理财（50%），全部 10-50万层级。"""
    return [
        _customer(
            1000 + index,
            aum_level="10-50万",
            aum=20_000,
            wealth=1 if index <= 30 else 0,
            risk="R2",
        )
        for index in range(1, 61)
    ]


class FakeSource:
    """确定性数据源：audience / scope 由测试提供。"""

    def __init__(self, audience=None, scope=None, as_of="2026-09-24"):
        self._audience = audience if audience is not None else _audience_rows()
        self._scope = scope if scope is not None else _benchmark_rows()
        self._as_of = as_of

    def fetch_audience(self, member_ids):
        wanted = {str(item) for item in member_ids}
        return [row for row in self._audience if row["cust_id"] in wanted]

    def count_audience(self, member_ids):
        return len(self.fetch_audience(member_ids))

    def fetch_scope(self, benchmark_type, audience_rows):
        return list(self._scope)

    def data_as_of(self):
        return self._as_of


def _runtime(source=None, path=None):
    registry = SkillRegistry(storage_path=path or ":memory:")
    register_builtin_skills(registry)
    for manifest in MANIFESTS:
        registry.transition(manifest.skill_id, manifest.version, "publish", operator_name="tester")
    return SkillRuntime(registry, source or FakeSource())


def _run_request(member_ids=None, **overrides):
    if member_ids is None:
        member_ids = [row["cust_id"] for row in _audience_rows()]
    payload = {
        "audience_id": "12",
        "audience_name": "大额入金未持有理财",
        "member_ids": member_ids,
        "as_of_date": "2026-09-24",
        "operator_id": "1",
        "operator_name": "admin",
        "permissions": list(PERMISSIONS),
        "trace_id": "trace-test",
    }
    payload.update(overrides)
    return payload


# ---------- Manifest 契约 ----------

def test_manifest_rejects_missing_evidence_validator():
    manifest = MANIFESTS[0].model_copy(deep=True)
    manifest.validators = ["metric_reconciliation", "small_sample_suppression"]
    errors, _ = validate_manifest(manifest)
    assert any("evidence_completeness" in item for item in errors)


def test_manifest_rejects_unknown_chart_skill_and_l3_without_risk_check():
    manifest = MANIFESTS[1].model_copy(deep=True)
    manifest.visualizations = [VisualizationSpec(chart_skill="chart.intent.show_magic", preferred_mark="bar")]
    manifest.validators = ["metric_reconciliation", "small_sample_suppression", "evidence_completeness"]
    errors, _ = validate_manifest(manifest)
    assert any("图表 Skill" in item for item in errors)

    l3 = MANIFESTS[2].model_copy(deep=True)
    l3.validators = ["metric_reconciliation", "small_sample_suppression", "evidence_completeness"]
    errors, _ = validate_manifest(l3)
    assert any("risk_suitability_check" in item for item in errors)


def test_manifest_default_benchmark_must_be_allowed():
    manifest = MANIFESTS[0].model_copy(deep=True)
    manifest.default_benchmark = "SAME_RISK_LEVEL"
    manifest.allowed_benchmarks = ["ALL_BRANCH"]
    errors, _ = validate_manifest(manifest)
    assert any("default_benchmark" in item for item in errors)


def test_three_core_skills_declare_required_contract_fields():
    assert [item.skill_id for item in MANIFESTS] == [
        "audience_asset_structure",
        "product_holding_gap",
        "marketing_opportunity_priority",
    ]
    for manifest in MANIFESTS:
        errors, _ = validate_manifest(manifest)
        assert errors == []
        assert manifest.preconditions.required_permissions
        assert manifest.evaluation_suite.endswith("_eval_v1")


# ---------- 注册表生命周期与权限 ----------

def test_registry_lifecycle_and_illegal_transition(tmp_path):
    registry = SkillRegistry(storage_path=str(tmp_path / "reg.sqlite"))
    register_builtin_skills(registry)
    assert registry.effective_manifest("product_holding_gap").status == "draft"

    with pytest.raises(SkillRegistryError):
        registry.transition("product_holding_gap", "1.0.0", "offline", operator_name="tester")

    published = registry.transition("product_holding_gap", "1.0.0", "publish", operator_name="tester", reason="验收通过")
    assert published["status"] == "published"
    assert "manifest_valid" in published["gate"]

    offline = registry.transition("product_holding_gap", "1.0.0", "offline", operator_name="tester", reason="例行下线")
    assert offline["status"] == "offline"
    versions = registry.versions("product_holding_gap")
    assert versions[0]["status"] == "offline"
    assert len(registry.lifecycle("product_holding_gap")) == 2


def test_registry_permission_filter(tmp_path):
    registry = SkillRegistry(storage_path=str(tmp_path / "reg.sqlite"))
    register_builtin_skills(registry)
    visible = registry.list_skills(permissions=["audience:read", "insight:asset_structure"])
    assert [item["skill_id"] for item in visible] == ["audience_asset_structure"]
    assert len(registry.list_skills(permissions=["*"])) == 3


def test_recommend_returns_scenario_pack(tmp_path):
    registry = SkillRegistry(storage_path=str(tmp_path / "reg.sqlite"))
    register_builtin_skills(registry)
    pack = registry.recommend(permissions=["*"])
    assert pack["scenario_pack"]["id"] == "large_inflow_conversion"
    assert len(pack["skills"]) == 3


# ---------- 受控执行链 ----------

def test_run_blocked_when_skill_not_published(tmp_path):
    registry = SkillRegistry(storage_path=str(tmp_path / "reg.sqlite"))
    register_builtin_skills(registry)
    runtime = SkillRuntime(registry, FakeSource())
    with pytest.raises(SkillBlocked) as info:
        runtime.run("product_holding_gap", _run_request())
    assert info.value.status_code == 409
    assert "未发布" in info.value.reason


def test_run_blocked_without_permission(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    with pytest.raises(SkillBlocked) as info:
        runtime.run("product_holding_gap", _run_request(permissions=["audience:read"]))
    assert info.value.status_code == 403
    assert "insight:product_gap" in info.value.reason


def test_run_blocked_on_small_sample(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    members = [row["cust_id"] for row in _audience_rows()][:10]
    with pytest.raises(SkillBlocked) as info:
        runtime.run("audience_asset_structure", _run_request(member_ids=members))
    assert info.value.status_code == 422
    assert "最小样本阈值" in info.value.reason


def test_run_blocked_on_empty_members(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    with pytest.raises(SkillBlocked) as info:
        runtime.run("audience_asset_structure", _run_request(member_ids=[]))
    assert "成员为空" in info.value.reason


def test_run_blocked_on_unknown_benchmark(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    with pytest.raises(SkillBlocked) as info:
        runtime.run("audience_asset_structure", _run_request(benchmark_type="SAME_CITY"))
    assert "基准类型不合法" in info.value.reason


# ---------- Skill A：客群资产结构透视 ----------

def test_asset_structure_metrics_reconcile(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    result = runtime.run("audience_asset_structure", _run_request())

    assert result["status"] == "succeeded"
    metrics = result["metrics"]
    assert metrics["customer_count"]["value"] == 40
    assert metrics["total_aum"]["value"] == 30 * 10_000 + 10 * 1_200_000
    assert metrics["avg_aum"]["value"] == pytest.approx((30 * 10_000 + 10 * 1_200_000) / 40, abs=0.01)
    assert metrics["median_aum"]["value"] == pytest.approx(10_000.0, abs=0.01)
    # 理财产品持有率 8/40
    assert metrics["wealth_product_holding_rate"]["value"] == 20.0
    # 活期占比 = 日均存款/AUM = 85% > 70%，全部 40 人
    assert metrics["liquid_heavy_share"]["value"] == 100.0

    checks = {item["name"]: item["passed"] for item in result["validations"]}
    assert checks["metric_reconciliation"] is True
    assert checks["evidence_completeness"] is True
    assert checks["chart_spec_validation"] is True
    assert checks["accessibility_validation"] is True
    assert all(item["passed"] for item in result["chart_validations"])
    assert result["audience"]["benchmark_customer_count"] == 60
    assert len(result["insight_cards"]) == 4


# ---------- Skill B：产品持仓缺口诊断 ----------

def test_product_gap_uses_benchmark_and_suitability(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    result = runtime.run("product_holding_gap", _run_request(benchmark_type="SAME_AUM_BAND"))

    gaps = {item["product"]: item for item in result["payload"]["gap_ranking"]}
    wealth = gaps["理财"]
    # 目标持有率 20%，基准 50% → 缺口 30 个百分点
    assert wealth["gap_points"] == pytest.approx(30.0, abs=0.01)
    # 未持有且风险适配（理财最低 R1）且未排除：40 - 8 持有 - 2 黑名单 = 30
    assert wealth["opportunity_count"] == 30

    trust = gaps["信托"]
    # 信托最低 R5，10 位 R5 客户全部适配且均未持有
    assert trust["opportunity_count"] == 10

    # 基金最低 R3：只有 10 位 R5 客户适配
    assert gaps["基金"]["opportunity_count"] == 10

    checks = {item["name"]: item["passed"] for item in result["validations"]}
    assert checks["risk_suitability_check"] is True
    assert checks["exclusion_rule_check"] is True
    assert result["metrics"]["excluded_customer_share"]["value"] == 5.0
    assert all(item["passed"] for item in result["chart_validations"])


def test_product_gap_heatmap_suppresses_small_groups(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    result = runtime.run("product_holding_gap", _run_request())
    suppressed = [item for item in result["diagnostics"] if item["code"] == "SMALL_GROUP_SUPPRESSED"]
    messages = [item["message"] for item in suppressed]
    # R5 只有 10 人 < 20，且 R1/R3/R4 为 0 人，热力图须全部抑制；R2 有 30 人，保留
    assert suppressed
    assert any("R5" in m for m in messages)
    assert not any("R2" in m for m in messages)
    assert {row["risk_level"] for row in result["payload"]["heatmap"]} == {"R2"}


# ---------- Skill C：营销机会优先级排序 ----------

def test_opportunity_priority_bands_and_no_customer_list(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    result = runtime.run("marketing_opportunity_priority", _run_request())

    bands = {item["band"]: item["customer_count"] for item in result["payload"]["bands"]}
    # 40 位客户中 2 位命中营销排除规则，机会分层只统计可触达的 38 位
    assert sum(bands.values()) == 38
    assert result["metrics"]["excluded_customer_share"]["value"] == 5.0
    assert result["metrics"]["high_priority_opportunity_count"]["value"] == bands["high"]
    assert result["metrics"]["opportunity_customer_count"]["value"] == bands["high"] + bands["medium"]

    # 名单安全边界：不输出任何客户 ID
    serialized = str(result["payload"])
    assert "C000" not in serialized
    assert result["payload"]["customer_list_policy"].startswith("明细名单由业务服务")

    funnel = next(chart for chart in result["charts"] if chart["view"]["mark"] == "funnel")
    values = [row["customer_count"] for row in funnel["rows"]]
    assert values == sorted(values, reverse=True)
    assert all(item["passed"] for item in result["chart_validations"])


def test_run_records_history(tmp_path):
    runtime = _runtime(path=str(tmp_path / "reg.sqlite"))
    result = runtime.run("audience_asset_structure", _run_request())
    runs = runtime.registry.list_runs(skill_id="audience_asset_structure")
    assert runs and runs[0]["run_id"] == result["run_id"]
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["customer_count"] == 40


# ---------- 图表规范校验器 ----------

def test_chart_validator_rejects_customer_identifiers_and_causality():
    spec = ChartSpec(
        chart_id="CHART_TEST",
        intent="category_comparison",
        chart_skill="chart.intent.compare_categories",
        title="持有率导致业绩提升",
        subtitle="数据截至2026-09-24",
        fields=[
            ChartField(field="product_category", semantic_type="category", role="dimension"),
            ChartField(field="holding_rate", semantic_type="percentage", role="measure", unit="percent"),
        ],
        rows=[{"product_category": "理财", "holding_rate": 20.0, "cust_id": "C00001"}],
        view=ChartView(mark="bar", encoding={"x": "holding_rate", "y": "product_category"}),
        provenance=ChartProvenance(skill_id="x", skill_version="1.0.0"),
    )
    results = {item.name: item for item in validate_chart_spec(spec)}
    assert results["chart_semantic_validation"].passed is False
    assert "cust_id" in results["chart_semantic_validation"].detail or "因果" in results["chart_semantic_validation"].detail


def test_chart_validator_rejects_unknown_mark():
    spec = ChartSpec(
        chart_id="CHART_TEST2",
        intent="category_comparison",
        chart_skill="chart.intent.compare_categories",
        title="测试",
        fields=[ChartField(field="a", semantic_type="category", role="dimension")],
        rows=[{"a": "x"}],
        view=ChartView(mark="pie3d", encoding={"x": "a"}),
        provenance=ChartProvenance(skill_id="x", skill_version="1.0.0"),
    )
    results = {item.name: item for item in validate_chart_spec(spec)}
    assert results["chart_spec_schema"].passed is False


# ---------- 真实数据库冒烟（缺库时自动跳过） ----------

def test_real_database_smoke():
    from tagpilot_agent.skills.datasource import MySqlAudienceSource

    source = MySqlAudienceSource()
    try:
        members = [f"{index:06d}" for index in range(1, 5)]
        source.fetch_audience(members)
    except SkillDataNotReady as exc:
        pytest.skip(f"本地标签宽表不可用：{exc}")
    except Exception as exc:  # 连接层异常同样视为不可用
        pytest.skip(f"指标数据库不可用：{exc}")
