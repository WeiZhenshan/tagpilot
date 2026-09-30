"""数字只来自事实登记表；Guard 失败永远不改数字、不放宽样本门槛。"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping

from .contracts import Fact, InsightCard, InsightChartSpec, InsightReport, Statement
from .registry import INTENTS, SkillRegistry

REFERENCE = re.compile(r"\{fact:([a-z][a-z0-9_.-]{0,79})\}")
RAW_NUMBER = re.compile(r"[\d０-９]|[零〇一二三四五六七八九十百千万亿两]+(?:人|元|%|％|成|倍|个百分点)")
CAUSAL = re.compile(r"导致|因而|因此|所以|促使|归因|原因是|因为|caus(?:e|ed|ation)|resulted in", re.I)
VAGUE = re.compile(r"建议加强营销|加强营销|加大营销力度")
UNSAFE = re.compile(r"<[a-zA-Z!/]")


class GuardError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def require(condition: bool, code: str, message: str):
    if not condition:
        raise GuardError(code, message)


def fact_value(facts: Mapping[str, Fact], fact_id: str) -> float:
    require(fact_id in facts, "UNKNOWN_FACT", "引用未登记事实")
    fact = facts[fact_id]
    require(fact.status == "AVAILABLE" and fact.value is not None, "UNAVAILABLE_FACT", "不能引用抑制或缺失事实")
    return fact.value


def validate_statement(statement: Statement, facts: Mapping[str, Fact]):
    refs = set(REFERENCE.findall(statement.text))
    require(refs <= set(statement.fact_ids), "UNDECLARED_REFERENCE", "文案数字引用未声明")
    for fact_id in statement.fact_ids:
        fact_value(facts, fact_id)
    plain = REFERENCE.sub("", statement.text)
    require(not RAW_NUMBER.search(plain), "UNBOUND_NUMBER", "文案数字必须通过事实引用生成")
    require(not CAUSAL.search(plain), "CAUSAL_LANGUAGE", "诊断不允许无因果证据的措辞")
    require(not VAGUE.search(plain), "VAGUE_ACTION", "行动必须有明确客户范围和动作")
    require(not UNSAFE.search(plain), "UNSAFE_TEXT", "不允许 HTML 文案")


def render_statement(statement: Statement, facts: Mapping[str, Fact]) -> str:
    validate_statement(statement, facts)
    def replace(match):
        fact = facts[match[1]]
        number = format(fact.value, ".10g")
        return number + fact.unit
    return REFERENCE.sub(replace, statement.text)


def validate_card(card: InsightCard, facts: Mapping[str, Fact], skill_version: str, data_as_of):
    for statement in (card.facts, card.comparison, card.diagnosis, card.action):
        validate_statement(statement, facts)
    require(not RAW_NUMBER.search(card.title), "UNBOUND_NUMBER", "卡片标题不能含自由数字")
    compare = card.comparison
    if re.search(r"高于|低于|缺口|偏离|higher|lower|gap", compare.text, re.I):
        require(bool(compare.benchmark_fact_ids and compare.difference_fact_ids), "MISSING_BENCHMARK", "比较必须有基准和差值事实")
    for fact_id in compare.benchmark_fact_ids:
        fact_value(facts, fact_id)
        require(facts[fact_id].role == "BENCHMARK", "INVALID_BENCHMARK", "基准事实未标记")
        require(facts[fact_id].sample_size >= 30, "COMPARISON_SAMPLE", "比较基准样本不足")
    for fact_id in compare.difference_fact_ids:
        fact_value(facts, fact_id)
        require(facts[fact_id].role == "DERIVED", "INVALID_DIFFERENCE", "差值必须来自派生事实")
        require(facts[fact_id].sample_size >= 30, "COMPARISON_SAMPLE", "比较客群样本不足")
    if card.diagnosis.basis == "HYPOTHESIS":
        require("假设" in card.diagnosis.text, "UNLABELED_HYPOTHESIS", "推测必须标为假设")
    action = card.action
    if action.priority != "NONE":
        require(action.population_fact_id is not None, "MISSING_ACTION_POPULATION", "行动必须给出扣除排除规则后的范围")
    if action.population_fact_id:
        fact_value(facts, action.population_fact_id)
        population = facts[action.population_fact_id]
        require(population.role == "POST_EXCLUSION" and population.unit == "人", "INVALID_ACTION_POPULATION", "行动范围必须是扣除排除规则后的客户数")
        require(action.population_fact_id in action.fact_ids and action.population_fact_id in REFERENCE.findall(action.text), "MISSING_ACTION_REFERENCE", "行动文案必须引用客户范围")
    boundary = card.boundary
    require(boundary.skill_version == skill_version and boundary.data_as_of == data_as_of, "EVIDENCE_VERSION", "证据日期或技能版本不一致")
    fact_value(facts, boundary.sample_fact_id)
    require(facts[boundary.sample_fact_id].unit == "人", "INVALID_SAMPLE", "边界样本须引用客户数")
    require(not UNSAFE.search(boundary.text), "UNSAFE_TEXT", "边界不允许 HTML")


def validate_facts(facts: Mapping[str, Fact], suppression: int):
    for fact in facts.values():
        require(not UNSAFE.search(fact.label), "UNSAFE_TEXT", "事实标签不允许 HTML")
        if fact.status != "AVAILABLE":
            continue
        require(fact.sample_size >= suppression, "SMALL_SAMPLE", "小样本事实应被抑制")
        if fact.unit == "人":
            require(fact.value >= 0 and fact.value.is_integer(), "INVALID_COUNT", "人数必须是非负整数")
            require(not 0 < fact.value < suppression, "SMALL_CELL", "小样本人数应被抑制")
        if fact.unit == "%":
            require(0 <= fact.value <= 100 and bool(fact.denominator_id), "MISSING_DENOMINATOR", "百分比必须有有效分母")
        for source in fact.derived_from:
            fact_value(facts, source)
        require(fact.id not in fact.derived_from and fact.denominator_id != fact.id, "CYCLIC_FACT", "派生事实不能引用自身")
        if fact.denominator_id:
            denominator = fact_value(facts, fact.denominator_id)
            require(denominator > 0, "INVALID_DENOMINATOR", "分母必须为正数")
            if fact.unit == "%" and fact.derived_from:
                expected = math.fsum(fact_value(facts, ref) for ref in fact.derived_from) / denominator * 100
                require(abs(expected - fact.value) <= .01, "FACT_RECONCILIATION", "百分比与分子分母不一致")
        if fact.unit == "pp":
            require(len(fact.derived_from) == 2, "MISSING_DIFFERENCE_SOURCE", "pp 差值必须引用两侧比例")
            a, b = fact.derived_from
            require(facts[a].unit == facts[b].unit == "%" and abs(fact_value(facts, a) - fact_value(facts, b) - fact.value) <= .01,
                    "FACT_RECONCILIATION", "pp 差值与两侧比例不一致")
    visiting, visited = set(), set()
    def visit(fid):
        require(fid not in visiting, "CYCLIC_FACT", "事实派生关系存在环")
        if fid in visited:
            return
        visiting.add(fid)
        fact = facts[fid]
        for source in [*fact.derived_from, *([fact.denominator_id] if fact.denominator_id else [])]:
            require(source in facts, "UNKNOWN_FACT", "派生事实来源未登记")
            visit(source)
        visiting.remove(fid)
        visited.add(fid)
    for fid in facts:
        visit(fid)


def validate_chart(spec: InsightChartSpec, facts: Mapping[str, Fact]):
    require(spec.kind == "table" or INTENTS[spec.intent] == spec.kind, "INTENT_MISMATCH", "图型不符合声明意图")
    require(not UNSAFE.search(spec.title + spec.metric_label), "UNSAFE_TEXT", "图表标题或轴不允许 HTML")
    all_points = []
    for series in spec.series:
        require(set(series.fact_ids) == {p.fact_id for p in series.points}, "SERIES_EVIDENCE", "每个系列须完整绑定事实")
        require(len({(p.category, p.column) for p in series.points}) == len(series.points), "DUPLICATE_CELL", "系列存在重复类别或格子")
        for point in series.points:
            require(point.fact_id in facts, "UNKNOWN_FACT", "图表引用未登记事实")
            fact = facts[point.fact_id]
            require(spec.unit == fact.unit, "UNIT_MISMATCH", "轴单位与事实单位不一致")
            require(point.value == fact.value, "CHART_FACT_MISMATCH", "图上数字与事实登记表不一致")
            if fact.status != "AVAILABLE":
                require(point.value is None, "SMALL_SAMPLE", "抑制格子不得下发数值")
            if spec.kind == "heatmap":
                require(point.column is not None, "MATRIX_ENCODING", "热力图须有列维度")
            else:
                require(point.column is None, "INVALID_ENCODING", "非矩阵图不允许列编码")
        all_points.extend(series.points)
    require(len({p.category for p in all_points}) <= 12, "TOO_MANY_CATEGORIES", "类别过多，需要聚合其他或重新查询")
    require(len({p.column for p in all_points}) <= 12, "TOO_MANY_CATEGORIES", "矩阵列过多")
    if spec.kind in {"kpi", "heatmap", "funnel"}:
        require(len(spec.series) == 1, "SERIES_COUNT", "此图型只允许单系列")
    if spec.kind == "kpi":
        require(len(all_points) == 1, "KPI_COUNT", "每个 KPI 只含一个事实")
    for annotation in spec.annotations:
        validate_statement(Statement(text=annotation.text, fact_ids=annotation.fact_ids), facts)
    displayed = {p.fact_id for p in all_points}
    for reconcile in spec.reconcile:
        require(set(reconcile.fact_ids) <= displayed, "RECONCILE_EVIDENCE", "对账成员必须在图上")
        require(len(reconcile.fact_ids) == len(set(reconcile.fact_ids)), "DUPLICATE_FACT", "对账事实重复")
        values = [fact_value(facts, fid) for fid in reconcile.fact_ids]
        if reconcile.kind == "funnel":
            require(values == sorted(values, reverse=True) and min(values) >= 0, "FUNNEL_ORDER", "漏斗人数须逐步减少")
        else:
            if reconcile.kind == "percentage":
                require(spec.unit == "%", "UNIT_MISMATCH", "占比对账只能使用百分比")
                target = 100
            else:
                require(bool(reconcile.total_fact_id), "MISSING_TOTAL", "合计对账必须有总量")
                target = fact_value(facts, reconcile.total_fact_id)
                require(facts[reconcile.total_fact_id].unit == spec.unit, "UNIT_MISMATCH", "合计单位不一致")
            require(abs(math.fsum(values) - target) <= reconcile.tolerance, "RECONCILIATION", "图表合计无法对账")
    if spec.kind == "funnel":
        require(any(r.kind == "funnel" and r.fact_ids == [p.fact_id for p in all_points] for r in spec.reconcile), "MISSING_RECONCILE", "漏斗必须声明完整顺序对账")
    if spec.kind == "stacked_bar" and spec.unit == "%":
        require(bool(spec.reconcile), "MISSING_RECONCILE", "百分比堆叠必须声明每组对账")
        for category in {p.category for p in all_points}:
            ids = {p.fact_id for p in all_points if p.category == category}
            require(any(r.kind == "percentage" and set(r.fact_ids) == ids for r in spec.reconcile), "MISSING_RECONCILE", "百分比堆叠缺少分组对账")


def validate_report(report: InsightReport, registry: SkillRegistry | None = None) -> InsightReport:
    registry = registry or SkillRegistry()
    require(len({r.skill_id for r in report.results}) == len(report.results), "DUPLICATE_SKILL", "报告技能重复")
    for result in report.results:
        manifest = registry.get(result.skill_id)
        require(result.skill_version == manifest.version and result.pack_hash == registry.hash(result.skill_id), "PACK_MISMATCH", "技能版本或包 hash 不匹配")
        # DRAFT 可以在合成数据中验证；真实运行不得绕过 Java 发布治理。
        require(report.cohort.synthetic or manifest.status == "PUBLISHED", "UNPUBLISHED_SKILL", "草稿技能仅允许合成预览")
        if result.status == "BLOCKED":
            require(result.level == "L4" and bool(result.reasons) and not (result.facts or result.cards or result.charts), "BLOCKED_DATA", "阻断结果不得出数")
            continue
        require(report.cohort.count >= manifest.preconditions.min_sample, "SMALL_SAMPLE", "客群样本不足")
        age = (report.cohort.reference_date - report.cohort.data_as_of).days
        require(0 <= age <= manifest.preconditions.max_stale_days, "STALE_DATA", "数据日期未来或超过时效")
        require(bool(result.facts and result.cards and result.charts), "EMPTY_RESULT", "成功结果必须有事实、卡片与图表")
        require(result.level in {None, "L2", "L3"}, "INVALID_DEGRADE_LEVEL", "非阻断结果不能标为 L4")
        if result.status == "PARTIAL":
            require(result.level == "L2" and bool(result.reasons), "MISSING_DEGRADE_REASON", "部分成功必须说明原因")
        require(len({f.id for f in result.facts}) == len(result.facts), "DUPLICATE_FACT", "事实标识重复")
        facts = {f.id: f for f in result.facts}
        query_ids = {q.id for q in manifest.queries}
        for fact in facts.values():
            require(fact.query_id in query_ids and fact.metric in manifest.metrics, "UNDECLARED_METRIC", "事实引用未声明指标或查询")
        validate_facts(facts, manifest.preconditions.suppression_threshold)
        cohort_counts = [f for f in facts.values() if f.metric == "customer_count" and f.query_id == "customers"]
        require(len(cohort_counts) == 1 and cohort_counts[0].value == report.cohort.count, "COHORT_COUNT", "各技能客群人数必须与快照一致")
        for card in result.cards:
            validate_card(card, facts, result.skill_version, report.cohort.data_as_of)
            if result.skill_id == "opportunity_priority":
                require("假设" in card.boundary.text and "未经" in card.boundary.text, "UNCALIBRATED_SCORE", "评分必须声明权重假设未经响应数据校准")
        for chart in result.charts:
            validate_chart(chart, facts)
        # C3 的校验在报告出口统一执行，缺失关键图表不能冒充完整报告。
        from .charts import compose_dashboard
        compose_dashboard(manifest.dashboard, result.charts, facts, partial=result.status == "PARTIAL")
    return report
