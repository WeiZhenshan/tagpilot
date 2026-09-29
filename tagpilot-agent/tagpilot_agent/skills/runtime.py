"""Skill Runtime：受控执行链（对齐方案 4.7 与 4.13）。

执行顺序固定为：
    技能存在与发布状态 → 权限 → 参数与基准白名单 → 数据就绪 → 确定性执行
    → 结果 Schema 校验 → 数值对账 → 小样本抑制 → 证据完整性 → 图表规范校验 → 留痕

任何一步不通过都不会进入下一步，也不会把未校验的结果交给展示层或模型。
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date, datetime

from tagpilot_agent.skills.chartspec import validate_chart_spec
from tagpilot_agent.skills.contract import SkillBlocked, SkillContext, SkillOutcome
from tagpilot_agent.skills.datasource import BENCHMARK_LABELS, AudienceDataSource, SkillDataNotReady
from tagpilot_agent.skills.insight import check_evidence_completeness
from tagpilot_agent.skills.registry import SkillRegistry, SkillRegistryError

VALID_BENCHMARKS = tuple(BENCHMARK_LABELS)

_EXECUTOR_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="skill-run")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _validation(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


class SkillRuntime:
    def __init__(self, registry: SkillRegistry, source: AudienceDataSource):
        self.registry = registry
        self.source = source

    # ---------- 主流程 ----------

    def run(self, skill_id: str, request: dict) -> dict:
        started = time.monotonic()
        run_id = "run_" + uuid.uuid4().hex[:16]
        trace_id = str(request.get("trace_id") or uuid.uuid4().hex)
        operator_id = str(request.get("operator_id") or "")
        operator_name = str(request.get("operator_name") or "")
        permissions = [str(item) for item in (request.get("permissions") or [])]
        audience_id = str(request.get("audience_id") or "")
        audience_name = str(request.get("audience_name") or "")

        def fail(status_code: int, reason: str, validations: list | None = None):
            self.registry.record_run(
                {
                    "run_id": run_id,
                    "skill_id": skill_id,
                    "skill_version": version_holder.get("version", ""),
                    "audience_id": audience_id,
                    "audience_name": audience_name,
                    "customer_count": len(member_ids),
                    "status": "blocked",
                    "blocked_reason": reason,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "operator_id": operator_id,
                    "operator_name": operator_name,
                    "trace_id": trace_id,
                }
            )
            raise SkillBlocked(reason, code="blocked", status_code=status_code, validations=validations or [])

        version_holder: dict = {}
        member_ids = [str(item) for item in (request.get("member_ids") or []) if str(item or "").strip()]

        # 1. 技能存在性与发布状态
        try:
            skill = self.registry.get(skill_id, request.get("version") or None)
        except SkillRegistryError as exc:
            raise SkillBlocked(str(exc), code="not_found", validations=[]) from exc
        manifest = self.registry.effective_manifest(skill_id, skill.manifest.version)
        version_holder["version"] = manifest.version
        if manifest.status != "published":
            fail(409, f"技能当前状态为 {manifest.status}，未发布不可执行；请先在技能管理中发布")

        # 2. 权限（"*" 与 RuoYi 约定的 "*:*:*" 均视为通配）
        caller = set(permissions)
        if not (caller & {"*", "*:*:*"}) and not set(manifest.preconditions.required_permissions) <= caller:
            missing = sorted(set(manifest.preconditions.required_permissions) - caller)
            fail(403, "当前用户缺少执行该技能所需权限：" + "、".join(missing))

        # 3. 参数与基准白名单
        benchmark_type = str(request.get("benchmark_type") or manifest.default_benchmark).upper()
        if benchmark_type not in VALID_BENCHMARKS:
            fail(422, f"基准类型不合法：{benchmark_type}")
        if benchmark_type not in manifest.allowed_benchmarks:
            fail(422, f"技能 {skill_id} 不支持基准 {benchmark_type}，可选：" + "、".join(manifest.allowed_benchmarks))
        if not member_ids:
            fail(422, "客群成员为空：请先在客群管理中运行客群或检查规则有效性")

        as_of_date = str(request.get("as_of_date") or "").strip() or date.today().isoformat()
        try:
            datetime.fromisoformat(as_of_date)
        except ValueError:
            fail(422, f"数据日期格式不合法：{as_of_date}")

        # 4. 数据就绪
        validations: list[dict] = []
        try:
            audience_rows = self.source.fetch_audience(member_ids)
        except SkillDataNotReady as exc:
            fail(422, str(exc))
        actual_count = len(audience_rows)
        if actual_count == 0:
            fail(422, "客群成员在标签宽表中无匹配记录：规则可能已失效或数据未加工")
        independent_count = 0
        try:
            independent_count = self.source.count_audience(member_ids)
        except SkillDataNotReady:
            independent_count = actual_count
        reconciled = abs(independent_count - actual_count) <= max(1, int(actual_count * 0.001))
        validations.append(
            _validation(
                "metric_reconciliation",
                reconciled,
                f"客群成员 {len(member_ids)} 条，宽表命中 {actual_count} 条，独立计数 {independent_count} 条",
            )
        )
        if not reconciled:
            fail(422, "客群成员数与标签宽表不一致，数据未就绪或存在重复客户号")

        min_count = manifest.preconditions.min_customer_count
        sample_ok = actual_count >= min_count
        validations.append(
            _validation(
                "small_sample_suppression",
                sample_ok,
                f"客群客户数 {actual_count}，最小样本阈值 {min_count}",
            )
        )
        if not sample_ok:
            fail(422, f"客群客户数 {actual_count} 低于最小样本阈值 {min_count}，已阻止执行以保护个体隐私")

        benchmark_rows: list[dict] = []
        try:
            benchmark_rows = self.source.fetch_scope(benchmark_type, audience_rows)
        except SkillDataNotReady as exc:
            fail(422, f"基准客群取数失败：{exc}")
        benchmark_rows = [row for row in benchmark_rows if row.get("cust_id") not in set(member_ids)]
        if not benchmark_rows:
            benchmark_rows = audience_rows
            validations.append(
                _validation("benchmark_applicability", False, "基准客群为空，已回退为目标客群自身（差异将为 0）")
            )
        else:
            validations.append(
                _validation(
                    "benchmark_applicability",
                    True,
                    f"基准 {BENCHMARK_LABELS[benchmark_type]} 共 {len(benchmark_rows)} 人",
                )
            )

        context = SkillContext(
            manifest=manifest,
            audience_id=audience_id,
            audience_name=audience_name,
            as_of_date=as_of_date,
            benchmark_type=benchmark_type,
            benchmark_name=BENCHMARK_LABELS[benchmark_type],
            benchmark_id=benchmark_type,
            trace_id=trace_id,
            params=dict(request.get("params") or {}),
            audience_rows=audience_rows,
            benchmark_rows=benchmark_rows,
        )

        # 5. 确定性执行（带超时）
        future = _EXECUTOR_POOL.submit(skill.executor, context)
        try:
            outcome: SkillOutcome = future.result(timeout=manifest.executor.timeout_seconds)
        except FutureTimeout:
            fail(422, f"技能执行超时（>{manifest.executor.timeout_seconds}s），已终止且不返回部分结果")
        except SkillBlocked as exc:
            fail(422, exc.reason, exc.validations)
        except Exception as exc:  # 执行器内部错误：不暴露堆栈，保留可诊断信息
            fail(422, f"技能执行失败：{type(exc).__name__}: {exc}")

        # 6. 结果 Schema 校验
        schema_problems: list[str] = []
        if not outcome.metrics:
            schema_problems.append("未产出任何指标")
        if not outcome.insight_cards:
            schema_problems.append("未产出洞察卡")
        if not outcome.charts:
            schema_problems.append("未产出图表规范")
        validations.append(
            _validation(
                "output_schema",
                not schema_problems,
                "；".join(schema_problems) or f"输出 {len(outcome.metrics)} 个指标、{len(outcome.insight_cards)} 张洞察卡、{len(outcome.charts)} 个图表",
            )
        )

        # 7. 业务规则交叉校验（风险适配与排除规则）
        if "risk_suitability_check" in manifest.validators:
            gap_records = outcome.payload.get("gap_ranking") or []
            missing_rating = [item for item in gap_records if not item.get("min_rating")]
            declares_exclusion = "excluded_customer_share" in outcome.metrics
            declares_rule = bool(outcome.payload.get("rule_id"))
            passed = (not missing_rating) and (declares_exclusion or declares_rule)
            validations.append(
                _validation(
                    "risk_suitability_check",
                    bool(passed),
                    "机会客户均经最低风险适配等级过滤，并输出不适配占比或显式排序规则"
                    if passed
                    else "缺少风险适配等级信息，无法证明机会客户经过适当性过滤",
                )
            )
        if "exclusion_rule_check" in manifest.validators:
            passed = "excluded_customer_share" in outcome.metrics
            validations.append(
                _validation(
                    "exclusion_rule_check",
                    passed,
                    f"营销排除客户占比 {outcome.metrics.get('excluded_customer_share', {}).get('value', 0)}%，已从机会名单剔除"
                    if passed
                    else "未输出排除规则校验结果",
                )
            )

        # 8. 证据完整性
        evidence_problems = check_evidence_completeness(outcome.insight_cards, outcome.evidence)
        validations.append(
            _validation(
                "evidence_completeness",
                not evidence_problems,
                "；".join(evidence_problems) or f"{len(outcome.insight_cards)} 张洞察卡全部引用有效证据",
            )
        )
        if evidence_problems:
            fail(422, "证据完整性校验未通过：" + "；".join(evidence_problems), validations)

        # 9. 图表规范与数据一致性校验
        chart_results: list[dict] = []
        for spec in outcome.charts:
            for result in validate_chart_spec(
                spec, outcome.chart_expectations.get(spec.chart_id), min_group_size=min_count
            ):
                chart_results.append(result.model_dump())
        chart_problems = [item for item in chart_results if not item["passed"]]
        validations.append(
            _validation(
                "chart_spec_validation",
                not chart_problems,
                "；".join(f"{item['name']}:{item['detail']}" for item in chart_problems)
                or f"{len(outcome.charts)} 个图表规范通过 Schema、数据、语义、可读性、安全与渲染校验",
            )
        )
        accessibility_problems = [
            spec.chart_id
            for spec in outcome.charts
            if not spec.accessibility.summary.strip() or not spec.accessibility.data_table
        ]
        validations.append(
            _validation(
                "accessibility_validation",
                not accessibility_problems,
                "全部图表提供文字摘要与可展开数据表"
                if not accessibility_problems
                else "以下图表缺少无障碍替代文本或数据表：" + "、".join(accessibility_problems),
            )
        )

        duration_ms = int((time.monotonic() - started) * 1000)
        response = {
            "run_id": run_id,
            "skill_id": skill_id,
            "skill_version": manifest.version,
            "status": "succeeded",
            "blocked_reason": None,
            "started_at": _now(),
            "duration_ms": duration_ms,
            "audience": {
                "audience_id": audience_id,
                "name": audience_name,
                "customer_count": actual_count,
                "as_of_date": as_of_date,
                "benchmark_type": benchmark_type,
                "benchmark_name": context.benchmark_name,
                "benchmark_customer_count": len(benchmark_rows),
            },
            "metrics": outcome.metrics,
            "insight_cards": [card.model_dump() for card in outcome.insight_cards],
            "charts": [spec.model_dump() for spec in outcome.charts],
            "evidence": [item.model_dump() for item in outcome.evidence],
            "diagnostics": outcome.diagnostics,
            "validations": validations,
            "chart_validations": chart_results,
            "payload": outcome.payload,
            "data_as_of": as_of_date,
            "trace_id": trace_id,
        }
        self.registry.record_run(
            {
                "run_id": run_id,
                "skill_id": skill_id,
                "skill_version": manifest.version,
                "audience_id": audience_id,
                "audience_name": audience_name,
                "customer_count": actual_count,
                "status": "succeeded",
                "blocked_reason": "",
                "duration_ms": duration_ms,
                "operator_id": operator_id,
                "operator_name": operator_name,
                "trace_id": trace_id,
            }
        )
        return response
