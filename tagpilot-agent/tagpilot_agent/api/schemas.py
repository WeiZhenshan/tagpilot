from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator
from tagpilot_agent.agent.outcome import Question

class ClarificationRecord(BaseModel):
    model_config=ConfigDict(extra='forbid')
    questions: list[Question] = Field(max_length=3)
    answer: str | dict

class ClarificationState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    records: list[ClarificationRecord] = Field(default_factory=list,max_length=20)
    pending_questions: list[Question] = Field(default_factory=list,max_length=3)

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    run_id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    thread_id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    owner_id: str = Field(min_length=1,max_length=64)
    library_id: int = Field(gt=0)
    build_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    snapshot_id: str
    artifact_hash: str
    eligible_tag_ids: list[int] = Field(max_length=100000)
    pinned_tag_ids: list[PositiveInt] = Field(default_factory=list,max_length=5)
    pinned_only: bool = False
    requirement: str = Field(min_length=1,max_length=2000)
    reference_date: str | None = Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$')
    timezone: str = Field(default='Asia/Shanghai',max_length=64)
    previous_plan: dict = Field(default_factory=dict)
    source_plan: dict = Field(default_factory=dict)
    edited_plan: dict | None = None
    history: list[dict] = Field(default_factory=list,max_length=20)
    confirmed_clause_ids: list[str] = Field(default_factory=list,max_length=30)
    clarification_state: ClarificationState = Field(default_factory=ClarificationState)
    continuation_of: str | None = Field(default=None,pattern=r'^[a-zA-Z0-9-]{1,64}$')

    @model_validator(mode='after')
    def validate_pinned(self):
        if len(set(self.pinned_tag_ids))!=len(self.pinned_tag_ids) or not set(self.pinned_tag_ids)<=set(self.eligible_tag_ids):
            raise ValueError('所选标签必须唯一且属于当前可用标签')
        if self.pinned_only and not self.pinned_tag_ids:
            raise ValueError('仅选标签入口必须提供标签')
        return self

class ResumeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    owner_id: str
    answer: str | dict | None = None
    eligible_tag_ids: list[int] = Field(default_factory=list,max_length=100000)
    confirmed_clause_ids: list[str] = Field(default_factory=list,max_length=30)

class RepairRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    owner_id: str
    diagnostics: list[dict] = Field(min_length=1,max_length=20)
    eligible_tag_ids: list[int] = Field(max_length=100000)
    confirmed_clause_ids: list[str] = Field(default_factory=list,max_length=30)
