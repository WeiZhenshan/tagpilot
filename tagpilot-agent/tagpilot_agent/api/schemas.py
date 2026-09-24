from pydantic import BaseModel, ConfigDict, Field

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
    requirement: str = Field(min_length=1,max_length=2000)
    previous_plan: dict = Field(default_factory=dict)
    edited_plan: dict | None = None
    history: list[dict] = Field(default_factory=list,max_length=20)
    confirmed_clause_ids: list[str] = Field(default_factory=list,max_length=30)

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
