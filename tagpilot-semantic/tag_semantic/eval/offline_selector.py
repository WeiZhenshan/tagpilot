"""检索验收用的精确证据选择器与 DSL 校验；不是 Agent 编排图。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AudienceCondition(BaseModel):
    tag_id: int = Field(gt=0)
    operator: Literal["=", "in", "not_in", ">", ">=", "<", "<=", "between", "like", "contains"]
    value: Any | None = None
    values: list[Any] | None = None

    @model_validator(mode="after")
    def one_value_shape(self):
        if self.operator in {"in", "not_in", "between"}:
            if not isinstance(self.values, list) or not self.values:
                raise ValueError("集合或区间操作符必须提供非空 values")
            if self.operator == "between" and len(self.values) != 2:
                raise ValueError("between 必须恰有两个端点")
        elif self.value is None:
            raise ValueError("单值操作符必须提供 value")
        return self


class AudienceQueryDSL(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: list[AudienceCondition] = Field(min_length=1, max_length=20)


def validate_dsl(payload: dict[str, Any], catalog, eligible_tag_ids: set[int]) -> AudienceQueryDSL:
    dsl = AudienceQueryDSL.model_validate(payload)
    code_by_tag: dict[int, set[str]] = {}
    for row in catalog.code_values:
        code_by_tag.setdefault(int(row["tag_id"]), set()).add(str(row["code"]))
    for condition in dsl.conditions:
        if condition.tag_id not in eligible_tag_ids or condition.tag_id not in catalog.tags:
            raise ValueError("DSL 引用了资格外或不存在的标签")
        tag = catalog.tags[condition.tag_id]
        allowed = set(tag.get("allowed_operators") or [])
        if condition.operator not in allowed:
            raise ValueError(f"标签 {condition.tag_id} 不允许操作符 {condition.operator}")
        if tag.get("semantic_type") in {"BOOL", "ENUM_NOMINAL", "ENUM_ORDINAL", "ENUM_HIERARCHY"}:
            raw = condition.values if condition.operator in {"in", "not_in"} else [condition.value]
            if any(str(value) not in code_by_tag.get(condition.tag_id, set()) for value in raw):
                raise ValueError(f"标签 {condition.tag_id} 引用了未发布码值")
    return dsl


class ExactEvidenceSelector:
    """无生成式模型时的显式演示后备：只接受唯一的标签名称/别名证据。"""

    name = "exact-evidence-offline"

    def select(self, requirement, candidates, catalog):
        normalized = "".join(requirement.lower().split())
        exact = []
        candidate_ids = {int(c["tag_id"]) for c in candidates}
        for tag_id in candidate_ids:
            tag = catalog.tags[tag_id]
            names = {str(tag.get("name") or "")}
            names.update(str(a.get("alias_text") or "") for a in tag.get("aliases") or [] if a.get("review_status") == "REVIEWED")
            matched = ["".join(name.lower().split()) for name in names if name and "".join(name.lower().split()) in normalized]
            if matched:
                exact.append((max(map(len, matched)), tag))
        if len(exact) != 1:
            if not exact:
                return None
            longest = max(length for length, _ in exact)
            exact = [item for item in exact if item[0] == longest]
            if len(exact) != 1:
                return None
        tag = exact[0][1]
        semantic_type = tag.get("semantic_type")
        operator = "=" if semantic_type in {"BOOL", "ENUM_NOMINAL", "ENUM_ORDINAL", "ENUM_HIERARCHY"} else None
        dsl = None
        if str(semantic_type).startswith("NUM_"):
            import re
            from decimal import Decimal
            boundary = re.search(r"(至少|不低于|大于等于|超过|高于|大于|不超过|不高于|小于等于|低于|小于)\s*(\d+(?:\.\d+)?)\s*(亿|万)?", normalized)
            if boundary:
                word, number, magnitude = boundary.groups()
                operator = {"至少": ">=", "不低于": ">=", "大于等于": ">=", "超过": ">", "高于": ">", "大于": ">",
                            "不超过": "<=", "不高于": "<=", "小于等于": "<=", "低于": "<", "小于": "<"}[word]
                value = Decimal(number) * {None: 1, "万": 10000, "亿": 100000000}[magnitude]
                dsl = {"logic": "AND", "conditions": [{"tag_id": int(tag["tag_id"]), "operator": operator,
                                                            "value": int(value) if value == value.to_integral() else float(value)}]}
        return {"decision": "RECOMMEND" if dsl else "NEEDS_VALUE", "confidence": 1.0, "explanation": "唯一已复核名称或别名精确命中",
                "recommended_tag_ids": [int(tag["tag_id"])], "operator_hint": operator, "dsl": dsl}
