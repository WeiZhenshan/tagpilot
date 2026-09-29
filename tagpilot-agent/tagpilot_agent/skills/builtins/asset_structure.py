"""Skill A：客群资产结构透视（L1 基础事实）。

回答“这群客户是什么样”：规模、AUM 总量与分布、资产/产品结构、活期沉淀、渠道可达性。
全部为确定性计算，与同层级基准比较后形成事实—对比—边界结构的洞察卡。
"""

from __future__ import annotations

from tagpilot_agent.skills.chartspec import (
    ChartAnnotation,
    build_category_spec,
    build_kpi_spec,
    build_stacked_spec,
    build_table_spec,
)
from tagpilot_agent.skills.contract import SkillContext, SkillOutcome
from tagpilot_agent.skills.insight import (
    InsightAction,
    InsightBenchmark,
    InsightBoundary,
    InsightCard,
    InsightDiagnosis,
    InsightFact,
    InsightProvenance,
    benchmark_evidence,
    metric_evidence,
    sanitize_text,
)
from tagpilot_agent.skills.metrics import (
    PRODUCT_DEFINITIONS,
    avg_of,
    band_order,
    is_excluded,
    is_online_reachable,
    median_of,
    rating_value,
    share,
)

LIQUID_HEAVY_THRESHOLD = 70.0


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counter: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "未分层")
        counter[label] = counter.get(label, 0) + 1
    return counter


def _liquid_ratio(row: dict) -> float:
    aum = float(row.get("aum_balance") or 0)
    if aum <= 0:
        return 0.0
    return round(float(row.get("avg_daily_deposit") or 0) * 100.0 / aum, 2)


def run(context: SkillContext) -> SkillOutcome:
    audience = context.audience_rows
    benchmark = context.benchmark_rows
    total = len(audience)
    outcome = SkillOutcome()
    data_as_of = context.as_of_date
    skill_id, skill_version = context.manifest.skill_id, context.manifest.version
    prov = InsightProvenance(
        skill_id=skill_id, skill_version=skill_version, data_as_of=data_as_of, trace_id=context.trace_id
    )

    # ---------- 规模与 AUM ----------
    aum_values = [float(row.get("aum_balance") or 0) for row in audience]
    total_aum = round(sum(aum_values), 2)
    avg_aum = avg_of(aum_values)
    median_aum = median_of(aum_values)
    coverage_avg = avg_of([float(row.get("total_products_count") or 0) for row in audience])

    outcome.add_metric("customer_count", total, numerator="客群客户数", dimensions=["branch_code", "cust_segment"])
    outcome.add_metric("total_aum", total_aum, denominator="—", dimensions=["aum_level"])
    outcome.add_metric("avg_aum", avg_aum, numerator="总AUM", denominator="客户数", dimensions=["aum_level"])
    outcome.add_metric("median_aum", median_aum, denominator="—")
    outcome.add_metric("product_coverage_avg", coverage_avg, numerator="Σ持有产品数", denominator="客户数")

    bench_avg_aum = avg_of([float(row.get("aum_balance") or 0) for row in benchmark])
    bench_aum_gap = round(avg_aum - bench_avg_aum, 2)
    bench_coverage = avg_of([float(row.get("total_products_count") or 0) for row in benchmark])

    evidence = [
        metric_evidence("EV_A01", "customer_count", f"客群客户数 {total} 人", total, "人", "标签宽表聚合", data_as_of),
        metric_evidence("EV_A02", "total_aum", f"总AUM {total_aum:,.0f} 元", total_aum, "元", "Σ aum_balance", data_as_of),
        metric_evidence("EV_A03", "avg_aum", f"人均AUM {avg_aum:,.0f} 元", avg_aum, "元", "总AUM / 客户数", data_as_of),
        metric_evidence("EV_A04", "median_aum", f"AUM中位数 {median_aum:,.0f} 元", median_aum, "元", "中位数", data_as_of),
    ]
    if benchmark:
        evidence.append(
            benchmark_evidence(
                "EV_A05",
                context.benchmark_id,
                f"{context.benchmark_name}人均AUM {bench_avg_aum:,.0f} 元（{len(benchmark)} 人）",
                bench_avg_aum,
                "元",
                data_as_of,
            )
        )

    cards: list[InsightCard] = []
    cards.append(
        InsightCard(
            card_id="IC_ASSET_01",
            title="客群规模与资产概览",
            fact=InsightFact(
                text=f"客群共 {total} 人，总AUM {total_aum:,.0f} 元，人均AUM {avg_aum:,.0f} 元，中位数 {median_aum:,.0f} 元",
                metric_ids=["customer_count", "total_aum", "avg_aum", "median_aum"],
                evidence_ids=["EV_A01", "EV_A02", "EV_A03", "EV_A04"],
            ),
            benchmark=InsightBenchmark(
                text=f"{context.benchmark_name}人均AUM {bench_avg_aum:,.0f} 元，本客群{'高' if bench_aum_gap >= 0 else '低'} {abs(bench_aum_gap):,.0f} 元",
                benchmark_id=context.benchmark_id,
                benchmark_name=context.benchmark_name,
                evidence_ids=["EV_A05"] if benchmark else [],
            )
            if benchmark
            else None,
            diagnosis=InsightDiagnosis(
                text=f"人均AUM{'高于' if bench_aum_gap >= 0 else '低于'}基准 {abs(bench_aum_gap):,.0f} 元，客群整体处于"
                f"{'较高' if avg_aum >= bench_avg_aum else '待提升'}的资产水平",
                type="rule_based_inference",
                confidence=0.86 if benchmark else 0.6,
            ),
            action=InsightAction(
                eligible_customer_count=total,
                priority="medium",
                recommendation="作为后续结构透视与产品缺口诊断的分析基数，暂不产生触达动作",
                rule_ids=["ASSET_SCOPE_V1"],
            ),
            boundary=InsightBoundary(
                text="仅描述客群当前资产分布，不构成产品适配结论；样本量低于 20 时不输出",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        )
    )

    # ---------- AUM 分层 ----------
    audience_bands = _count_by(audience, "aum_level")
    benchmark_bands = _count_by(benchmark, "aum_level") if benchmark else {}
    band_labels = sorted(set(audience_bands) | set(benchmark_bands), key=band_order)
    band_rows: list[dict] = []
    band_table: list[dict] = []
    band_evidence: list[str] = []
    for index, label in enumerate(band_labels, start=1):
        audience_count = audience_bands.get(label, 0)
        audience_share = share(audience_count, total)
        row = {"aum_level": label, "customer_count": audience_count, "share": audience_share, "audience_type": "目标客群"}
        band_rows.append(row)
        band_table.append(
            {"aum_level": label, "客户数": audience_count, "占比": f"{audience_share}%", "客群类型": "目标客群"}
        )
        ev_id = f"EV_A1{index:02d}"
        evidence.append(
            metric_evidence(ev_id, "aum_band_share", f"{label}：{audience_count} 人（{audience_share}%）", audience_share,
                            "percent", "分层计数", data_as_of)
        )
        band_evidence.append(ev_id)
        if benchmark:
            bench_count = benchmark_bands.get(label, 0)
            bench_share = share(bench_count, len(benchmark))
            band_rows.append(
                {"aum_level": label, "customer_count": bench_count, "share": bench_share, "audience_type": context.benchmark_name}
            )
            band_table.append(
                {"aum_level": label, "客户数": bench_count, "占比": f"{bench_share}%", "客群类型": context.benchmark_name}
            )
            evidence.append(
                benchmark_evidence(
                    f"{ev_id}B", context.benchmark_id, f"{context.benchmark_name} {label}：{bench_count} 人（{bench_share}%）",
                    bench_share, "percent", data_as_of,
                )
            )
            band_evidence.append(f"{ev_id}B")

    outcome.add_metric("aum_band_share", band_labels[0] if band_labels else "", unit="", dimensions=["aum_level"])

    charts = [
        build_kpi_spec(
            skill_id,
            skill_version,
            data_as_of,
            "客群规模与资产概览",
            [
                {"label": "客群客户数", "value": total, "unit": "人", "metric_id": "customer_count"},
                {"label": "总AUM", "value": total_aum, "unit": "元", "metric_id": "total_aum"},
                {"label": "人均AUM", "value": avg_aum, "unit": "元", "metric_id": "avg_aum",
                 "delta_text": f"较基准 {bench_aum_gap:+,.0f} 元" if benchmark else ""},
                {"label": "平均持有产品数", "value": coverage_avg, "unit": "个", "metric_id": "product_coverage_avg",
                 "delta_text": f"较基准 {coverage_avg - bench_coverage:+.2f} 个" if benchmark else ""},
            ],
            summary=f"客群 {total} 人，总AUM {total_aum:,.0f} 元，数据截至 {data_as_of}",
        )
    ]

    if band_rows:
        charts.append(
            build_stacked_spec(
                skill_id,
                skill_version,
                data_as_of,
                "AUM 分层结构（目标客群 vs 基准）",
                band_rows,
                category_field="aum_level",
                measure_field="share",
                series_field="audience_type",
                summary=f"按 AUM 层级展示客户占比，共 {len(band_labels)} 个层级",
            )
        )
        cards.append(
            InsightCard(
                card_id="IC_ASSET_02",
                title="AUM 分层结构",
                fact=InsightFact(
                    text="；".join(
                        f"{row['aum_level']} {row['customer_count']} 人（{row['share']}%）"
                        for row in band_rows
                        if row["audience_type"] == "目标客群"
                    ),
                    metric_ids=["aum_band_share"],
                    evidence_ids=band_evidence[:6],
                ),
                benchmark=InsightBenchmark(
                    text=f"与{context.benchmark_name}的层级分布逐层对比见图表数据表",
                    benchmark_id=context.benchmark_id,
                    benchmark_name=context.benchmark_name,
                    evidence_ids=[item for item in band_evidence if item.endswith("B")][:6],
                )
                if benchmark
                else None,
                diagnosis=InsightDiagnosis(
                    text=f"客群主要分布在{max(audience_bands, key=audience_bands.get) if audience_bands else '未知'}层级，"
                    "分层集中度决定后续适合推荐的产品类型",
                    type="rule_based_inference",
                    confidence=0.8,
                ),
                action=InsightAction(
                    eligible_customer_count=total,
                    priority="medium",
                    recommendation="按层级分别进入产品缺口诊断，不同 AUM 层级使用不同基准",
                    rule_ids=["AUM_BAND_V1"],
                ),
                boundary=InsightBoundary(
                    text="层级名称与口径来自标签库 aum_level 字段，跨库比较前需确认层级定义一致",
                    data_as_of=data_as_of,
                    sample_size=total,
                ),
                provenance=prov,
            )
        )

    # ---------- 产品与资产结构 ----------
    product_rows: list[dict] = []
    product_table: list[dict] = []
    product_evidence: list[str] = []
    for index, product in enumerate(PRODUCT_DEFINITIONS, start=1):
        flag = product["flag"]
        held = sum(1 for row in audience if row.get(flag))
        rate = share(held, total)
        row = {"product_category": product["label"], "holding_rate": rate, "audience_type": "目标客群"}
        product_rows.append(row)
        bench_rate = share(sum(1 for row in benchmark if row.get(flag)), len(benchmark)) if benchmark else 0.0
        product_table.append(
            {
                "产品类别": product["label"],
                "目标客群持有率": f"{rate}%",
                f"{context.benchmark_name}持有率": f"{bench_rate}%" if benchmark else "—",
                "缺口（百分点）": f"{round(bench_rate - rate, 2)}" if benchmark else "—",
            }
        )
        ev_id = f"EV_A2{index:02d}"
        evidence.append(
            metric_evidence(ev_id, "product_holding_rate", f"{product['label']}持有率 {rate}%（{held}/{total}）", rate,
                            "percent", f"{flag} 计数", data_as_of)
        )
        product_evidence.append(ev_id)
        if benchmark:
            product_rows.append(
                {"product_category": product["label"], "holding_rate": bench_rate, "audience_type": context.benchmark_name}
            )
            evidence.append(
                benchmark_evidence(
                    f"{ev_id}B", context.benchmark_id,
                    f"{context.benchmark_name}{product['label']}持有率 {bench_rate}%", bench_rate, "percent", data_as_of,
                )
            )
            product_evidence.append(f"{ev_id}B")

    wealth_rate = next(
        (row["holding_rate"] for row in product_rows if row["product_category"] == "理财" and row["audience_type"] == "目标客群"),
        0.0,
    )
    outcome.add_metric("wealth_product_holding_rate", wealth_rate, numerator="持有理财产品客户数", denominator="客群客户数")

    charts.append(
        build_category_spec(
            skill_id,
            skill_version,
            data_as_of,
            "客群与基准的产品持有率对比",
            "product_category",
            "holding_rate",
            product_rows,
            mark="bar",
            orientation="horizontal",
            series_field="audience_type",
            unit="percent",
            semantic_type="percentage",
            metric_id="product_holding_rate",
            summary="横向条形图展示九类产品的持有率，按目标客群与基准分组对比",
            legend_filter=True,
        )
    )
    charts.append(
        build_table_spec(
            skill_id, skill_version, data_as_of, "资产结构明细（含基准与缺口）",
            [
                {"field": "产品类别", "semantic_type": "category", "role": "dimension"},
                {"field": "目标客群持有率", "semantic_type": "percentage", "role": "measure", "unit": "percent"},
                {"field": f"{context.benchmark_name}持有率", "semantic_type": "percentage", "role": "measure", "unit": "percent"},
                {"field": "缺口（百分点）", "semantic_type": "measure", "role": "measure"},
            ],
            product_table,
            summary="明细表给出每类产品的持有率、基准与缺口，可展开对账",
            intent="table",
            chart_skill="chart.intent.show_ranking",
        )
    )
    cards.append(
        InsightCard(
            card_id="IC_ASSET_03",
            title="产品持有结构与覆盖度",
            fact=InsightFact(
                text=f"人均持有 {coverage_avg} 个产品；理财产品持有率 {wealth_rate}%",
                metric_ids=["product_coverage_avg", "wealth_product_holding_rate"],
                evidence_ids=product_evidence[:5],
            ),
            benchmark=InsightBenchmark(
                text=f"人均产品数较{context.benchmark_name}{coverage_avg - bench_coverage:+.2f} 个",
                benchmark_id=context.benchmark_id,
                benchmark_name=context.benchmark_name,
                evidence_ids=[item for item in product_evidence if item.endswith("B")][:5],
            )
            if benchmark
            else None,
            diagnosis=InsightDiagnosis(
                text="产品结构以基础类为主，覆盖度差异指向可进一步诊断的缺口方向",
                type="rule_based_inference",
                confidence=0.78,
            ),
            action=InsightAction(
                eligible_customer_count=total,
                priority="medium",
                recommendation="进入产品持仓缺口诊断，按风险等级与价值层级分群识别机会",
                rule_ids=["PRODUCT_COVERAGE_V1"],
            ),
            boundary=InsightBoundary(
                text="持有率为时点值，不含产品余额与期限结构；不含非本行持有的产品",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        )
    )

    # ---------- 活期沉淀与渠道可达 ----------
    liquid_rows = [row for row in audience if _liquid_ratio(row) > LIQUID_HEAVY_THRESHOLD]
    liquid_share = share(len(liquid_rows), total)
    outcome.add_metric("liquid_heavy_share", liquid_share, numerator="活期占比>70% 客户数", denominator="客群客户数")
    if benchmark:
        bench_liquid = share(
            sum(1 for row in benchmark if _liquid_ratio(row) > LIQUID_HEAVY_THRESHOLD), len(benchmark)
        )
        liquid_gap = round(liquid_share - bench_liquid, 2)
    else:
        bench_liquid, liquid_gap = 0.0, 0.0

    reachable = sum(1 for row in audience if is_online_reachable(row))
    reachable_share = share(reachable, total)
    outcome.add_metric("channel_reachable_rate", reachable_share, numerator="线上渠道客户数", denominator="客群客户数")

    excluded = sum(1 for row in audience if is_excluded(row))
    excluded_share = share(excluded, total)
    outcome.add_metric("excluded_customer_share", excluded_share)

    evidence.extend(
        [
            metric_evidence(
                "EV_A30", "liquid_heavy_share",
                f"活期及短期存款占比超过 {LIQUID_HEAVY_THRESHOLD:.0f}% 的客户 {len(liquid_rows)} 人（{liquid_share}%）",
                liquid_share, "percent", "avg_daily_deposit / aum_balance", data_as_of,
            ),
            metric_evidence("EV_A31", "channel_reachable_rate", f"线上渠道可达客户 {reachable} 人（{reachable_share}%）",
                            reachable_share, "percent", "手机银行/网银/微信银行任一", data_as_of),
            metric_evidence("EV_A32", "excluded_customer_share", f"营销排除客户 {excluded} 人（{excluded_share}%）",
                            excluded_share, "percent", "黑名单或欺诈预警", data_as_of),
        ]
    )
    if benchmark:
        evidence.append(
            benchmark_evidence(
                "EV_A33", context.benchmark_id,
                f"{context.benchmark_name}活期沉淀占比 {bench_liquid}%", bench_liquid, "percent", data_as_of,
            )
        )

    cards.append(
        InsightCard(
            card_id="IC_ASSET_04",
            title="资金沉淀与渠道可达性",
            fact=InsightFact(
                text=f"{len(liquid_rows)} 人活期及短期存款占金融资产比例超过 {LIQUID_HEAVY_THRESHOLD:.0f}%（占客群 {liquid_share}%）；"
                f"线上渠道可达 {reachable_share}%",
                metric_ids=["liquid_heavy_share", "channel_reachable_rate"],
                evidence_ids=["EV_A30", "EV_A31", "EV_A32"],
            ),
            benchmark=InsightBenchmark(
                text=f"较{context.benchmark_name}高 {liquid_gap:+.2f} 个百分点",
                benchmark_id=context.benchmark_id,
                benchmark_name=context.benchmark_name,
                evidence_ids=["EV_A33"],
            )
            if benchmark
            else None,
            diagnosis=InsightDiagnosis(
                text="资金已进入本行但沉淀于活期，说明配置深度不足；线上可达性支持低打扰的数字化触达",
                type="rule_based_inference",
                confidence=0.88,
            ),
            action=InsightAction(
                eligible_customer_count=max(total - excluded, 0),
                priority="medium",
                recommendation="在排除名单客户后，作为产品缺口诊断与机会排序的输入客群",
                rule_ids=["LIQUID_DEPOSIT_V1", "EXCLUSION_V1"],
            ),
            boundary=InsightBoundary(
                text="活期占比以日均存款/AUM 近似，未区分定期期限结构；样本量低于 20 时不输出",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        )
    )

    outcome.evidence = evidence
    outcome.insight_cards = cards
    outcome.charts = charts
    outcome.diagnostics = [
        {"level": "info", "code": "ASSET_STRUCTURE_OK", "message": f"完成 {total} 位客户的资产结构透视"},
    ]
    if liquid_gap > 0:
        outcome.diagnostics.append(
            {"level": "warn", "code": "LIQUID_HEAVY", "message": f"活期沉淀占比高于基准 {liquid_gap:.2f} 个百分点"}
        )
    outcome.payload = {
        "risk_level_distribution": {
            rating: sum(1 for row in audience if rating_value(row) == int(rating[-1]))
            for rating in sorted({"R1", "R2", "R3", "R4", "R5"})
        },
        "aum_band_table": band_table,
        "product_table": product_table,
    }
    # 使用 sanitize_text 统一清洗文案，避免任何注入内容进入展示层
    for card in outcome.insight_cards:
        card.title = sanitize_text(card.title)
        card.fact.text = sanitize_text(card.fact.text)
        card.diagnosis.text = sanitize_text(card.diagnosis.text)
    return outcome
