"""评测侧自足契约：案例、条件树、期望。

刻意不引用被测 Agent 的任何词表（outcome 枚举、plan schema、question reason 等）。
Agent 产物进入本 schema 的唯一路径是 `adapter.py`。这样 Agent 改协议时只需改 adapter，
案例集、判定、报告三者不动。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

# 评测侧终态枚举（与 Agent 业务含义对应，但取值由本包定义）
Outcome = Literal['READY', 'NEEDS_USER_INPUT', 'CAPABILITY_GAP', 'PARTIAL']
# 案例来源/难度（用于报告分组）
Source = Literal['scenario-61', 'demo-100', 'patch', 'guard']
Difficulty = Literal['直达', '需组合', '需澄清', '明细', '空集', '越权']
AnswerMode = Literal['MYSQL_RECOUNT', 'P3_ORACLE', 'HUMAN']


def finite_decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('数值字面量非法') from exc
    if not result.is_finite():
        raise ValueError('数值必须有限')
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Expression(StrictModel):
    """条件树叶子里的算术表达式：标签字段、常量、四则运算、正计数（派生类数）。"""
    kind: Literal['TAG', 'CONST', 'ADD', 'SUB', 'MUL', 'DIV', 'COUNT_POSITIVE']
    tag_id: int | None = None
    field_name: str | None = None
    value: StrictStr | None = None
    unit: str = 'NONE'
    args: list[Expression] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def shape(self):
        if self.kind == 'TAG':
            if not self.tag_id or not self.field_name or self.value is not None or self.args:
                raise ValueError('TAG 必须且只能引用一个标签字段')
        elif self.kind == 'CONST':
            if self.tag_id is not None or self.field_name is not None or self.args or self.value is None:
                raise ValueError('CONST 只能提供值')
            finite_decimal(self.value)
        else:
            if self.tag_id is not None or self.field_name is not None or self.value is not None:
                raise ValueError('表达式不能混入标签或常量字段')
            if self.kind != 'COUNT_POSITIVE' and len(self.args) != 2:
                raise ValueError('二元表达式必须两个参数')
            if self.kind == 'COUNT_POSITIVE' and not self.args:
                raise ValueError('计数表达式不能为空')
        return self


class Tree(StrictModel):
    """条件树：GROUP（逻辑分组）/ PREDICATE（单条件）/ SCOPE_ALL（全集）。"""
    kind: Literal['GROUP', 'PREDICATE', 'SCOPE_ALL']
    logic: Literal['AND', 'OR'] | None = None
    children: list[Tree] = Field(default_factory=list, max_length=30)
    expression: Expression | None = None
    operator: Literal['=', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'between',
                      'contains', 'is_null', 'is_not_null'] | None = None
    values: list[StrictStr] = Field(default_factory=list, max_length=100)
    data_kind: Literal['NUMBER', 'STRING', 'DATE'] | None = None
    null_policy: Literal['EXCLUDE'] = 'EXCLUDE'
    caliber: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def shape(self):
        if self.kind == 'GROUP':
            if not self.logic or not self.children or self.expression or self.operator or self.values or self.data_kind or self.caliber:
                raise ValueError('GROUP 字段错误')
        elif self.kind == 'SCOPE_ALL':
            if self.logic or self.children or self.expression or self.operator or self.values or self.data_kind or self.caliber:
                raise ValueError('SCOPE_ALL 不能隐藏额外条件')
        else:
            if self.logic or self.children or not self.expression or not self.operator or not self.data_kind:
                raise ValueError('PREDICATE 字段错误')
            count = len(self.values)
            if self.operator in {'is_null', 'is_not_null'}:
                if count:
                    raise ValueError('空值判定不能带值')
            elif self.operator == 'between':
                if count != 2:
                    raise ValueError('between 需要两个端点，且均包含')
            elif self.operator in {'in', 'not_in'}:
                if not count or count != len(set(self.values)):
                    raise ValueError('码值集合不能为空或重复')
            elif count != 1:
                raise ValueError('比较操作符需要一个值')
            for value in self.values:
                if self.data_kind == 'NUMBER':
                    finite_decimal(value)
                if self.data_kind == 'DATE':
                    date.fromisoformat(value)
            if self.operator == 'between' and self.data_kind == 'NUMBER':
                if Decimal(self.values[0]) > Decimal(self.values[1]):
                    raise ValueError('区间端点倒置')
            if self.operator == 'between' and self.data_kind != 'NUMBER':
                if self.values[0] > self.values[1]:
                    raise ValueError('区间端点倒置')
        return self


class Expected(StrictModel):
    """一个案例的期望：终态 + （READY）标准树 / （澄清）槽位 / （缺口）原因。

    `forbid_ready=True` 用于越权/拒答输入：只要求**不产出可执行计划**（终态非 READY），
    此时不要求槽位/缺口。
    """
    outcomes: list[Outcome] = Field(min_length=1)
    tree: Tree | None = None
    clarify_slots: list[str] = Field(default_factory=list)
    gap_codes: list[str] = Field(default_factory=list)
    counts: dict | None = None
    forbid_ready: bool = False

    @model_validator(mode='after')
    def actionable(self):
        if len(set(self.outcomes)) != len(self.outcomes):
            raise ValueError('终态重复')
        if 'READY' in self.outcomes and (self.tree is None or self.clarify_slots or self.gap_codes):
            raise ValueError('READY 需要完整标准树且无未解决项')
        if self.forbid_ready:
            if 'READY' in self.outcomes:
                raise ValueError('forbid_ready 案例不能期望 READY')
            return self
        if 'NEEDS_USER_INPUT' in self.outcomes and not self.clarify_slots:
            raise ValueError('澄清题缺少槽位')
        if 'CAPABILITY_GAP' in self.outcomes and not self.gap_codes:
            raise ValueError('能力缺口题缺少原因')
        return self


class Turn(StrictModel):
    """多轮案例的一轮用户消息（首轮之后的追加/澄清回答）。"""
    user_message: str = Field(min_length=1)
    expected: Expected


class Provenance(StrictModel):
    authoring: Literal['HUMAN_DOC_STRUCTURED', 'P3_DEMO', 'HUMAN_WRITTEN']
    oracle: AnswerMode
    verified: bool = False
    note: str | None = None


class Case(StrictModel):
    schema_version: Literal['bench-case.v1'] = 'bench-case.v1'
    case_id: str = Field(pattern=r'^(SC|DM|PT|GD)-[A-Z0-9]+$')
    suite: Literal['core', 'guard'] = 'core'
    source: Source
    scenario: str
    tags: list[str] = Field(min_length=1)
    difficulty: Difficulty
    requirement: str = Field(min_length=1, max_length=2000)
    turns: list[Turn] = Field(default_factory=list, max_length=4)
    reference_date: Literal['2026-09-18'] = '2026-09-18'
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    expected: Expected
    oracle_ref: str | None = None
    provenance: Provenance
