"""模型输入契约；系统派生的状态、资格、发布版本不由模型声明。"""
from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ExpressionBase(StrictModel):
    expected_caliber: dict = Field(default_factory=dict)
    time_constraint: str | None = None
    time_alignment: Literal['EXPLICIT_PERIODS'] | None = None

class TagRef(ExpressionBase):
    kind: Literal['TAG']
    tag_id: int = Field(gt=0)

class Const(StrictModel):
    kind: Literal['CONST']
    value: str | float | int
    unit: str = 'NONE'

class CapabilityRef(ExpressionBase):
    kind: Literal['CAPABILITY']
    capability_id: str
    version: int | str

class BinaryOp(ExpressionBase):
    kind: Literal['ADD', 'SUB', 'MUL', 'DIV']
    args: list['Expression'] = Field(min_length=2, max_length=2)

class CountPositive(ExpressionBase):
    kind: Literal['COUNT_POSITIVE']
    args: list['Expression'] = Field(min_length=1, max_length=12)

Expression = Annotated[Union[TagRef, Const, CapabilityRef, BinaryOp, CountPositive], Field(discriminator='kind')]

class LeafBase(StrictModel):
    clause_id: str = Field(min_length=1, max_length=80)
    source_span: str = Field(min_length=1, max_length=2000)
    requirement_ids: list[str] = Field(default_factory=list, max_length=30)
    gap_reason: str | None = None

class Predicate(LeafBase):
    operator: str | None = None
    values: list[str | int | float] = Field(default_factory=list, max_length=100)
    value_unit: str | None = None
    value_scale: str | int | float | None = None
    expected_caliber: dict = Field(default_factory=dict)
    time_constraint: str | None = None
    unknown_policy: Literal['EXCLUDE', 'INCLUDE'] = 'EXCLUDE'

class TagPredicate(Predicate):
    kind: Literal['TAG_PREDICATE'] = 'TAG_PREDICATE'
    tag_id: int | None = Field(default=None, gt=0)

class DerivedPredicate(Predicate):
    kind: Literal['DERIVED_PREDICATE']
    expression: Expression | None = None
    compare_expression: Expression | None = None
    time_alignment: Literal['EXPLICIT_PERIODS'] | None = None

class ScopeAll(LeafBase):
    kind: Literal['SCOPE_ALL']

Leaf = Annotated[Union[TagPredicate, DerivedPredicate, ScopeAll], Field(discriminator='kind')]
class Group(StrictModel):
    logic: Literal['AND', 'OR']
    children: list[Union['Group', Leaf]] = Field(min_length=1, max_length=30)

class Requirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    source_spans: list[str] = Field(min_length=1)
    business_meaning: str = Field(min_length=1)
    origin: Literal['USER', 'CLARIFIED'] = 'USER'

class DefinitionRef(StrictModel):
    tag_id: int | None = None
    capability_id: str | None = None
    version: str | int | None = None

class Assumption(StrictModel):
    requirement_id: str
    status: Literal['PUBLISHED', 'PENDING', 'CONFIRMED']
    definition_ref: DefinitionRef | None = None
    question: str | None = None
    options: list[str] = Field(default_factory=list)

class IntentPlan(StrictModel):
    original_request: str
    requirements: list[Requirement] = Field(min_length=1, max_length=30)
    logic_tree: dict
    assumptions: list[Assumption] = Field(default_factory=list)

class IntentChange(StrictModel):
    operation: Literal['ADD', 'MODIFY', 'REMOVE', 'REPLACE_ALL']
    requirement_ids: list[str] = Field(default_factory=list)
    clause_ids: list[str] = Field(default_factory=list)
    source_span: str = Field(min_length=1)

class AudiencePlan(StrictModel):
    schema_version: Literal[3] = 3
    tree: Union[Group, Leaf]
    summary: str = Field(default='', max_length=120)
    intent_plan: IntentPlan | None = None
    intent_changes: list[IntentChange] = Field(default_factory=list)

BinaryOp.model_rebuild()
CountPositive.model_rebuild()
Group.model_rebuild()
AudiencePlan.model_rebuild()
