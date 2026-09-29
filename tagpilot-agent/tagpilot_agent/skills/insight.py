"""洞察卡与证据：事实—对比—诊断—行动—边界 五层结构（对齐方案 4.2 / 4.11）。

强制约束：
  * 每张洞察卡必须引用至少一条证据；
  * 禁止泛化结论（“价值较高”“建议加强营销”）——必须给出比较对象、差异幅度或规则依据；
  * 事实与规则推断必须区分（diagnosis.type = rule_based_inference / model_explanation）。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BANNED_PHRASES = (
    "建议加强营销",
    "客户价值较高",
    "可能有理财需求",
    "值得关注",
    "表现良好",
)

DiagnosisType = Literal["rule_based_inference", "model_explanation", "descriptive"]
Priority = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    kind: Literal["metric", "benchmark", "rule", "dataset"]
    metric_id: str = ""
    text: str
    value: float | int | str | None = None
    unit: str = ""
    rule: str = ""
    source: str = ""
    data_as_of: str = ""


class InsightFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    metric_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class InsightBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    benchmark_id: str = ""
    benchmark_name: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class InsightDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    type: DiagnosisType = "rule_based_inference"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class InsightAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible_customer_count: int = 0
    priority: Priority = "medium"
    recommendation: str = ""
    rule_ids: list[str] = Field(default_factory=list)


class InsightBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    data_as_of: str = ""
    sample_size: int = 0


class InsightProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    skill_version: str
    data_as_of: str = ""
    trace_id: str = ""


class InsightCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    title: str
    fact: InsightFact
    benchmark: InsightBenchmark | None = None
    diagnosis: InsightDiagnosis
    action: InsightAction
    boundary: InsightBoundary
    provenance: InsightProvenance

    def referenced_evidence(self) -> set[str]:
        ids = set(self.fact.evidence_ids)
        if self.benchmark:
            ids.update(self.benchmark.evidence_ids)
        return ids


def check_evidence_completeness(cards: list[InsightCard], evidence: list[Evidence]) -> list[str]:
    """证据完整性校验：返回问题列表，空列表表示通过。"""
    problems: list[str] = []
    known = {item.evidence_id: item for item in evidence}
    for card in cards:
        referenced = card.referenced_evidence()
        if not referenced:
            problems.append(f"{card.card_id} 未引用任何证据")
            continue
        missing = sorted(item for item in referenced if item not in known)
        if missing:
            problems.append(f"{card.card_id} 引用了不存在的证据：{', '.join(missing)}")
        for phrase in BANNED_PHRASES:
            if phrase in card.fact.text or phrase in card.diagnosis.text:
                problems.append(f"{card.card_id} 出现泛化结论“{phrase}”")
        if not card.boundary.text:
            problems.append(f"{card.card_id} 缺少适用边界说明")
        if card.benchmark is None and card.diagnosis.type != "descriptive":
            problems.append(f"{card.card_id} 缺少对比基准，但诊断类型为 {card.diagnosis.type}")
    return problems


def metric_evidence(
    evidence_id: str,
    metric_id: str,
    text: str,
    value: float | int | str | None,
    unit: str = "",
    source: str = "",
    data_as_of: str = "",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind="metric",
        metric_id=metric_id,
        text=text,
        value=value,
        unit=unit,
        source=source,
        data_as_of=data_as_of,
    )


def benchmark_evidence(
    evidence_id: str,
    benchmark_id: str,
    text: str,
    value: float | int | None = None,
    unit: str = "",
    data_as_of: str = "",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind="benchmark",
        metric_id=benchmark_id,
        text=text,
        value=value,
        unit=unit,
        source="基准客群聚合",
        data_as_of=data_as_of,
    )


def rule_evidence(evidence_id: str, rule: str, text: str, value: float | int | None = None) -> Evidence:
    return Evidence(evidence_id=evidence_id, kind="rule", rule=rule, text=text, value=value)


def sanitize_text(text: str) -> str:
    """轻量清洗：压缩空白、去掉可能的 HTML，避免洞察文本被注入。"""
    cleaned = re.sub(r"<[^>]{1,200}>", "", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()
