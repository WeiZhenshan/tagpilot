"""内容即代码的草稿注册表；发布权属于后续 Java Registry。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .contracts import Manifest

PACK_DIR = Path(__file__).parent / "skills"


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


class SkillRegistry:
    def __init__(self, directory: Path = PACK_DIR):
        self.manifests: dict[str, Manifest] = {}
        self.hashes: dict[str, str] = {}
        for path in sorted(directory.glob("*.yaml")):
            manifest = Manifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            if manifest.id in self.manifests:
                raise ValueError("技能标识重复")
            self.manifests[manifest.id] = manifest
            # 把 Guard / 选图代码也计入包 hash，代码更新不能复用旧评测门禁。
            code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(Path(__file__).parent.glob("*.py"))}
            fixtures = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((Path(__file__).parent / "fixtures").glob("*.json"))}
            self.hashes[manifest.id] = canonical_hash({"manifest": manifest.model_dump(mode="json"), "code": code, "fixtures": fixtures})
        if not self.manifests:
            raise ValueError("洞察技能注册表为空")

    def get(self, skill_id: str) -> Manifest:
        if skill_id not in self.manifests:
            raise ValueError("技能未登记")
        # 返回副本，调用方不能修改注册表中的不可变版本。
        return self.manifests[skill_id].model_copy(deep=True)

    def hash(self, skill_id: str) -> str:
        self.get(skill_id)
        return self.hashes[skill_id]

    def parameters(self, skill_id: str, supplied: dict | None = None) -> dict:
        specs = self.get(skill_id).inputs
        supplied = supplied or {}
        if set(supplied) - set(specs):
            raise ValueError("存在未声明的输入参数")
        result = {}
        for key, spec in specs.items():
            value = supplied.get(key, spec.default)
            if spec.type == "enum" and value not in spec.choices:
                raise ValueError("输入枚举非法")
            if spec.type in {"integer", "number"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("数值参数非法")
                if spec.type == "integer" and not isinstance(value, int):
                    raise ValueError("整数参数非法")
                import math
                if not math.isfinite(value) or (spec.minimum is not None and value < spec.minimum) or (spec.maximum is not None and value > spec.maximum):
                    raise ValueError("输入数值超出范围")
            if spec.type == "string_list" and (not isinstance(value, list) or not value or len(value) > 12 or
                                               any(not isinstance(v, str) or not v or len(v) > 80 for v in value)):
                raise ValueError("输入品类清单非法")
            result[key] = value
        return result


# 只建设本轮需要的 6 原子、6 意图、3 编排。
ATOMIC_CHARTS = ("kpi", "table", "bar", "stacked_bar", "heatmap", "funnel")
INTENTS = {
    "single_value": "kpi",
    "compare_categories": "bar",
    "show_composition": "stacked_bar",
    "show_distribution": "bar",
    "show_matrix": "heatmap",
    "show_conversion": "funnel",
}
DASHBOARDS = {
    "compose.audience_overview": ("single_value", "show_distribution", "show_composition", "compare_categories"),
    "compose.product_gap": ("compare_categories", "show_matrix", "show_conversion", "table"),
    "compose.opportunity_board": ("show_conversion", "show_distribution", "show_composition", "compare_categories", "table"),
}
