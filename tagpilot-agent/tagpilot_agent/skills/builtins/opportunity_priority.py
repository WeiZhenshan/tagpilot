"""Skill C：营销机会优先级排序（L3 行动决策）。

用可解释加权规则把客户分入高/中/低三档机会，并给出入档原因、建议渠道与排除原因。
第一版不训练预测模型；权重与惩罚项集中在 metrics.OPPORTUNITY_WEIGHTS，可审计、可回归。

安全约束：
  * 名单本身不由本 Skill 直接输出给模型或前端，只输出分层规模、归因分布与规则定义；
    实际触达名单由业务服务按同一规则生成，并继承审批与合规校验。
"""

from __future__ import annotations

from datetime import date, datetime

# 漏斗至少要保留的层级数，少于该值时不产出漏斗图
MIN_FUNNEL_STAGES = 2

from tagpilot_agent.skills.chartspec import (
    ChartAnnotation,
    build_category_spec,
    build_funnel_spec,
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
    OPPORTUNITY_BANDS,
    OPPORTUNITY_PENALTY,
    OPPORTUNITY_WEIGHTS,
    PRODUCT_DEFINITIONS,
    avg_of,
    is_excluded,
    is_online_reachable,
    merge_small_counts,
    product_available,
    share,
)

RULE_ID = "OPP_RULE_V1"


def _percentile_ranks(values: list[float]) -> list[float]:
    """返回每个元素在数组中的百分位（0-100），用于把绝对金额转成可比得分。"""
    if not values:
        return []
    ordered = sorted(values)
    size = len(ordered)
    ranks: list[float] = []
    import bisect

    for value in values:
        position = bisect.bisect_right(ordered, value)
        ranks.append(round(position * 100.0 / size, 2))
    return ranks


def _recency_score(last_date) -> float:
    if not last_date:
        return 20.0
    if isinstance(last_date, datetime):
        last_date = last_date.date()
    if isinstance(last_date, str):
        try:
            last_date = date.fromisoformat(last_date[:10])
        except ValueError:
            return 20.0
    if not isinstance(last_date, date):
        return 20.0
    days = (date.today() - last_date).days
    if days <= 7:
        return 100.0
    if days <= 30:
        return 70.0
    if days <= 90:
        return 40.0
    return 10.0


def run(context: SkillContext) -> SkillOutcome:
    audience = context.audience_rows
    benchmark = context.benchmark_rows
    total = len(audience)
    data_as_of = context.as_of_date
    skill_id, skill_version = context.manifest.skill_id, context.manifest.version
    prov = InsightProvenance(
        skill_id=skill_id, skill_version=skill_version, data_as_of=data_as_of, trace_id=context.trace_id
    )
    outcome = SkillOutcome()
    evidence: list = []
    diagnostics: list[dict] = []

    if not audience:
        return outcome

    # 营销排除规则：黑名单与欺诈预警客户不进入机会名单（对齐方案 4.7 与 4.14）
    excluded_rows = [row for row in audience if is_excluded(row)]
    excluded_share = share(len(excluded_rows), total)
    eligible_rows = [row for row in audience if not is_excluded(row)]
    outcome.add_metric("excluded_customer_share", excluded_share, numerator="排除客户数", denominator="客群客户数")
    if not eligible_rows:
        diagnostics.append(
            {"level": "warn", "code": "ALL_EXCLUDED", "message": "客群客户全部命中营销排除规则，无可触达机会客户"}
        )
        outcome.evidence = [
            rule_evidence(
                RULE_ID, RULE_ID,
                "机会分 = 价值×0.30 + 需求事件×0.25 + 产品缺口×0.20 + 历史响应×0.15 + 渠道可达×0.10 − 风险/打扰惩罚",
                0,
            ),
            rule_evidence("EV_C01", "EXCLUSION_V1", "全部客户命中营销排除规则，机会名单为空", 0),
        ]
        outcome.insight_cards = [
            InsightCard(
                card_id="IC_OPP_00",
                title="无可触达机会客户",
                fact=InsightFact(text=f"{total} 位客户全部命中营销排除规则", metric_ids=["excluded_customer_share"],
                                 evidence_ids=["EV_C01"]),
                benchmark=None,
                diagnosis=InsightDiagnosis(text="排除规则先于机会排序生效，未做该收敛的机会数量会显著高估", type="descriptive", confidence=1.0),
                action=InsightAction(eligible_customer_count=0, priority="low",
                                     recommendation="请复核客群规则或调整排除条件后重跑", rule_ids=["EXCLUSION_V1"]),
                boundary=InsightBoundary(text="排除名单来自黑名单与欺诈预警字段，触达前需再次校验",
                                         data_as_of=data_as_of, sample_size=total),
                provenance=prov,
            )
        ]
        return outcome

    audience = eligible_rows
    audience_total = total
    total = len(audience)

    clv = [float(row.get("clv_score") or 0) for row in audience]
    amount = [float(row.get("transaction_amt_monthly") or 0) for row in audience]
    clv_pct = _percentile_ranks(clv)
    amount_pct = _percentile_ranks(amount)

    scored: list[dict] = []
    for index, row in enumerate(audience):
        available = [product for product in PRODUCT_DEFINITIONS if product_available(product, row)]
        held = [product for product in available if row.get(product["flag"])]
        gap_products = [product for product in available if not row.get(product["flag"])]
        gap_score = (len(gap_products) * 100.0 / len(available)) if available else 0.0

        value_score = round(0.5 * float(row.get("clv_score") or 0) + 0.5 * clv_pct[index], 2)
        event_score = round(0.5 * _recency_score(row.get("last_transaction_date")) + 0.5 * amount_pct[index], 2)
        response_score = float(row.get("cross_sell_index") or 0)
        channel_score = 0.0
        if is_online_reachable(row):
            channel_score += 60.0
        if str(row.get("channel_preference") or "") in {"线上", "全渠道"}:
            channel_score += 25.0
        if float(row.get("online_login_freq_monthly") or 0) > 0:
            channel_score += 15.0
        if not any(row.get(flag) for flag in ("has_credit_card",)) and str(row.get("kyc_status") or "") == "未完成":
            channel_score = max(channel_score - 20.0, 0.0)

        score = (
            OPPORTUNITY_WEIGHTS["value"] * value_score
            + OPPORTUNITY_WEIGHTS["event"] * event_score
            + OPPORTUNITY_WEIGHTS["gap"] * gap_score
            + OPPORTUNITY_WEIGHTS["response"] * response_score
            + OPPORTUNITY_WEIGHTS["channel"] * channel_score
        )

        penalties: list[str] = []
        if not available:
            score -= OPPORTUNITY_PENALTY["risk_mismatch"]
            penalties.append("risk_mismatch:无风险适配产品")
        if int(row.get("counter_visit_freq_quarterly") or 0) >= 6:
            score -= OPPORTUNITY_PENALTY["disturbance"]
            penalties.append("disturbance:近季度柜面接触频繁")
        score = round(max(score, 0.0), 2)

        band = "low"
        for label, threshold in OPPORTUNITY_BANDS:
            if score >= threshold:
                band = label
                break

        top_gap = max(gap_products, key=lambda item: item["min_rating"]) if gap_products else None
        scored.append(
            {
                "band": band,
                "score": score,
                "components": {
                    "value": value_score,
                    "event": event_score,
                    "gap": round(gap_score, 2),
                    "response": response_score,
                    "channel": round(channel_score, 2),
                },
                "penalties": penalties,
                "gap_product": top_gap["label"] if top_gap else "",
                "channel_preference": str(row.get("channel_preference") or "未知"),
                "branch_code": str(row.get("branch_code") or "未知"),
                "cust_segment": str(row.get("cust_segment") or "未知"),
                "held_product_count": len(held),
            }
        )

    band_counts = {label: sum(1 for row in scored if row["band"] == label) for label, _ in OPPORTUNITY_BANDS}
    high_count = band_counts.get("high", 0)
    med_count = band_counts.get("medium", 0)
    low_count = band_counts.get("low", 0)
    penalized = sum(1 for row in scored if row["penalties"])

    outcome.add_metric("opportunity_customer_count", high_count + med_count, numerator="机会分≥45 客户数", denominator="—")
    outcome.add_metric("high_priority_opportunity_count", high_count, numerator="机会分≥70 客户数")
    reachable_share = share(sum(1 for row in audience if is_online_reachable(row)), total)
    outcome.add_metric("channel_reachable_rate", reachable_share, numerator="线上渠道客户数", denominator="可触达客户数")
    benchmark_reachable_share = (
        share(sum(1 for row in benchmark if is_online_reachable(row)), len(benchmark)) if benchmark else 0.0
    )
    if benchmark:
        evidence.append(
            benchmark_evidence(
                "EV_C07", context.benchmark_id,
                f"{context.benchmark_name}线上渠道可达率 {benchmark_reachable_share}%（{len(benchmark)} 人）",
                benchmark_reachable_share, "percent", data_as_of,
            )
        )

    avg_score = avg_of([row["score"] for row in scored])
    evidence.extend(
        [
            rule_evidence(
                RULE_ID, RULE_ID,
                "机会分 = 价值×0.30 + 需求事件×0.25 + 产品缺口×0.20 + 历史响应×0.15 + 渠道可达×0.10 − 风险/打扰惩罚",
                avg_score,
            ),
            metric_evidence("EV_C01", "high_priority_opportunity_count", f"高优先级机会客户 {high_count} 人（机会分≥70）",
                            high_count, "人", RULE_ID, data_as_of),
            metric_evidence("EV_C02", "opportunity_customer_count", f"中高优先级机会客户 {high_count + med_count} 人（机会分≥45）",
                            high_count + med_count, "人", RULE_ID, data_as_of),
            metric_evidence("EV_C03", "channel_reachable_rate", f"线上渠道可达率 {reachable_share}%", reachable_share,
                            "percent", "手机银行/网银/微信银行任一", data_as_of),
            rule_evidence("EV_C04", "DISTURBANCE_V1", f"{penalized} 位客户命中风险或打扰惩罚项，已相应下调机会分", penalized),
            rule_evidence(
                "EV_C06", "EXCLUSION_V1",
                f"营销排除客户 {len(excluded_rows)} 人（{excluded_share}%）不进入机会名单；可触达客户 {total} 人",
                excluded_share,
            ),
        ]
    )

    min_group = context.manifest.preconditions.min_customer_count
    channel_rows_raw = [
        {
            "channel": channel,
            "customer_count": sum(1 for row in scored if row["channel_preference"] == channel and row["band"] == "high"),
            "audience_type": "高优先级机会客户",
        }
        for channel in sorted({row["channel_preference"] for row in scored})
    ]
    channel_rows, merged_channels = merge_small_counts(channel_rows_raw, "channel", "customer_count", min_group)
    if merged_channels:
        diagnostics.append(
            {
                "level": "info",
                "code": "SMALL_GROUP_MERGED",
                "message": f"渠道分布中 {merged_channels} 个分组低于最小样本阈值 {min_group}，已合并为“其他”",
            }
        )
    branch_counter: dict[str, int] = {}
    for row in scored:
        if row["band"] == "high":
            branch_counter[row["branch_code"]] = branch_counter.get(row["branch_code"], 0) + 1
    branch_rows_raw = [
        {"branch": branch, "customer_count": count}
        for branch, count in sorted(branch_counter.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    branch_rows, merged_branches = merge_small_counts(branch_rows_raw, "branch", "customer_count", min_group)
    if merged_branches:
        diagnostics.append(
            {
                "level": "info",
                "code": "SMALL_GROUP_MERGED",
                "message": f"机构分布中 {merged_branches} 个分组低于最小样本阈值 {min_group}，已合并为“其他”",
            }
        )
    if not branch_rows and not channel_rows:
        diagnostics.append({"level": "warn", "code": "NO_OPPORTUNITY", "message": "当前客群中没有符合条件的机会客户"})

    gap_counter: dict[str, int] = {}
    for row in scored:
        if row["band"] in {"high", "medium"} and row["gap_product"]:
            gap_counter[row["gap_product"]] = gap_counter.get(row["gap_product"], 0) + 1
    gap_rows_raw = [
        {"product_category": product, "customer_count": count}
        for product, count in sorted(gap_counter.items(), key=lambda item: item[1], reverse=True)
    ]
    gap_rows, merged_gaps = merge_small_counts(gap_rows_raw, "product_category", "customer_count", min_group)
    if merged_gaps:
        diagnostics.append(
            {
                "level": "info",
                "code": "SMALL_GROUP_MERGED",
                "message": f"缺口产品分布中 {merged_gaps} 个分组低于最小样本阈值 {min_group}，已合并为“其他”",
            }
        )
    # 漏斗逐层收敛，不做“其他”合并：低于阈值的层级直接抑制并说明原因
    funnel_rows: list[dict] = []
    for stage in (
        {"stage": "客群客户", "customer_count": audience_total},
        {"stage": "可触达（排除规则后）", "customer_count": total},
        {"stage": "中高优先级（≥45）", "customer_count": high_count + med_count},
        {"stage": "高优先级（≥70）", "customer_count": high_count},
    ):
        count = stage["customer_count"]
        if 0 < count < min_group:
            diagnostics.append(
                {
                    "level": "info",
                    "code": "SMALL_GROUP_SUPPRESSED",
                    "message": f"漏斗层级“{stage['stage']}”样本 {count} 低于 {min_group}，已抑制",
                }
            )
            continue
        funnel_rows.append(stage)

    charts = [
        build_kpi_spec(
            skill_id,
            skill_version,
            data_as_of,
            "营销机会概览",
            [
                {"label": "客群客户数", "value": audience_total, "unit": "人", "metric_id": "customer_count"},
                {"label": "可触达客户", "value": total, "unit": "人", "metric_id": "excluded_customer_share"},
                {"label": "中高优先级机会", "value": high_count + med_count, "unit": "人",
                 "metric_id": "opportunity_customer_count"},
                {"label": "高优先级机会", "value": high_count, "unit": "人", "metric_id": "high_priority_opportunity_count"},
            ],
            summary=f"客群 {audience_total} 人，排除 {len(excluded_rows)} 人后高优先级 {high_count} 人、中优先级 {med_count} 人，"
            f"平均机会分 {avg_score}",
        ),
        build_funnel_spec(
            skill_id,
            skill_version,
            data_as_of,
            "机会客户分层漏斗",
            funnel_rows,
            summary="按排除规则与机会分阈值逐层收敛，触达优先级自上而下递减；"
            f"低于最小样本阈值 {min_group} 的层级已抑制",
            annotations=[
                ChartAnnotation(type="note", text=f"惩罚项命中 {penalized} 人，已在分数中扣减", evidence_id="EV_C04")
            ],
        )
        if len(funnel_rows) >= MIN_FUNNEL_STAGES
        else None,
    ]
    charts = [chart for chart in charts if chart is not None]
    if channel_rows:
        channel_chart = build_category_spec(
            skill_id,
            skill_version,
            data_as_of,
            "高优先级机会客户的渠道偏好分布",
            "channel",
            "customer_count",
            channel_rows,
            mark="bar",
            orientation="horizontal",
            unit="人",
            metric_id="customer_count",
            summary="用于选择低打扰的触达渠道；线上偏好客户优先使用手机银行消息；低于最小样本阈值的渠道已合并",
            intent="ranking",
            chart_skill="chart.intent.show_ranking",
        )
        charts.append(channel_chart)
        outcome.expect(channel_chart, "customer_count", high_count)
    if gap_rows:
        charts.append(
            build_category_spec(
                skill_id,
                skill_version,
                data_as_of,
                "机会客户的优势缺口产品分布",
                "product_category",
                "customer_count",
                gap_rows,
                mark="bar",
                orientation="horizontal",
                unit="人",
                metric_id="customer_count",
                summary="每位机会客户按其适配范围内缺口层级最高的产品归因一次",
                intent="ranking",
                chart_skill="chart.intent.show_ranking",
            )
        )
    if branch_rows:
        branch_table = build_table_spec(
            skill_id, skill_version, data_as_of, "高优先级机会客户机构分布（Top 10）",
            [
                {"field": "branch", "semantic_type": "category", "role": "dimension"},
                {"field": "customer_count", "semantic_type": "count", "role": "measure", "unit": "人",
                 "metric_id": "customer_count"},
            ],
            branch_rows,
            summary="供管护团队领取任务清单时参考；明细名单由业务服务按同一规则生成",
            intent="table",
            chart_skill="chart.intent.show_ranking",
        )
        charts.append(branch_table)
        outcome.expect(branch_table, "customer_count", high_count)

    cards = [
        InsightCard(
            card_id="IC_OPP_01",
            title="高优先级机会客户与触达建议",
            fact=InsightFact(
                text=f"{high_count} 人进入高优先级（机会分≥70），另有 {med_count} 人进入中优先级；平均机会分 {avg_score}",
                metric_ids=["high_priority_opportunity_count", "opportunity_customer_count"],
                evidence_ids=["EV_C01", "EV_C02"],
            ),
            benchmark=InsightBenchmark(
                text=f"比较对象：{context.benchmark_name}（{len(benchmark)} 人），用于校准机会分的相对位置"
                if benchmark
                else "未启用基准比较",
                benchmark_id=context.benchmark_id if benchmark else "",
                benchmark_name=context.benchmark_name,
                evidence_ids=["EV_C05"] if benchmark else [],
            )
            if benchmark
            else None,
            diagnosis=InsightDiagnosis(
                text="机会分由价值、需求事件、产品缺口、历史响应与渠道可达加权得到，命中风险或打扰惩罚的客户已下调",
                type="rule_based_inference",
                confidence=0.87,
            ),
            action=InsightAction(
                eligible_customer_count=high_count,
                priority="high",
                recommendation=f"建议在入金后 3 个工作日内优先触达高优先级 {high_count} 人，先确认资金用途再提产品方案",
                rule_ids=[RULE_ID, "RISK_SUITABILITY_V1", "EXCLUSION_V1"],
            ),
            boundary=InsightBoundary(
                text="机会分仅用于排序，不构成投资建议；触达需人工确认并执行现有适当性与反打扰规则",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        ),
        InsightCard(
            card_id="IC_OPP_02",
            title="触达渠道与节奏",
            fact=InsightFact(
                text=f"可触达客户线上可达率 {reachable_share}%（{total} 人），渠道偏好分布见图表",
                metric_ids=["channel_reachable_rate"],
                evidence_ids=["EV_C03", "EV_C04"],
            ),
            benchmark=InsightBenchmark(
                text=f"较{context.benchmark_name}线上可达率 {benchmark_reachable_share}% {'高' if reachable_share >= benchmark_reachable_share else '低'} "
                f"{abs(reachable_share - benchmark_reachable_share):.2f} 个百分点",
                benchmark_id=context.benchmark_id,
                benchmark_name=context.benchmark_name,
                evidence_ids=["EV_C07"] if benchmark else [],
            )
            if benchmark
            else None,
            diagnosis=InsightDiagnosis(
                text="线上偏好客户适合消息化触达，柜面接触频繁客户需降低频次以避免打扰",
                type="rule_based_inference",
                confidence=0.8,
            ),
            action=InsightAction(
                eligible_customer_count=high_count,
                priority="high",
                recommendation="手机银行/微信银行客户走线上消息；其余客户由客户经理电话或面谈跟进",
                rule_ids=["CHANNEL_RULE_V1", "DISTURBANCE_V1"],
            ),
            boundary=InsightBoundary(
                text="渠道建议基于客户偏好字段，实际触达仍需遵守行内渠道使用与频次管理规定",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        ),
        InsightCard(
            card_id="IC_OPP_03",
            title="规则与可复现性说明",
            fact=InsightFact(
                text="机会分权重：价值 0.30、需求事件 0.25、产品缺口 0.20、历史响应 0.15、渠道可达 0.10；"
                f"惩罚项：风险不适配 -{OPPORTUNITY_PENALTY['risk_mismatch']:.0f}、打扰 -{OPPORTUNITY_PENALTY['disturbance']:.0f}",
                metric_ids=[],
                evidence_ids=["EV_C04"],
            ),
            benchmark=None,
            diagnosis=InsightDiagnosis(
                text="规则全部显式声明，同数据同版本重复运行结果一致，可用于回归与对账",
                type="descriptive",
                confidence=1.0,
            ),
            action=InsightAction(
                eligible_customer_count=high_count + med_count,
                priority="medium",
                recommendation="如需调整权重，请走 Skill 版本升级与评测门禁，不直接修改线上逻辑",
                rule_ids=[RULE_ID],
            ),
            boundary=InsightBoundary(
                text="历史响应得分使用交叉销售指数近似（当前数据源缺少触达响应明细），引入真实响应数据后需重新校准",
                data_as_of=data_as_of,
                sample_size=total,
            ),
            provenance=prov,
        ),
    ]

    if benchmark:
        evidence.append(
            benchmark_evidence(
                "EV_C05", context.benchmark_id,
                f"{context.benchmark_name}共 {len(benchmark)} 人，用于机会分相对位置校准", len(benchmark), "人", data_as_of,
            )
        )

    outcome.evidence = evidence
    outcome.insight_cards = cards
    outcome.charts = charts
    outcome.diagnostics = diagnostics + [
        {
            "level": "info",
            "code": "OPPORTUNITY_OK",
            "message": f"完成 {total} 位客户的机会分计算（权重版本 {RULE_ID}），名单不由本服务输出",
        }
    ]
    outcome.payload = {
        "rule_id": RULE_ID,
        "weights": OPPORTUNITY_WEIGHTS,
        "penalties": OPPORTUNITY_PENALTY,
        "bands": [{"band": label, "threshold": threshold, "customer_count": band_counts.get(label, 0)}
                  for label, threshold in OPPORTUNITY_BANDS],
        "avg_score": avg_score,
        "channel_distribution": channel_rows,
        "gap_distribution": gap_rows,
        "branch_distribution": branch_rows,
        "customer_list_policy": "明细名单由业务服务按同一规则生成，本 Skill 只输出聚合结果与规则定义",
    }
    for card in outcome.insight_cards:
        card.title = sanitize_text(card.title)
        card.fact.text = sanitize_text(card.fact.text)
        card.diagnosis.text = sanitize_text(card.diagnosis.text)
    return outcome
