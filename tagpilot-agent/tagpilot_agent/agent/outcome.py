"""唯一终态提交契约，以及 Java 兼容 result 映射。"""
from typing import Literal
from pydantic import Field
from tagpilot_agent.domain.plan_model import StrictModel, AudiencePlan

class Question(StrictModel):
    requirement_id: str
    clause_id: str | None = None
    prompt: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=5)
    reason: Literal['DEFINITION_MISSING','MULTIPLE_PUBLISHED_DEFINITIONS','CONFLICTING_INTERPRETATIONS','THRESHOLD_MISSING','GOAL_UNCLEAR']

class Gap(StrictModel):
    requirement_id: str
    reason: Literal['NO_PUBLISHED_TAG','NO_CAPABILITY','CALIBER_UNAVAILABLE','METADATA_INCOMPLETE']
    nearest_tag_ids: list[int] = Field(default_factory=list, max_length=10)

class AgentOutcome(StrictModel):
    outcome: Literal['READY','NEEDS_USER_INPUT','CAPABILITY_GAP','PARTIAL']
    plan: AudiencePlan
    questions: list[Question] = Field(default_factory=list, max_length=3)
    gaps: list[Gap] = Field(default_factory=list, max_length=30)
    summary: str = Field(default='', max_length=120)


def result_for(ctx):
    accepted=ctx.accepted or {'outcome':'PARTIAL','plan':ctx.best_plan or ctx.request.get('previous_plan') or {},'questions':[],'gaps':[]}
    return {'plan':accepted['plan'], 'questions':accepted.get('questions',[]),
            'interrupt_id':ctx.request['run_id']+'-'+str(ctx.request.get('_generation',0)) if accepted['outcome']=='NEEDS_USER_INPUT' else None,
            'outcome':{'outcome':accepted['outcome'],'gaps':accepted.get('gaps',[]),'stats':ctx.stats}}
