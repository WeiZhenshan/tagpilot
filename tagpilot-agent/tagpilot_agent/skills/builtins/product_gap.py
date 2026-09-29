"""Skill B：产品持仓缺口诊断（L2 诊断分析）。

与同价值、同风险层级基准比较，识别明显低配或空白的类别，并在排除风险不适配与营销禁止客户后，
给出可落地的机会客户范围与原因。这是最能体现业务价值的核心 Skill。
"""

from __future__ import annotations

from tagpilot_agent.skills.chartspec import (
    ChartAnnotation,
    build_category_spec,
    build_heatmap_spec,
    build_kpi_spec,
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
    rule_evidence,
    sanitize_text,
)
from tagpilot_agent.skills.metrics import (
    PRODUCT_DEFINITIONS,
    RISK_ORDER,
    is_excluded,
    merge_small_counts,
    product_available,
    rating_of,
    share,
)

MIN_GAP_POINTS = 3.0  # 缺口显著阈值（百分点），低于该值不进入机会诊断


def _holding_rate(rows: list[dict], flag: str) -> float:
    if not rows:
        return 0.0
    return share(sum(1 for row in rows if row.get(flag)), len(rows))


def run(context: SkillContext) -> SkillOutcome:
    audience = context.audience_rows
    benchmark = context.benchmark_rows
    total = len(audience)
    data_as_of = context.as_of_date
    skill_id, skill_version = context.manifest.skill_id, context.manifest.version
    prov = InsightProvenance(
        skill_id=skill_id, skill_version=skill_version, data_as_of=data_as_of, trace_id=context.trace_id
    )
    min_group = context.manifest.preconditions.min_customer_count
    outcome = SkillOutcome()
    evidence = []
    diagnostics: list[dict] = []

    excluded_rows = [row for row in audience if is_excluded(row)]
    eligible_rows = [row for row in audience if not is_excluded(row)]
    excluded_share = share(len(excluded_rows), total)
    outcome.add_metric("excluded_customer_share", excluded_share, numerator="排除客户数", denominator="客群客户数")
    evidence.append(
        rule_evidence(
            "EV_B01", "EXCLUSION_V1",
            f"黑名单/欺诈预警客户 {len(excluded_rows)} 人（{excluded_share}%）已从机会名单排除",
            excluded_share,
        )
    )

    risk_counts = {rating: 0 for rating in RISK_ORDER}
    for row in audience:
        risk_counts[rating_of(row)] = risk_counts.get(rating_of(row), 0) + 1

    gap_rows: list[dict] = []
    gap_table: list[dict] = []
    heat_rows: list[dict] = []
    opportunity_by_product: dict[str, dict] = {}
    evidence_index = 1

    for product in PRODUCT_DEFINITIONS:
        flag = product["flag"]
        audience_rate = _holding_rate(audience, flag)
        bench_rate = _holding_rate(benchmark, flag) if benchmark else 0.0
        gap = round(bench_rate - audience_rate, 2)

        opportunity_rows = [row for row in eligible_rows if not row.get(flag) and product_available(product, row)]
        unsuitable = [row for row in audience if not product_available(product, row)]
        opportunity_count = len(opportunity_rows)
        opportunity_share = share(opportunity_count, total)
        unsuitable_share = share(len(unsuitable), total)

        opportunity_by_product[product["key"]] = {
            "label": product["label"],
            "gap": gap,
            "opportunity_count": opportunity_count,
            "opportunity_share": opportunity_share,
            "audience_rate": audience_rate,
            "benchmark_rate": bench_rate,
            "min_rating": product["min_rating"],
            "unsuitable_share": unsuitable_share,
        }

        gap_rows.append(
            {
                "product_category": product["label"],
                "gap_points": gap,
                "opportunity_count": opportunity_count,
                "audience_type": "缺口与机会",
            }
        )
        gap_table.append(
            {
                "产品类别": product["label"],
                "目标客群持有率": f"{audience_rate}%",
                f"{context.benchmark_name}持有率": f"{bench_rate}%" if benchmark else "—",
                "缺口（百分点）": gap,
                "风险适配机会客户数": opportunity_count,
                "最低适配等级": product["min_rating"],
            }
        )
        evidence.extend(
            [
                metric_evidence(
                    f"EV_B1{evidence_index:02d}", "product_gap_rate",
                    f"{product['label']}：目标持有率 {audience_rate}%、基准 {bench_rate}%、缺口 {gap} 个百分点",
                    gap, "percent", "持有率差值", data_as_of,
                ),
                metric_evidence(
                    f"EV_B2{evidence_index:02d}", "opportunity_customer_count",
                    f"{product['label']}适配机会客户 {opportunity_count} 人（风险等级≥{product['min_rating']} 且未持有且未排除）",
                    opportunity_count, "人", "风险适配+持有状态+排除规则", data_as_of,
                ),
            ]
        )
        evidence_index += 1

        for rating in sorted(RISK_ORDER):
            group = [row for row in audience if rating_of(row) == rating]
            if len(group) < min_group:
                diagnostics.append(
                    {
                        "level": "info",
                        "code": "SMALL_GROUP_SUPPRESSED",
                        "message": f"{product['label']} × {rating} 分组样本 {len(group)} 低于 {min_group}，热力图已抑制",
                    }
                )
                continue
            heat_rows.append(
                {
                    "product_category": product["label"],
                    "risk_level": rating,
                    "opportunity_rate": share(
                        sum(1 for row in group if not row.get(flag) and product_available(product, row)), len(group)
                    ),
                }
            )

    ranked = sorted(opportunity_by_product.items(), key=lambda item: item[1]["gap"], reverse=True)
    top_key, top = ranked[0] if ranked else ("", {})
    significant = [item for item in ranked if item[1]["gap"] >= MIN_GAP_POINTS]
    total_opportunity = max((item[1]["opportunity_count"] for item in ranked), default=0)
    primary_key, primary = (significant[0] if significant else ranked[0]) if ranked else ("", {})

    outcome.add_metric("product_gap_rate", primary.get("gap", 0.0), numerator="基准持有率−目标持有率", denominator="—",
                       dimensions=["product_category"])
    outcome.add_metric("opportunity_customer_count", total_opportunity, numerator="机会名单客户数")
    risk_unsuitable_share = round(
        sum(item["unsuitable_share"] for item in opportunity_by_product.values()) / max(len(opportunity_by_product), 1), 2
    )
    outcome.add_metric("risk_unsuitable_share", risk_unsuitable_share, numerator="不适配客户数", denominator="客群客户数")

    outcome.evidence = evidence
    charts = [
        build_kpi_spec(
            skill_id,
            skill_version,
            data_as_of,
            "产品缺口诊断概览",
            [
                {"label": "客群客户数", "value": total, "unit": "人", "metric_id": "customer_count"},
                {"label": f"最大缺口产品", "value": primary.get("label", "—"), "unit": "", "metric_id": ""},
                {"label": "该产品缺口", "value": primary.get("gap", 0.0), "unit": "百分点", "metric_id": "product_gap_rate"},
                {"label": "风险适配机会客户", "value": primary.get("opportunity_count", 0), "unit": "人",
                 "metric_id": "opportunity_customer_count"},
            ],
            summary=f"以{context.benchmark_name}为基准，最大缺口出现在{primary.get('label', '—')}",
        ),
        build_category_spec(
            skill_id,
            skill_version,
            data_as_of,
            "产品覆盖缺口排名（百分点）",
            "product_category",
            "gap_points",
            sorted(gap_rows, key=lambda row: row["gap_points"], reverse=True),
            mark="bar",
            orientation="horizontal",
            unit="百分点",
            metric_id="product_gap_rate",
            summary="正值表示目标客群持有率低于基准，数值越大缺口越明显",
            annotations=[
                ChartAnnotation(
                    type="highlight",
                    category=primary.get("label", ""),
                    text=f"缺口最大：{primary.get('gap', 0.0)} 个百分点",
                    evidence_id="EV_B101",
                )
            ],
            transforms=[],
        ),
        build_category_spec(
            skill_id,
            skill_version,
            data_as_of,
            "风险适配机会客户数（按产品）",
            "product_category",
            "opportunity_count",
            merge_small_counts(
                sorted(gap_rows, key=lambda row: row["opportunity_count"], reverse=True),
                "product_category",
                "opportunity_count",
                min_group,
            )[0],
            mark="bar",
            orientation="horizontal",
            unit="人",
            metric_id="opportunity_customer_count",
            summary="已扣除风险不适配、已持有与营销排除客户的净机会客户数；低于最小样本阈值的产品已合并为“其他”",
            intent="ranking",
            chart_skill="chart.intent.show_ranking",
        ),
        build_table_spec(
            skill_id, skill_version, data_as_of, "产品缺口与机会明细",
            [
                {"field": "产品类别", "semantic_type": "category", "role": "dimension"},
                {"field": "目标客群持有率", "semantic_type": "percentage", "role": "measure", "unit": "percent"},
                {"field": f"{context.benchmark_name}持有率", "semantic_type": "percentage", "role": "measure", "unit": "percent"},
                {"field": "缺口（百分点）", "semantic_type": "measure", "role": "measure", "metric_id": "product_gap_rate"},
                {"field": "风险适配机会客户数", "semantic_type": "count", "role": "measure", "unit": "人",
                 "metric_id": "opportunity_customer_count"},
                {"field": "最低适配等级", "semantic_type": "category", "role": "dimension"},
            ],
            merge_small_counts(gap_table, "产品类别", "风险适配机会客户数", min_group)[0],
            summary="仅用于营销机会识别；最低适配等级来自产品风险适配规则，低于最小样本阈值的产品已合并为“其他”",
            intent="table",
            chart_skill="chart.intent.show_ranking",
        ),
    ]
    if heat_rows:
        charts.append(
            build_heatmap_spec(
                skill_id,
                skill_version,
                data_as_of,
                "产品 × 风险等级 机会客户占比热力图",
                heat_rows,
                x_field="risk_level",
                y_field="product_category",
                value_field="opportunity_rate",
                summary="颜色越深表示该风险等级下未持有且适配该产品的客户占比越高；低于最小样本的分组已抑制",
            )
        )

    cards = [
        InsightCard(
            card_id="IC_GAP_01",
            title=f"最大配置缺口出现在{primary.get('label', '—')}",
            fact=InsightFact(
                text=f"目标客群{primary.get('label', '—')}持有率 {primary.get('audience_rate', 0.0)}%，"
                f"{context.benchmark_name}为 {primary.get('benchmark_rate', 0.0)}%",
                metric_ids=["product_gap_rate"],
                evidence_ids=["EV_B101"],
            ),
            benchmark=InsightBenchmark(
                text=f"缺口 {primary.get('gap', 0.0)} 个百分点（{'高于' if primary.get('gap', 0) >= MIN_GAP_POINTS else '低于'}显著阈值 {MIN_GAP_POINTS} 个百分点）",
                benchmark_id=context.benchmark_id,
                benchmark_name=context.benchmark_name,
                evidence_ids=["EV_B101"],
            ),
            diagnosis=InsightDiagnosis(
                text="缺口由持有状态与风险适配共同决定，属于可通过合规营销弥补的配置深度不足",
                type="rule_based_inference",
                confidence=0.9,
            ),
            action=InsightAction(
                eligible_customer_count=primary.get("opportunity_count", 0),
                priority="high" if primary.get("gap", 0) >= MIN_GAP_POINTS else "medium",
                recommendation=f"对 {primary.get('opportunity_count', 0)} 位风险适配客户优先开展产品说明与资金用途确认",
                rule_ids=["PRODUCT_GAP_V1", "RISK_SUITABILITY_V1", "EXCLUSION_V1"],
            ),
            boundary=InsightBoundary(
                text="仅给出机会客户范围，不构成产品推荐；最终适配仍执行现有适当性规则与人工确认",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        )
    ]

    if significant:
        detail = "；".join(f"{item[1]['label']} 缺口 {item[1]['gap']} 个百分点" for item in significant[:4])
        cards.append(
            InsightCard(
                card_id="IC_GAP_02",
                title="显著缺口产品清单",
                fact=InsightFact(
                    text=f"达到显著阈值（≥{MIN_GAP_POINTS} 个百分点）的产品共 {len(significant)} 类：{detail}",
                    metric_ids=["product_gap_rate"],
                    evidence_ids=[f"EV_B1{index:02d}" for index in range(1, min(len(significant), 4) + 1)],
                ),
                benchmark=InsightBenchmark(
                    text=f"比较对象：{context.benchmark_name}（{len(benchmark)} 人）",
                    benchmark_id=context.benchmark_id,
                    benchmark_name=context.benchmark_name,
                    evidence_ids=[f"EV_B1{index:02d}" for index in range(1, min(len(significant), 4) + 1)],
                ),
                diagnosis=InsightDiagnosis(
                    text="缺口集中在同类资产谱系，提示需要按风险等级分层设计沟通口径",
                    type="rule_based_inference",
                    confidence=0.82,
                ),
                action=InsightAction(
                    eligible_customer_count=max(item[1]["opportunity_count"] for item in significant),
                    priority="high",
                    recommendation="将缺口最大的产品作为第一优先沟通主题，其余产品作为组合建议",
                    rule_ids=["PRODUCT_GAP_V1"],
                ),
                boundary=InsightBoundary(
                    text="缺口是群体层面的统计差异，个体是否适合仍需结合适当性与资金用途判断",
                    data_as_of=data_as_of,
                    sample_size=total,
                ),
                provenance=prov,
            )
        )

    cards.append(
        InsightCard(
            card_id="IC_GAP_03",
            title="风险适配与排除规则的边界",
            fact=InsightFact(
                text=f"平均 {risk_unsuitable_share}% 的客户风险等级低于对应产品的最低适配等级；"
                f"{len(excluded_rows)} 人命中营销排除规则",
                metric_ids=["risk_unsuitable_share", "excluded_customer_share"],
                evidence_ids=["EV_B01"],
            ),
            benchmark=None,
            diagnosis=InsightDiagnosis(
                text="风险不适配与排除规则共同收窄了可触达范围，未做该收敛的机会数量会显著高估",
                type="descriptive",
                confidence=0.95,
            ),
            action=InsightAction(
                eligible_customer_count=len(eligible_rows),
                priority="medium",
                recommendation="触达前复核对接触限制与客户偏好，避免重复打扰",
                rule_ids=["RISK_SUITABILITY_V1", "EXCLUSION_V1"],
            ),
            boundary=InsightBoundary(
                text="风险等级与排除标志为时点值，触达前需以最新适当性评估为准",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        )
    )

    outcome.insight_cards = cards
    outcome.charts = charts
    outcome.diagnostics = diagnostics + [
        {"level": "info", "code": "PRODUCT_GAP_OK", "message": f"完成 {len(PRODUCT_DEFINITIONS)} 类产品的缺口诊断"}
    ]
    outcome.payload = {
        "gap_ranking": [
            {
                "product": item[1]["label"],
                "gap_points": item[1]["gap"],
                "opportunity_count": item[1]["opportunity_count"],
                "min_rating": item[1]["min_rating"],
                "significant": item[1]["gap"] >= MIN_GAP_POINTS,
            }
            for item in ranked
        ],
        "risk_level_distribution": risk_counts,
        "heatmap": heat_rows,
        "gap_threshold_points": MIN_GAP_POINTS,
    }
    for card in outcome.insight_cards:
        card.title = sanitize_text(card.title)
        card.fact.text = sanitize_text(card.fact.text)
        card.diagnosis.text = sanitize_text(card.diagnosis.text)
    return outcome
