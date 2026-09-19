"""AudienceQueryDSL 最小执行契约与目录约束校验。"""

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
