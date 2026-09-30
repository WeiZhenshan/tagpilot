"""Java 取数前的纯契约准入；只返回声明式查询，不执行查询。"""
from typing import Literal
from pydantic import Field
from .contracts import CohortSnapshot, Contract, Hash, Identifier, MetricBinding, MetricQuery, Text, Version
from .registry import SkillRegistry
from .metrics import METRICS


class MetricPlan(Contract):
    skill_id: Identifier
    skill_version: Version
    pack_hash: Hash
    snapshot_id: Text
    binding_version: Version
    cohort: CohortSnapshot
    parameters: dict
    partial_reasons: list[str] = Field(default_factory=list)
    status: Literal["READY", "BLOCKED"]
    reasons: list[str]
    queries: list[MetricQuery]


def plan_skill(skill_id: str, cohort: CohortSnapshot, bindings: list[MetricBinding],
               eligible_tag_ids: set[int], parameters: dict | None = None, registry: SkillRegistry | None = None, published_hash: str | None = None) -> MetricPlan:
    registry = registry or SkillRegistry()
    manifest = registry.get(skill_id)
    resolved = registry.parameters(skill_id, parameters)
    if skill_id=="product_holding_gap" and "categories" not in (parameters or {}):
        bound_categories=[c for c in resolved["categories"] if any(b.metric=="product_holding" and b.category==c for b in bindings)]
        if bound_categories:resolved["categories"]=bound_categories
    reasons = []
    if not cohort.synthetic and published_hash != registry.hash(skill_id):
        reasons.append("技能版本尚未发布")
    if cohort.count < manifest.preconditions.min_sample:
        reasons.append("客群样本不足")
    age = (cohort.reference_date - cohort.data_as_of).days
    if not 0 <= age <= manifest.preconditions.max_stale_days:
        reasons.append("数据日期未来或超过时效")
    index = {(binding.metric, binding.category): binding for binding in bindings}
    if len(index) != len(bindings):
        reasons.append("指标绑定标识重复")
    partial = []
    categories = resolved.get("categories", [])
    for metric in manifest.metrics:
        # 客户数由Java按当前方案实时统计；适当性缺配置时机会计算返回MISSING。
        if metric in {"suitability", "customer_count"}:
            continue
        keys = [(metric, c) for c in categories] if metric == "product_holding" else [(metric, None)]
        if metric == "asset_holder":
            keys = [(metric,c) for c in ("liquid","fixed","investment")]
        for key in keys:
            binding = index.get(key)
            if binding is None:
                (partial if metric=="product_holding" else reasons).append("指标待绑定：" + metric + (":" + key[1] if key[1] else ""))
            elif binding.status != "PUBLISHED" or binding.snapshot_id != cohort.snapshot_id or binding.version != cohort.binding_version:
                reasons.append("指标绑定未发布或版本不一致：" + metric)
            elif binding.unit != METRICS[metric].unit:
                reasons.append("指标单位与语义层不一致："+metric)
            elif binding.tag_id not in eligible_tag_ids:
                reasons.append("依赖标签无权限：" + metric)
    if skill_id=="product_holding_gap" and not any(b.metric=="product_holding" for b in bindings):reasons.append("没有已绑定的产品持有品类")
    return MetricPlan(skill_id=skill_id, skill_version=manifest.version, pack_hash=registry.hash(skill_id),
                      snapshot_id=cohort.snapshot_id, binding_version=cohort.binding_version,
                      cohort=cohort, parameters=resolved,
                      status="BLOCKED" if reasons else "READY", reasons=reasons, partial_reasons=partial,
                      queries=[] if reasons else manifest.queries)
