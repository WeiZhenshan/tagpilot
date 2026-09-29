"""固定手工聚合 fixtures，不生成客户明细；不代表 G1/G2/G3 业务计算已经实现。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = []


def fact(fid, metric, label, value, unit="人", query="customers", n=240, **kwargs):
    row = dict(id=fid, metric=metric, label=label, value=value, unit=unit, query_id=query,
               sample_size=n, status="AVAILABLE", evidence=["固定手工聚合参考，合成数据"], **kwargs)
    FACTS.append(row)
    return fid


def statement(text, *ids, **kwargs):
    return dict(text=text, fact_ids=list(ids), **kwargs)


def chart(cid, title, intent, unit, metric_label, groups, kind=None, reconcile=None):
    defaults = dict(single_value="kpi", compare_categories="bar", show_composition="stacked_bar",
                    show_distribution="bar", show_matrix="heatmap", show_conversion="funnel")
    index = {f["id"]: f for f in FACTS}
    series = []
    for name, rows in groups:
        points = [dict(category=row[0], fact_id=row[1], value=index[row[1]]["value"],
                       **(dict(column=row[2]) if len(row) > 2 else {})) for row in rows]
        series.append(dict(name=name, fact_ids=[p["fact_id"] for p in points], points=points))
    return dict(id=cid, title=title, kind=kind or defaults[intent], intent=intent, unit=unit,
                metric_label=metric_label, series=series, reconcile=reconcile or [])


def card(cid, title, facts, comparison, diagnosis, action, boundary, definitions):
    return dict(id=cid, title=title, facts=facts, comparison=comparison, diagnosis=diagnosis,
                action=action, boundary=dict(text=boundary, data_as_of="2026-09-28", skill_version="0.1.0",
                                            sample_fact_id="customers", metric_definitions=definitions))


def result(skill, cards, charts):
    global FACTS
    value = dict(skill_id=skill, skill_version="0.1.0", pack_hash="0" * 64,
                 status="COMPLETE", facts=FACTS, cards=cards, charts=charts)
    FACTS = []
    return value


def build():
    fact("customers", "customer_count", "客户数", 240)
    fact("total_aum", "aum", "总 AUM", 120000000, "元", "total_aum")
    fact("average_aum", "aum", "平均 AUM", 500000, "元", "average_aum")
    fact("median_aum", "aum", "中位 AUM", 480000, "元", "median_aum")
    for fid, label, value in [("low", "普通层级", 80), ("mid", "中等层级", 100), ("high", "高资产层级", 60)]:
        fact(fid, "aum_tier", label, value, query="aum_bands")
    fact("benchmark_customers", "customer_count", "基准客户数", 800, query="benchmark_assets", n=800, role="BENCHMARK")
    for fid, label, value in [("low", "普通层级", 200), ("mid", "中等层级", 400), ("high", "高资产层级", 200)]:
        fact("benchmark_" + fid, "aum_tier", label, value, query="benchmark_assets", n=800, role="BENCHMARK")
    fact("benchmark_total", "aum", "基准总资产", 400000000, "元", "benchmark_assets", n=800, role="BENCHMARK")
    for fid, metric, amount, share, benchmark in [("liquid", "liquid_aum", 72000000, 60, 39),
                                                ("fixed", "fixed_aum", 24000000, 20, 31),
                                                ("investment", "investment_aum", 24000000, 20, 30)]:
        fact(fid + "_amount", metric, "资产金额", amount, "元", fid)
        fact(fid + "_share", metric, "金额加权占比", share, "%", fid,
             denominator_id="total_aum", derived_from=[fid + "_amount"], role="DERIVED")
        fact("benchmark_" + fid + "_amount", metric, "基准资产金额", benchmark * 4000000, "元", "benchmark_assets", n=800, role="BENCHMARK")
        fact("benchmark_" + fid + "_share", metric, "基准金额占比", benchmark, "%", "benchmark_assets", n=800,
             denominator_id="benchmark_total", derived_from=["benchmark_" + fid + "_amount"], role="BENCHMARK")
    fact("liquid_gap", "liquid_aum", "流动资产占比偏离", 21, "pp", "liquid",
         derived_from=["liquid_share", "benchmark_liquid_share"], role="DERIVED")
    fact("high_liquid", "liquid_share", "流动资产占比超过阈值且 AUM 有效", 120, query="high_liquid",
         role="POST_EXCLUSION", exclusions_applied=["missing_aum"])
    holder_rows = []
    for fid, label, count in [("liquid", "流动资产", 180), ("fixed", "定期", 120), ("investment", "投资资产", 90)]:
        fact(fid + "_holders", "asset_holder", "持有客户数", count, query="holders")
        fact(fid + "_holder_share", "asset_holder", "持有客户占比", count / 240 * 100, "%", "holders",
             denominator_id="customers", derived_from=[fid + "_holders"], role="DERIVED")
        holder_rows.append((label, fid + "_holder_share"))
    g1_charts = [chart("kpi_" + fid, label, "single_value", unit, label, [(label, [(label, fid)])])
                 for fid, label, unit in [("customers", "客户数", "人"), ("total_aum", "总 AUM", "元"),
                                          ("average_aum", "平均 AUM", "元"), ("median_aum", "中位 AUM", "元")]]
    g1_charts.append(chart("aum_bands", "AUM 分层人数对比", "show_distribution", "人", "客户数", [
        ("客群", [(label, fid) for fid, label in [("low", "普通层级"), ("mid", "中等层级"), ("high", "高资产层级")]]),
        ("基准", [(label, "benchmark_" + fid) for fid, label in [("low", "普通层级"), ("mid", "中等层级"), ("high", "高资产层级")]])],
        reconcile=[dict(kind="sum", fact_ids=["low", "mid", "high"], total_fact_id="customers"),
                   dict(kind="sum", fact_ids=["benchmark_low", "benchmark_mid", "benchmark_high"], total_fact_id="benchmark_customers")]))
    g1_charts.append(chart("asset_mix", "资产结构 · 金额加权占比", "show_composition", "%", "资产金额占比", [
        (label, [("客群", fid + "_share"), ("同层级基准", "benchmark_" + fid + "_share")])
        for fid, label in [("liquid", "流动资产"), ("fixed", "定期"), ("investment", "投资资产")]],
        reconcile=[dict(kind="percentage", fact_ids=[fid + "_share" for fid in ["liquid", "fixed", "investment"]]),
                   dict(kind="percentage", fact_ids=["benchmark_" + fid + "_share" for fid in ["liquid", "fixed", "investment"]])]))
    g1_charts.append(chart("holder_mix", "持有客户占比 · 客户可持有多个品类", "compare_categories", "%", "持有客户占比", [("客群", holder_rows)]))
    g1_card = card("asset_findings", "资产结构偏离", statement("客群 {fact:customers}，总 AUM {fact:total_aum}。", "customers", "total_aum"),
        statement("流动资产占比高于同层级基准 {fact:liquid_gap}。", "liquid_share", "benchmark_liquid_share", "liquid_gap",
                  benchmark_fact_ids=["benchmark_liquid_share"], difference_fact_ids=["liquid_gap"]),
        statement("规则提示流动资产配置占比较高，需要进一步核验持仓深度。", basis="RULE"),
        statement("对 AUM 有效且流动资产占比较高的 {fact:high_liquid} 进入产品持仓缺口诊断。", "high_liquid",
                  population_fact_id="high_liquid", priority="MEDIUM"),
        "合成聚合数据；金额占比与客户占比不同，客户可持有多个品类；不构成产品推荐。",
        ["AUM 为当前时点资产总额。", "金额占比分母为客群总资产；持有占比分母为客群人数。"])
    g1 = result("asset_structure_profile", [g1_card], g1_charts)

    fact("customers", "customer_count", "客户数", 240)
    fact("benchmark_customers", "customer_count", "基准样本", 800, query="benchmark_coverage", n=800, role="BENCHMARK")
    gap_rows, cohort_rows, benchmark_rows = [], [], []
    for fid, label, count, baseline in [("wealth", "理财", 60, 75), ("fund", "基金", 120, 62.5), ("insurance", "保险", 90, 35)]:
        fact(fid + "_holders", "product_holding", label + "持有客户", count, query="coverage")
        fact(fid + "_rate", "product_holding", label + "覆盖率", count / 240 * 100, "%", "coverage",
             denominator_id="customers", derived_from=[fid + "_holders"], role="DERIVED")
        fact(fid + "_benchmark_holders", "product_holding", label + "基准持有", baseline * 8, query="benchmark_coverage", n=800, role="BENCHMARK")
        fact(fid + "_benchmark_rate", "product_holding", label + "标准化基准", baseline, "%", "benchmark_coverage", n=800,
             denominator_id="benchmark_customers", derived_from=[fid + "_benchmark_holders"], role="BENCHMARK")
        fact(fid + "_gap", "product_holding", label + "缺口", baseline - count / 240 * 100, "pp", "coverage",
             derived_from=[fid + "_benchmark_rate", fid + "_rate"], role="DERIVED")
        cohort_rows.append((label, fid + "_rate")); benchmark_rows.append((label, fid + "_benchmark_rate")); gap_rows.append((label, fid + "_gap"))
    fact("wealth_unheld", "product_holding", "理财未持有", 180, query="coverage")
    fact("wealth_suitable", "suitability", "风险适配", 150, query="suitable")
    fact("wealth_opportunity", "product_holding", "扣除营销排除后的机会", 120, query="opportunity",
         role="POST_EXCLUSION", exclusions_applied=["risk_mismatch", "marketing_excluded"])
    # 热力图隐藏稀疏格；不保存具体稀疏样本人数及值。
    FACTS.append(dict(id="sparse_cell", metric="product_holding", label="稀疏格已抑制", value=None,
                      unit="pp", sample_size=None, status="SUPPRESSED", query_id="coverage", evidence=["小样本格已抑制"]))
    matrix_rows = [("理财", "wealth_gap", "中高资产"), ("理财", "sparse_cell", "普通层级"),
                   ("基金", "fund_gap", "中高资产"), ("保险", "insurance_gap", "中高资产")]
    funnel_ids = ["customers", "wealth_unheld", "wealth_suitable", "wealth_opportunity"]
    g2_charts = [chart("coverage", "产品覆盖率与标准化基准", "compare_categories", "%", "覆盖率", [("客群", cohort_rows), ("标准化基准", benchmark_rows)]),
        chart("gap_matrix", "品类与 AUM 层级缺口 · 稀疏格隐藏", "show_matrix", "pp", "覆盖缺口", [("缺口", matrix_rows)]),
        chart("opportunity_funnel", "理财机会漏斗", "show_conversion", "人", "客户数", [("客户", list(zip(["客群", "未持有", "风险适配", "扣除营销排除"], funnel_ids)))],
              reconcile=[dict(kind="funnel", fact_ids=funnel_ids)]),
        chart("gap_table", "品类缺口汇总", "compare_categories", "pp", "覆盖缺口", [("缺口", gap_rows)], kind="table")]
    g2_card = card("holding_findings", "理财持仓缺口", statement("理财持有客户 {fact:wealth_holders}，覆盖率 {fact:wealth_rate}。", "wealth_holders", "wealth_rate"),
        statement("理财覆盖率低于结构标准化基准，缺口 {fact:wealth_gap}。", "wealth_gap", "wealth_benchmark_rate", "wealth_rate",
                  benchmark_fact_ids=["wealth_benchmark_rate"], difference_fact_ids=["wealth_gap"]),
        statement("统计参考发现理财覆盖不足；已声明圈选背景不作为因果诊断。", basis="RULE"),
        statement("对扣除风险不适配及营销排除后的 {fact:wealth_opportunity} 核验触达意愿。", "wealth_opportunity",
                  population_fact_id="wealth_opportunity", priority="HIGH"),
        "合成参考结果；此阶段未实现结构标准化与置信区间业务计算。适当性映射待业务确认，真实数据不得使用合成映射。",
        ["覆盖率分母为当前客群人数；基准在本 fixture 的各格覆盖率相同，加权后保持原值。", "漏斗每一步为独立登记的手工聚合参考值。"])
    g2 = result("product_holding_gap", [g2_card], g2_charts)

    fact("customers", "customer_count", "客户数", 240)
    exclusions = ["risk_mismatch", "do_not_disturb", "recent_contact", "no_channel"]
    fact("marketable", "customer_count", "硬排除后可营销", 180, query="priority", role="POST_EXCLUSION", exclusions_applied=exclusions)
    for fid, label, count in [("high", "高", 80), ("medium", "中", 60), ("low", "低", 40)]:
        fact(fid, "customer_count", label + "优先级", count, query="priority", role="POST_EXCLUSION", exclusions_applied=exclusions)
    for fid, count in zip(exclusions, [20, 20, 20, 0]):
        fact(fid, "customer_count", fid, count, query="priority")
    component_rows = []
    for fid, label, values in [("value_score", "价值", [25, 15, 5]), ("demand_event", "需求事件", [20, 10, 0]),
                               ("product_gap", "产品缺口", [20, 15, 10]), ("historical_response", "历史响应", [15, 5, 0]),
                               ("channel_reach", "渠道可达", [10, 10, 10]), ("disturbance_penalty", "打扰惩罚", [0, -5, -10])]:
        rows = []
        for tier, tier_label, n, value in zip(["high", "medium", "low"], ["高", "中", "低"], [80, 60, 40], values):
            fact(tier + "_" + fid, fid, label + "平均贡献", value, "分", "priority", n=n)
            rows.append((tier_label, tier + "_" + fid))
        component_rows.append((label, rows))
    channel_rows = []
    for channel, label, values in [("phone", "电话", [50, 40, 20]), ("app", "手机银行", [30, 20, 20])]:
        rows = []
        for tier, tier_label, n, value in zip(["high", "medium", "low"], ["高", "中", "低"], [80, 60, 40], values):
            fact(tier + "_" + channel, "channel", label + "可达", value, query="priority", n=n)
            rows.append((tier_label, tier + "_" + channel))
        channel_rows.append((label, rows))
    tier_rows = [("高", "high"), ("中", "medium"), ("低", "low")]
    g3_charts = [chart("priority_funnel", "可营销机会漏斗", "show_conversion", "人", "客户数", [("客户", [("客群", "customers"), ("可营销", "marketable")])],
                      reconcile=[dict(kind="funnel", fact_ids=["customers", "marketable"])]),
        chart("tier_counts", "可营销客户优先级分档", "show_distribution", "人", "分档人数", [("客户", tier_rows)],
              reconcile=[dict(kind="sum", fact_ids=["high", "medium", "low"], total_fact_id="marketable")]),
        chart("contributions", "各档平均分项贡献 · 规则假设", "show_composition", "分", "平均贡献", component_rows),
        chart("channels", "各档主要有效渠道 · 每人仅计主渠道", "compare_categories", "人", "客户数", channel_rows,
              reconcile=[dict(kind="sum", fact_ids=[tier + "_phone", tier + "_app"], total_fact_id=tier) for tier in ["high", "medium", "low"]]),
        chart("reason_table", "优先级原因组合参考", "compare_categories", "人", "客户数", [("人数", [("价值与需求事件", "high"), ("价值与产品缺口", "medium"), ("产品缺口与渠道", "low")])], kind="table"),
        chart("exclusions", "硬排除原因 · 互斥归因", "compare_categories", "人", "排除客户数", [("客户", list(zip(["风险不适配", "勿扰", "近期已触达", "无有效渠道"], exclusions)))])]
    g3_card = card("priority_findings", "规则画像排序", statement("可营销客户 {fact:marketable}，高优先级客户 {fact:high}。", "marketable", "high"),
        statement("各档使用同一规则画像，本次不进行响应效果比较。", benchmark_fact_ids=[], difference_fact_ids=[]),
        statement("假设：价值与产品缺口共同构成优先级信号。", basis="HYPOTHESIS"),
        statement("优先对 {fact:high} 按已核验渠道人工触达。", "high", population_fact_id="high", priority="HIGH"),
        "合成聚合参考；权重是规则假设，未经响应数据校准；仅供排序参考，不做任务下发。",
        ["所有分档在硬排除后评分；高、中、低为并列分组，不是逐步漏斗。", "排除原因采用顺序互斥归因，渠道每人仅计主要有效渠道。"])
    g3 = result("opportunity_priority", [g3_card], g3_charts)
    return dict(schema_version=1, run_id="synthetic-golden-pack", cohort=dict(
        audience_id="synthetic-audience", audience_name="大额入金转化 · 合成客群", library_id=107,
        revision=1, plan_hash="a" * 64, snapshot_id="synthetic-only", count=240,
        data_as_of="2026-09-28", reference_date="2026-09-29", binding_version="0.0.0",
        declared_context="近三十天大额转入是已声明背景，不推断入金导致产品缺口。", synthetic=True), results=[g1, g2, g3])


if __name__ == "__main__":
    target = ROOT / "tagpilot_insight/fixtures/golden_pack.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
