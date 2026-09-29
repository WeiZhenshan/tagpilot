"""显式合成预览入口；生产路径不得把缺失数据替换为 fixture。"""
import json
from pathlib import Path

from .contracts import InsightReport
from .guards import validate_report
from .registry import SkillRegistry


def synthetic_golden_report() -> InsightReport:
    data = json.loads((Path(__file__).parent / "fixtures/golden_pack.json").read_text(encoding="utf-8"))
    if data["cohort"]["synthetic"] is not True:
        raise ValueError("fixtures 必须明确标为合成数据")
    registry = SkillRegistry()
    # fixture 中保存零占位 hash，导出时绑定当前代码包；不是线上发布记录。
    for skill in data["results"]:
        skill["pack_hash"] = registry.hash(skill["skill_id"])
    return validate_report(InsightReport.model_validate(data), registry)
