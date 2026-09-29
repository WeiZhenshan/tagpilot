"""SkillManifest 契约与校验（对齐方案 4.6）。

Manifest 是 Skill 的身份与治理契约：输入、指标、前置条件、执行器、输出 Schema、
图表规范、校验器、评测集与版本状态。任何字段缺失都会在注册时被拒绝。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SkillCategory = Literal["fact", "diagnostic", "action"]
SkillLayer = Literal["L1", "L2", "L3"]
SkillStatus = Literal["draft", "published", "deprecated", "offline"]
BenchmarkType = Literal["ALL_BRANCH", "SAME_AUM_BAND", "SAME_RISK_LEVEL"]

SKILL_ID_PATTERN = r"^[a-z][a-z0-9_]{2,47}$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"

# 允许的校验器与图表意图（白名单，防止 Manifest 携带未实现的契约）
ALLOWED_VALIDATORS = {
    "metric_reconciliation",
    "small_sample_suppression",
    "risk_suitability_check",
    "evidence_completeness",
    "chart_spec_validation",
    "accessibility_validation",
    "exclusion_rule_check",
    "benchmark_applicability",
}

ALLOWED_CHART_SKILLS = {
    "chart.intent.compare_categories",
    "chart.intent.show_trend",
    "chart.intent.show_composition",
    "chart.intent.show_distribution",
    "chart.intent.show_correlation",
    "chart.intent.show_conversion",
    "chart.intent.show_contribution",
    "chart.intent.show_ranking",
    "chart.compose.audience_overview",
    "chart.compose.product_gap",
    "chart.compose.marketing_funnel",
}

ALLOWED_MARKS = {
    "kpi", "table", "bar", "line", "area", "stacked_bar", "pie",
    "histogram", "scatter", "heatmap", "funnel", "waterfall", "treemap",
}

OPERATOR_WHITELIST = {"builtin"}


class Preconditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_customer_count: int = Field(default=20, ge=1, le=10000)
    max_data_age_days: int = Field(default=2, ge=0, le=30)
    required_permissions: list[str] = Field(default_factory=list, max_length=20)


class ExecutorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["builtin"] = "builtin"
    operation: str = Field(min_length=2, max_length=64)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class VisualizationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_skill: str = Field(min_length=4, max_length=64)
    preferred_mark: str = Field(min_length=2, max_length=32)


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(pattern=SKILL_ID_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    name: str = Field(min_length=2, max_length=64)
    category: SkillCategory
    layer: SkillLayer
    owner: str = Field(min_length=2, max_length=64)
    status: SkillStatus = "draft"
    description: str = Field(min_length=10, max_length=500)

    applicable_objects: list[str] = Field(min_length=1, max_length=10)
    scenario_packs: list[str] = Field(default_factory=list, max_length=10)
    required_inputs: list[str] = Field(min_length=1, max_length=20)
    required_metrics: list[str] = Field(min_length=1, max_length=40)

    preconditions: Preconditions = Field(default_factory=Preconditions)
    executor: ExecutorSpec
    output_schema: str = Field(min_length=3, max_length=64)

    default_benchmark: BenchmarkType = "ALL_BRANCH"
    allowed_benchmarks: list[BenchmarkType] = Field(default_factory=lambda: ["ALL_BRANCH"], min_length=1)

    visualizations: list[VisualizationSpec] = Field(min_length=1, max_length=10)
    validators: list[str] = Field(min_length=1, max_length=20)
    evaluation_suite: str = Field(min_length=3, max_length=64)
    human_review_required: bool = False

    @field_validator("allowed_benchmarks")
    @classmethod
    def _dedupe_benchmarks(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen

    def summary(self) -> dict:
        """列表页使用的轻量摘要，不外泄完整执行细节。"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "category": self.category,
            "layer": self.layer,
            "version": self.version,
            "status": self.status,
            "owner": self.owner,
            "description": self.description,
            "applicable_objects": list(self.applicable_objects),
            "default_benchmark": self.default_benchmark,
            "required_permissions": list(self.preconditions.required_permissions),
            "human_review_required": self.human_review_required,
        }


def validate_manifest(manifest: SkillManifest) -> tuple[list[str], list[str]]:
    """深度校验 Manifest；返回 (errors, warnings)。errors 非空即不可注册。"""
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.default_benchmark not in manifest.allowed_benchmarks:
        errors.append("default_benchmark 必须包含在 allowed_benchmarks 中")

    if not manifest.preconditions.required_permissions:
        errors.append("preconditions.required_permissions 不能为空：Skill 必须声明最小权限")

    if manifest.executor.type not in OPERATOR_WHITELIST:
        errors.append(f"executor.type 不在白名单内：{manifest.executor.type}")

    unknown_validators = [item for item in manifest.validators if item not in ALLOWED_VALIDATORS]
    if unknown_validators:
        errors.append("存在未实现的校验器：" + "、".join(unknown_validators))

    if "evidence_completeness" not in manifest.validators:
        errors.append("validators 必须包含 evidence_completeness：洞察结论必须有证据")

    if "small_sample_suppression" not in manifest.validators:
        errors.append("validators 必须包含 small_sample_suppression：小样本必须抑制")

    for item in manifest.visualizations:
        if item.chart_skill not in ALLOWED_CHART_SKILLS:
            errors.append(f"visualizations 引用了未注册的图表 Skill：{item.chart_skill}")
        if item.preferred_mark not in ALLOWED_MARKS:
            errors.append(f"visualizations.preferred_mark 不在白名单内：{item.preferred_mark}")

    if manifest.layer == "L3" and "risk_suitability_check" not in manifest.validators:
        errors.append("L3 行动类 Skill 必须声明 risk_suitability_check")

    if not re.fullmatch(SKILL_ID_PATTERN, manifest.skill_id):
        errors.append("skill_id 必须是小写字母开头的下划线标识")

    if manifest.human_review_required is False and manifest.layer == "L3":
        warnings.append("L3 行动类 Skill 建议开启 human_review_required，由业务人工确认后触达")

    if not manifest.scenario_packs:
        warnings.append("未声明 scenario_packs，场景包推荐将无法命中该 Skill")

    if not manifest.evaluation_suite.endswith("_eval_v1") and "_eval_v" not in manifest.evaluation_suite:
        warnings.append("evaluation_suite 建议带版本后缀，便于评测集版本化")

    return errors, warnings
