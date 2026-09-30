"""Java→Python 的聚合信封。不接收客户键、物理字段、SQL或逐客分数。"""
from datetime import date
from typing import Literal
from pydantic import Field, model_validator
from .contracts import Contract, Hash, Identifier, Number, Text, Version

class AggregateRow(Contract):
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    n: int | None = Field(default=None, ge=0)
    value: Number | None = None
    holders: int | None = Field(default=None, ge=0)
    missing: int | None = Field(default=None, ge=0)
    unheld: int | None = Field(default=None, ge=0)
    suitable: int | None = Field(default=None, ge=0)
    opportunity: int | None = Field(default=None, ge=0)
    tier: Literal["low", "medium", "high"] | None = None
    reasons: list[Identifier] = Field(default_factory=list, max_length=2)
    channel: str | None = Field(default=None, max_length=24)
    contributions: dict[Identifier, Number] = Field(default_factory=dict, max_length=8)
    status: Literal["AVAILABLE", "SUPPRESSED", "MISSING"] = "AVAILABLE"

    @model_validator(mode="after")
    def safe(self):
        if self.status != "AVAILABLE" and any(v is not None for v in (self.n,self.value,self.holders,self.missing,self.unheld,self.suitable,self.opportunity)):
            raise ValueError("抑制结果不得携带数值")
        if self.status == "AVAILABLE" and self.n is None:
            raise ValueError("聚合结果必须有样本量")
        if self.status != "AVAILABLE" and self.contributions:
            raise ValueError("抑制结果不得携带贡献")
        for value in (self.holders,self.missing,self.unheld,self.suitable,self.opportunity):
            if value is not None and self.n is not None and value > self.n:
                raise ValueError("聚合计数超过总体")
        return self

class QueryAggregate(Contract):
    standardization_mode: Literal["aum_risk", "aum", "risk"] = "aum_risk"
    query_id: Identifier
    category: Identifier | None = None
    rows: list[AggregateRow] = Field(default_factory=list, max_length=144)
    status: Literal["AVAILABLE", "SUPPRESSED", "MISSING"] = "AVAILABLE"
    reason: str = Field(default="", max_length=500)
    evidence_id: Text

class AggregateBatch(Contract):
    skill_id: Identifier
    pack_hash: Hash
    snapshot_id: Text
    binding_version: Version
    plan_hash: Hash
    data_as_of: date
    queries: list[QueryAggregate] = Field(max_length=40)
    benchmark_definition: Text
    benchmark_version: Version
    scope_hash: Hash

    @model_validator(mode="after")
    def unique(self):
        if len({(q.query_id,q.category) for q in self.queries}) != len(self.queries):
            raise ValueError("聚合查询标识重复")
        for query in self.queries:
            if query.status != "AVAILABLE" and query.rows:
                raise ValueError("抑制或缺失查询不得下发聚合行")
        return self
