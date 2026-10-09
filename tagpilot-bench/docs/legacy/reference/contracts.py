"""评测控制面契约，与被测 Agent 的模型及 Guard 无依赖。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

Outcome = Literal['READY', 'NEEDS_USER_INPUT', 'CAPABILITY_GAP', 'PARTIAL']
Category = Literal['SINGLE', 'COMPOSITION', 'CLARIFICATION', 'BOUNDARY', 'MULTITURN', 'GAP']


def finite_decimal(value):
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('数值字面量非法') from exc
    if not result.is_finite():
        raise ValueError('数值必须有限')
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Expression(StrictModel):
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
            if len(self.args) != 2 and self.kind != 'COUNT_POSITIVE':
                raise ValueError('二元表达式必须两个参数')
            if self.kind == 'COUNT_POSITIVE' and not self.args:
                raise ValueError('计数表达式不能为空')
        return self


class Tree(StrictModel):
    kind: Literal['GROUP', 'PREDICATE', 'SCOPE_ALL']
    logic: Literal['AND', 'OR'] | None = None
    children: list[Tree] = Field(default_factory=list, max_length=30)
    expression: Expression | None = None
    operator: Literal['=', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'between', 'contains', 'is_null', 'is_not_null'] | None = None
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
            if self.operator in {'is_null','is_not_null'}:
                if count: raise ValueError('空值判定不能带值')
            elif self.operator == 'between':
                if count != 2: raise ValueError('between 需要两个端点，且均包含')
            elif self.operator in {'in','not_in'}:
                if not count or count != len(set(self.values)): raise ValueError('码值集合不能为空或重复')
            elif count != 1:
                raise ValueError('比较操作符需要一个值')
            for value in self.values:
                if self.data_kind == 'NUMBER':
                    finite_decimal(value)
                if self.data_kind == 'DATE':
                    date.fromisoformat(value)
            if self.operator == 'between' and self.values[0] > self.values[1] and self.data_kind != 'NUMBER':
                raise ValueError('区间端点倒置')
            if self.operator == 'between' and self.data_kind == 'NUMBER' and Decimal(self.values[0]) > Decimal(self.values[1]):
                raise ValueError('区间端点倒置')
        return self


class Expectation(StrictModel):
    outcomes: list[Outcome] = Field(min_length=1)
    tree: Tree | None = None
    required_slots: list[str] = Field(default_factory=list)
    gap_codes: list[str] = Field(default_factory=list)
    gap_subjects: list[str] = Field(default_factory=list)
    prohibited_behaviors: list[str] = Field(default_factory=lambda: ['AUTO_EXECUTE','SILENT_RELAXATION','UNSUPPORTED_REFERENCE'])

    @model_validator(mode='after')
    def actionable(self):
        if len(set(self.outcomes)) != len(self.outcomes):
            raise ValueError('终态重复')
        if 'READY' in self.outcomes and (self.tree is None or self.required_slots or self.gap_codes):
            raise ValueError('READY 需要完整标准树且无未解决项')
        if 'NEEDS_USER_INPUT' in self.outcomes and not self.required_slots:
            raise ValueError('澄清题缺少槽位')
        if 'CAPABILITY_GAP' in self.outcomes and not self.gap_codes:
            raise ValueError('能力缺口题缺少原因')
        return self


class Turn(StrictModel):
    user_message: str = Field(min_length=1)
    answer_slots: dict[str, str] = Field(default_factory=dict)
    expected: Expectation


class Provenance(StrictModel):
    authoring: Literal['DETERMINISTIC_FROM_AGENT_RECIPE', 'MODEL_EXPRESSION_FROM_DETERMINISTIC_TRUTH'] = 'DETERMINISTIC_FROM_AGENT_RECIPE'
    ai_review: Literal['NOT_INDEPENDENTLY_REVIEWED'] = 'NOT_INDEPENDENTLY_REVIEWED'
    human_review: Literal['PENDING'] = 'PENDING'
    official_bank_signoff: Literal[False] = False


class EvalCase(StrictModel):
    schema_version: Literal['eval-case.v1', 'eval-case.v2'] = 'eval-case.v1'
    case_id: str = Field(pattern=r'^CAL-\d{3,4}$')
    mother_id: str = Field(pattern=r'^M-\d{3,4}$')
    lineage_group: str
    phase: Literal['P1', 'P2', 'P3'] = 'P1'
    split: Literal['CALIBRATION', 'UNPARTITIONED', 'DEV', 'REGRESSION', 'HOLDOUT'] = 'CALIBRATION'
    status: Literal['DRAFT'] = 'DRAFT'
    category: Category
    persona: str
    scenario: str
    domains: list[str] = Field(min_length=1)
    requirement: str = Field(min_length=1,max_length=2000)
    fact_ids: list[str]
    target_tag_ids: list[int]
    forbidden_tag_ids: list[int] = Field(default_factory=list)
    eligible_tag_ids: list[int]
    reference_date: Literal['2026-09-18'] = '2026-09-18'
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    source_manifest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    expected: Expectation
    turns: list[Turn] = Field(default_factory=list,max_length=4)
    truth_basis: list[str] = Field(min_length=1)
    unresolved_fact_ids: list[str] = Field(default_factory=list)
    l3_status: Literal['FIXTURE_ORACLE_AVAILABLE','NOT_APPLICABLE']
    variant_index: int | None = Field(default=None, ge=0, le=3)
    variant_mode: Literal['TEMPLATE', 'MODEL_PARAPHRASE'] | None = None
    mother_requirement_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    provenance: Provenance = Field(default_factory=Provenance)


class EvalRun(StrictModel):
    schema_version: Literal['eval-run.v1'] = 'eval-run.v1'
    run_id: str
    case_id: str
    dataset_sha256: str
    source_revision: str
    model: str | None
    prompt_sha256: str | None
    snapshot_id: str
    build_id: str
    artifact_hash: str
    eligible_sha256: str
    reference_date: str
    status: Literal['COMPLETED','AGENT_TIMEOUT','AGENT_FAILED','RUN_INVALID']
    outcome: Outcome | None
    output: dict
    evidence_paths: list[str]
    elapsed_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    actual_cost: str | None
    stats: dict = Field(default_factory=dict)
    repeat: int = Field(default=0, ge=0)


class EvalVerdict(StrictModel):
    schema_version: Literal['eval-verdict.v1'] = 'eval-verdict.v1'
    case_id: str
    status: Literal['PASS','FAIL','RUN_INVALID','NOT_APPLICABLE']
    checks: dict[str, bool]
    failures: list[str]
    evidence: dict


class SemanticChangeSet(StrictModel):
    schema_version: Literal['semantic-changeset.v1'] = 'semantic-changeset.v1'
    change_id: str
    baseline_snapshot: str
    baseline_hash: str
    status: Literal['DRAFT', 'REVIEWED'] = 'DRAFT'
    library_id: int = 107
    source_case_ids: list[str]
    source_refs: list[str]
    changes: list[dict]
    review_records: list[dict] = Field(default_factory=list)
    regression_refs: list[str] = Field(default_factory=list)


CONTRACTS = {'EvalCase':EvalCase,'EvalRun':EvalRun,'EvalVerdict':EvalVerdict,'SemanticChangeSet':SemanticChangeSet}
