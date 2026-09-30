"""P0 叙述出口：只接收一次结构化卡片候选，拒绝时保留模板与全部原始数字。"""
from __future__ import annotations

from .contracts import InsightCard, InsightReport
from .guards import REFERENCE, GuardError, validate_report
from .registry import SkillRegistry


def guarded_narration(report: InsightReport, candidates: dict[str, list[dict]],
                      registry: SkillRegistry | None = None, *, published_hashes: dict[str,str] | None = None) -> tuple[InsightReport, bool]:
    registry = registry or SkillRegistry()
    validate_report(report, registry,published_hashes=published_hashes)
    result = report.model_copy(deep=True)
    try:
        if set(candidates) != {s.skill_id for s in report.results if s.status != "BLOCKED"}:
            raise ValueError("叙述候选必须与成功的技能结果对应")
        for skill in result.results:
            if skill.status == "BLOCKED":
                continue
            cards = [InsightCard.model_validate(card) for card in candidates[skill.skill_id]]
            if [c.id for c in cards] != [c.id for c in skill.cards]:
                raise ValueError("叙述不能添加或删除事实卡")
            # LLM 只改语句，不改证据、诊断依据或行动范围。
            for before, after in zip(skill.cards, cards):
                if before.boundary != after.boundary or before.diagnosis.basis != after.diagnosis.basis or before.diagnosis.statistical_evidence != after.diagnosis.statistical_evidence or before.action.population_fact_id != after.action.population_fact_id or before.action.priority != after.action.priority:
                    raise ValueError("叙述不能改变诊断依据、行动范围或证据边界")
                if before.comparison.benchmark_fact_ids != after.comparison.benchmark_fact_ids or before.comparison.difference_fact_ids != after.comparison.difference_fact_ids:
                    raise ValueError("叙述不能更换基准与差值")
                for field in ("facts", "comparison", "diagnosis", "action"):
                    original, proposed = getattr(before, field), getattr(after, field)
                    if original.fact_ids != proposed.fact_ids or sorted(REFERENCE.findall(original.text)) != sorted(REFERENCE.findall(proposed.text)):
                        raise ValueError("叙述只能改写文字，不能增加、删除或替换事实引用")
            skill.cards = cards
        validate_report(result, registry,published_hashes=published_hashes)
        return result, True
    except (ValueError, GuardError):
        fallback = report.model_copy(deep=True)
        for skill in fallback.results:
            if skill.status == "COMPLETE":
                skill.level = "L3"
                skill.reasons = [*skill.reasons, "叙述未通过 Guard，已回退确定性模板；数字与图表保持原结果。"]
            elif skill.status == "PARTIAL":
                skill.reasons = [*skill.reasons, "叙述未通过 Guard，已回退确定性模板。"]
        validate_report(fallback, registry,published_hashes=published_hashes)
        return fallback, False
