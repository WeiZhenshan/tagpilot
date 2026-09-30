from datetime import date
import json

import pytest
from pydantic import TypeAdapter, ValidationError

from tagpilot_insight.charts import compose_chart, compose_dashboard, data_profile, select_chart
from tagpilot_insight.contracts import Fact, InsightReport, MetricQuery, ScoreQuery, InsightChartSpec
from tagpilot_insight.fixtures import synthetic_golden_report
from tagpilot_insight.guards import GuardError, render_statement, validate_chart, validate_report
from tagpilot_insight.narration import guarded_narration
from tagpilot_insight.registry import ATOMIC_CHARTS, DASHBOARDS, INTENTS, SkillRegistry, canonical_hash
from tagpilot_insight.contracts import MetricBinding
from tagpilot_insight.planning import plan_skill


@pytest.fixture
def report():
    return synthetic_golden_report()


def test_all_three_registered_with_four_query_nodes():
    registry = SkillRegistry()
    assert set(registry.manifests) == {"asset_structure_profile", "product_holding_gap", "opportunity_priority"}
    assert {q.node for m in registry.manifests.values() for q in m.queries} == {"aggregate", "band", "flag_rate", "score"}
    assert all(m.status == "DRAFT" for m in registry.manifests.values())
    assert len(ATOMIC_CHARTS) == len(INTENTS) == 6 and len(DASHBOARDS) == 3
    assert len(set(registry.hashes.values())) == 3
    clone = registry.get("asset_structure_profile")
    clone.version = "9.9.9"
    assert registry.get(clone.id).version == "0.1.0"


def test_fixture_expected_independent_arithmetic(report):
    # 独立手算常量，不能从被测选图/Guard 生成期望。
    asset, gap, priority = [{f.id: f for f in r.facts} for r in report.results]
    assert asset["customers"].value == report.cohort.count == 240
    assert asset["total_aum"].value == 120_000_000
    assert asset["average_aum"].value == 500_000
    assert asset["liquid_share"].value == 60
    assert asset["liquid_gap"].value == 21
    assert sum(asset[k + "_amount"].value for k in ("liquid", "fixed", "investment")) == 120_000_000
    assert gap["wealth_gap"].value == 50
    assert gap["wealth_opportunity"].value == 120
    assert priority["marketable"].value == 180
    assert [priority[k].value for k in ("high", "medium", "low")] == [80, 60, 40]
    assert 20 + 20 + 20 + 0 + priority["marketable"].value == 240
    assert all(r.pack_hash != "0" * 64 for r in report.results)
    validate_report(report)


@pytest.mark.parametrize("patch,code", [
    (lambda r: setattr(r.results[0].facts[0], "value", 241), "FACT_RECONCILIATION"),
    (lambda r: setattr(r.results[0].charts[0].series[0].points[0], "value", 999), "CHART_FACT_MISMATCH"),
    (lambda r: setattr(r.results[0].cards[0].facts, "text", "共有 999 人。"), "UNBOUND_NUMBER"),
    (lambda r: setattr(r.results[0].cards[0].facts, "text", "共有九百人。"), "UNBOUND_NUMBER"),
    (lambda r: setattr(r.results[0].cards[0].comparison, "benchmark_fact_ids", []), "MISSING_BENCHMARK"),
    (lambda r: setattr(r.results[0].cards[0].diagnosis, "text", "入金导致持仓缺口。"), "CAUSAL_LANGUAGE"),
    (lambda r: setattr(r.results[0].cards[0].action, "text", "建议加强营销。"), "VAGUE_ACTION"),
    (lambda r: setattr(r.results[0].cards[0].action, "population_fact_id", "customers"), "INVALID_ACTION_POPULATION"),
    (lambda r: setattr(r.results[0].facts[0], "sample_size", 19), "SMALL_SAMPLE"),
    (lambda r: setattr(r.results[0].facts[0], "value", 19), "SMALL_CELL"),
    (lambda r: setattr(r.results[0], "pack_hash", "b" * 64), "PACK_MISMATCH"),
    (lambda r: setattr(r.cohort, "data_as_of", date(2026, 9, 20)), "STALE_DATA"),
    (lambda r: setattr(r.cohort, "data_as_of", date(2026, 9, 30)), "STALE_DATA"),
    (lambda r: setattr(r.cohort, "synthetic", False), "UNPUBLISHED_SKILL"),
    (lambda r: setattr(r.results[2].cards[0].diagnosis, "text", "价值决定触达顺序。"), "UNLABELED_HYPOTHESIS"),
    (lambda r: setattr(r.results[2].cards[0].boundary, "text", "已经证明此规则可以提升响应。"), "UNCALIBRATED_SCORE"),
    (lambda r: setattr(r.results[0].facts[0], "query_id", "sql_injected"), "UNDECLARED_METRIC"),
    (lambda r: setattr(r.results[0].facts[0], "denominator_id", "customers"), "CYCLIC_FACT"),
])
def test_adversarial_guard(report, patch, code):
    patch(report)
    with pytest.raises(GuardError) as exc:
        validate_report(report)
    assert exc.value.code == code


def test_suppressed_cell_contains_no_value_or_exact_count(report):
    fact = next(f for f in report.results[1].facts if f.id == "sparse_cell")
    assert fact.value is fact.sample_size is None
    for field in ("value", "sample_size"):
        data = fact.model_dump(); data[field] = 12
        with pytest.raises(ValidationError):
            Fact.model_validate(data)


def test_reconciliation_and_percent_denominator(report):
    result = report.results[0]
    facts = {f.id: f for f in result.facts}
    facts["liquid_share"].value = 59
    with pytest.raises(GuardError, match="FACT_RECONCILIATION"):
        validate_report(report)
    facts["liquid_share"].value = 60
    facts["liquid_share"].denominator_id = None
    with pytest.raises(GuardError, match="MISSING_DENOMINATOR"):
        validate_report(report)


def test_funnel_must_be_monotone_and_complete(report):
    result = report.results[1]
    facts = {f.id: f for f in result.facts}
    chart = next(c for c in result.charts if c.kind == "funnel")
    chart.reconcile[0].fact_ids = ["customers", "wealth_opportunity", "wealth_suitable", "wealth_unheld"]
    with pytest.raises(GuardError, match="FUNNEL_ORDER"):
        validate_chart(chart, facts)
    chart.reconcile = []
    with pytest.raises(GuardError, match="MISSING_RECONCILE"):
        validate_chart(chart, facts)


def test_percentage_stack_requires_every_category(report):
    result = report.results[0]; facts = {f.id: f for f in result.facts}
    chart = next(c for c in result.charts if c.kind == "stacked_bar")
    chart.reconcile.pop()
    with pytest.raises(GuardError, match="MISSING_RECONCILE"):
        validate_chart(chart, facts)


def test_only_four_queries_no_sql_or_detail_fields():
    query = {"node": "aggregate", "id": "total", "metric": "aum", "operation": "sum"}
    assert TypeAdapter(MetricQuery).validate_python(query).node == "aggregate"
    for patch in ({"sql": "select * from customer"}, {"node": "query"}, {"operation": "eval"},
                  {"operation": "percentile"}, {"percentile": 50}):
        with pytest.raises(ValidationError):
            TypeAdapter(MetricQuery).validate_python({**query, **patch})
    with pytest.raises(ValidationError):
        Fact.model_validate(dict(id="test", metric="aum", label="余额", value=500, unit="元", sample_size=40,
                                 query_id="total", evidence=["测试"], customer_id="123"))


def test_schema_forbids_functions_html_options_and_new_charts(report):
    data = report.results[0].charts[0].model_dump()
    for patch in ({"kind": "radar"}, {"formatter": "function(){}"}, {"zero_baseline": False}, {"axis_min": 300}):
        with pytest.raises(ValidationError):
            InsightChartSpec.model_validate({**data, **patch})
    report.results[0].charts[0].title = "<img src=x onerror=alert(1)>"
    with pytest.raises(GuardError, match="UNSAFE_TEXT"):
        validate_report(report)


def test_binding_pins_stale_report(report):
    assert not report.is_stale(1, "a" * 64)
    assert report.is_stale(2, "a" * 64)
    assert report.is_stale(1, "b" * 64)


def test_blocked_run_is_empty(report):
    result = report.results[0]
    result.status = "BLOCKED"; result.level = "L4"; result.reasons = ["无权限"]
    with pytest.raises(GuardError, match="BLOCKED_DATA"):
        validate_report(report)
    result.facts = []; result.cards = []; result.charts = []
    validate_report(report)


def test_score_requires_prior_exclusions():
    registry = SkillRegistry()
    score = next(q for q in registry.get("opportunity_priority").queries if q.node == "score")
    assert score.reason_top_k == 2 and score.assumption
    data = score.model_dump(); data["exclusions"] = ["risk_mismatch"]
    with pytest.raises(ValidationError):
        ScoreQuery.model_validate(data)


@pytest.mark.parametrize("parameters", [{"min_gap_pp": -1}, {"min_gap_pp": float("nan")},
                                       {"min_gap_pp": True}, {"benchmark_type": "all_customers"}, {"sql": "x"}])
def test_parameters_cannot_relax_or_inject(parameters):
    with pytest.raises(ValueError):
        SkillRegistry().parameters("product_holding_gap", parameters)


def test_narration_rejects_wrong_number_keeps_all_facts_and_charts(report):
    candidates = {r.skill_id: [c.model_dump(mode="json") for c in r.cards] for r in report.results}
    candidates["asset_structure_profile"][0]["facts"]["text"] = "客群999人。"
    fallback, accepted = guarded_narration(report, candidates)
    assert not accepted and all(r.level == "L3" for r in fallback.results)
    for before, after in zip(report.results, fallback.results):
        assert before.facts == after.facts and before.charts == after.charts and before.cards == after.cards
    assert report.results[0].level is None


def test_safe_structured_narration(report):
    candidates = {r.skill_id: [c.model_dump(mode="json") for c in r.cards] for r in report.results}
    candidates["asset_structure_profile"][0]["facts"]["text"] = "客群规模 {fact:customers}，资产总额 {fact:total_aum}。"
    narrated, accepted = guarded_narration(report, candidates)
    assert accepted
    facts = {f.id: f for f in narrated.results[0].facts}
    assert render_statement(narrated.results[0].cards[0].facts, facts) == "客群规模 240人，资产总额 120000000元。"


def test_compose_is_deterministic(report):
    result = report.results[0]; facts = {f.id: f for f in result.facts}
    source = result.charts[0]
    kwargs = dict(chart_id=source.id, title=source.title, intent=source.intent, metric_label=source.metric_label,
                  series=source.series, facts=facts)
    first, second = compose_chart(**kwargs), compose_chart(**kwargs)
    assert first == second
    assert canonical_hash(first.model_dump(mode="json")) == canonical_hash(second.model_dump(mode="json"))
    assert data_profile(source.series, facts)["units"] == ["人"]
    with pytest.raises(ValueError):
        select_chart("radar", data_profile(source.series, facts))


def test_roundtrip(report):
    assert InsightReport.model_validate_json(report.model_dump_json()) == report
    assert json.loads(report.model_dump_json())["cohort"]["synthetic"] is True


def test_missing_bindings_block_without_queries(report):
    plan = plan_skill("asset_structure_profile", report.cohort, [], set())
    assert plan.status == "BLOCKED" and plan.queries == []
    assert "指标待绑定：aum" in plan.reasons


def test_binding_permission_and_version_gate(report):
    registry = SkillRegistry()
    metrics = registry.get("asset_structure_profile").metrics
    bindings = [MetricBinding(metric=metric, tag_id=i + 1, version="0.0.0", snapshot_id="synthetic-only",
                              unit=__import__("tagpilot_insight.metrics",fromlist=["METRICS"]).METRICS[metric].unit, status="PUBLISHED") for i, metric in enumerate(metrics)]
    bindings = [b for b in bindings if b.metric != "asset_holder"] + [MetricBinding(metric="asset_holder",category=c,tag_id=100+i,version="0.0.0",snapshot_id="synthetic-only",unit="人",status="PUBLISHED") for i,c in enumerate(("liquid","fixed","investment"))]
    eligible = {binding.tag_id for binding in bindings}
    plan = plan_skill("asset_structure_profile", report.cohort, bindings, eligible, {"min_deviation_pp": 20})
    assert plan.status == "READY" and plan.queries
    assert plan.parameters["min_deviation_pp"] == 20 and plan.cohort.plan_hash == report.cohort.plan_hash
    assert plan_skill("asset_structure_profile", report.cohort, bindings, eligible - {next(b.tag_id for b in bindings if b.metric == "aum")}).status == "BLOCKED"
    next(b for b in bindings if b.metric == "aum").snapshot_id = "different"
    assert plan_skill("asset_structure_profile", report.cohort, bindings, eligible).status == "BLOCKED"


def test_customer_count_uses_cohort_without_tag_binding(report):
    registry = SkillRegistry()
    bindings = [MetricBinding(metric=m, tag_id=i+1, version=report.cohort.binding_version,
                              snapshot_id=report.cohort.snapshot_id,
                              unit=__import__("tagpilot_insight.metrics", fromlist=["METRICS"]).METRICS[m].unit,
                              status="PUBLISHED")
                for i, m in enumerate(registry.get("asset_structure_profile").metrics)
                if m not in {"customer_count", "asset_holder"}]
    bindings += [MetricBinding(metric="asset_holder", category=c, tag_id=100+i,
                              version=report.cohort.binding_version, snapshot_id=report.cohort.snapshot_id,
                              unit="人", status="PUBLISHED")
                 for i, c in enumerate(("liquid", "fixed", "investment"))]
    plan = plan_skill("asset_structure_profile", report.cohort, bindings, {b.tag_id for b in bindings})
    assert plan.status == "READY"
    assert plan.cohort.count == report.cohort.count


def test_raw_number_type_coercion_rejected(report):
    data = report.results[0].facts[0].model_dump()
    for value in (True, "240", float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            Fact.model_validate({**data, "value": value})


def test_narration_cannot_swap_fact_references(report):
    candidates = {r.skill_id: [c.model_dump(mode="json") for c in r.cards] for r in report.results}
    candidates["asset_structure_profile"][0]["facts"] = dict(text="客群 {fact:total_aum}。", fact_ids=["total_aum"])
    fallback, accepted = guarded_narration(report, candidates)
    assert not accepted and fallback.results[0].cards == report.results[0].cards


def test_comparison_needs_both_sides_at_least_thirty(report):
    result = report.results[0]
    next(f for f in result.facts if f.id == "benchmark_liquid_share").sample_size = 29
    with pytest.raises(GuardError, match="COMPARISON_SAMPLE"):
        validate_report(report)


def test_default_dashboards_have_all_required_intents(report):
    registry = SkillRegistry()
    for skill in report.results:
        manifest = registry.get(skill.skill_id)
        facts = {f.id: f for f in skill.facts}
        dashboard = compose_dashboard(manifest.dashboard, skill.charts, facts)
        assert len(dashboard) == len(skill.charts)
        with pytest.raises(ValueError):
            compose_dashboard(manifest.dashboard, [skill.charts[0]], facts)


def test_exported_frontend_fixture_and_schemas_do_not_drift(report):
    from pathlib import Path
    from tagpilot_insight.contracts import Manifest
    from tagpilot_insight.planning import MetricPlan
    root = Path(__file__).resolve().parents[1]
    frontend = json.loads((root.parent / "tagpilot-assistant/src/insight/synthetic-preview.json").read_text())
    assert frontend == report.model_dump(mode="json")
    for model in (InsightReport, Manifest, MetricBinding, MetricPlan):
        assert json.loads((root / "schemas" / (model.__name__ + ".schema.json")).read_text()) == model.model_json_schema()
    assert json.loads((root / "schemas/MetricQuery.schema.json").read_text()) == TypeAdapter(MetricQuery).json_schema()
