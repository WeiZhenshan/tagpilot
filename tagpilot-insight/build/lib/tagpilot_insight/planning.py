"""Java 取数前的纯契约准入；只返回声明式查询，不执行查询。"""
from typing import Literal
from .contracts import CohortSnapshot, Contract, Hash, Identifier, MetricBinding, MetricQuery, Text, Version
from .registry import SkillRegistry


class MetricPlan(Contract):
    skill_id: Identifier
    skill_version: Version
    pack_hash: Hash
    snapshot_id: Text
    binding_version: Version
    cohort: CohortSnapshot
    parameters: dict
    status: Literal["READY", "BLOCKED"]
    reasons: list[str]
    queries: list[MetricQuery]


def plan_skill(skill_id: str, cohort: CohortSnapshot, bindings: list[MetricBinding],
               eligible_tag_ids: set[int], parameters: dict | None = None, registry: SkillRegistry | None = None) -> MetricPlan:
    registry = registry or SkillRegistry()
    manifest = registry.get(skill_id)
    resolved = registry.parameters(skill_id, parameters)
    reasons = []
    if not cohort.synthetic and manifest.status != "PUBLISHED":
        reasons.append("技能版本尚未发布")
    if cohort.count < manifest.preconditions.min_sample:
        reasons.append("客群样本不足")
    age = (cohort.reference_date - cohort.data_as_of).days
    if not 0 <= age <= manifest.preconditions.max_stale_days:
        reasons.append("数据日期未来或超过时效")
    index = {binding.metric: binding for binding in bindings}
    if len(index) != len(bindings):
        reasons.append("指标绑定标识重复")
    # P0 只发完整取数计划；可选依赖缺失时的品类降级由 P3 实现。
    for metric in manifest.metrics:
        binding = index.get(metric)
        if binding is None:
            reasons.append("指标待绑定：" + metric)
        elif binding.status != "PUBLISHED" or binding.snapshot_id != cohort.snapshot_id or binding.version != cohort.binding_version:
            reasons.append("指标绑定未发布或版本不一致：" + metric)
        elif binding.tag_id not in eligible_tag_ids:
            reasons.append("依赖标签无权限：" + metric)
    return MetricPlan(skill_id=skill_id, skill_version=manifest.version, pack_hash=registry.hash(skill_id),
                      snapshot_id=cohort.snapshot_id, binding_version=cohort.binding_version,
                      cohort=cohort, parameters=resolved,
                      status="BLOCKED" if reasons else "READY", reasons=reasons,
                      queries=[] if reasons else manifest.queries)
