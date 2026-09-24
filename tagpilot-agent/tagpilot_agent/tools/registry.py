"""五个闭包领域工具；SDK 仅负责调用，不拥有业务校验。"""
import os
import time
from pydantic import Field, ValidationError
from tagpilot_agent.domain.plan_model import StrictModel, AudiencePlan
from tagpilot_agent.agent.outcome import AgentOutcome
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from .cards import observation
from typing import Literal

class Query(StrictModel):
    text: str = Field(min_length=1,max_length=500)
    requirement_id: str | None = None
class FindTags(StrictModel):
    queries: list[Query] = Field(min_length=1,max_length=8)
    depth: Literal['quick','deep'] = 'quick'
    top_k: int = Field(default=8,ge=1,le=8)
class TagDetails(StrictModel):
    tag_ids: list[int] = Field(min_length=1,max_length=10)
    value_query: str | None = Field(default=None,max_length=200)
    max_values: int = Field(default=30,ge=1,le=30)
class Capabilities(StrictModel):
    query: str = Field(default='',max_length=500)
    capability_ids: list[str] = Field(default_factory=list,max_length=20)
    requirement_ids: list[str] = Field(default_factory=list,max_length=30)
class CheckPlan(StrictModel):
    plan: AudiencePlan

DESCRIPTIONS={'find_tags':'批量找已发布候选：quick 词法匹配，deep 语义检索。请标记 requirement_id。',
    'get_tag_details':'核对标签口径、单位、码值及同族成员；value_query 可筛选码值。',
    'find_capabilities':'查找已发布计算或业务定义，标记 requirement_ids。',
    'check_plan':'检查完整或局部方案，返回可修复诊断。',
    'submit_result':'提交唯一终态：READY、NEEDS_USER_INPUT、CAPABILITY_GAP 或 PARTIAL；被拒后修复。'}
MODELS={'find_tags':FindTags,'get_tag_details':TagDetails,'find_capabilities':Capabilities,'check_plan':CheckPlan,'submit_result':AgentOutcome}
MESSAGES={'find_tags':'正在查找相关标签','get_tag_details':'正在核对标签口径与码值','find_capabilities':'正在查找已发布业务能力','check_plan':'正在核验圈选条件','submit_result':'正在整理圈选方案'}


from .find_tags import find_tags
from .tag_details import tag_details
from .capabilities import capabilities
from .check_plan import check_plan
from .submit_result import submit_result

HANDLERS={'find_tags':find_tags,'get_tag_details':tag_details,'find_capabilities':capabilities,'check_plan':check_plan,'submit_result':submit_result}

async def dispatch(ctx,name,args):
    if ctx.accepted:return observation({'ok':False,'message':'运行已提交'},True)
    ctx.stats['tools']+=1
    if ctx.stats['tools']>int(os.getenv('TAG_AGENT_MAX_TOOLS','16')) and name!='submit_result':
        return observation({'ok':False,'message':'工具预算已用完，请立即提交 PARTIAL'},True)
    ctx.emit({'type':'tool.started','tool':name,'message':MESSAGES[name]})
    started=time.monotonic()
    try:
        args=MODELS[name].model_validate(args).model_dump(exclude_none=True)
        result=await HANDLERS[name](ctx,args)
        if time.monotonic()-ctx.started>float(os.getenv('TAG_AGENT_SOFT_TIMEOUT','40')):result['budget_hint']='请尽快提交当前最佳方案'
        return observation(result,result.get('ok') is False)
    except SemanticRetrieveError as exc:
        if exc.status_code in {401,403,409}:
            ctx.stats['fatal_status']=exc.status_code;ctx.submitted.set()
        return observation({'ok':False,'code':'RETRIEVAL_UNAVAILABLE','retryable':exc.status_code not in {401,403,409}},True)
    except (ValueError,TypeError,KeyError) as exc:
        return observation({'ok':False,'code':'SCHEMA_INVALID','message':str(exc)[:500] if not isinstance(exc,ValidationError) else '工具参数不符合契约'},True)
    finally:
        ctx.emit({'type':'telemetry.span','name':'tool.'+name,'duration_ms':round((time.monotonic()-started)*1000)})
        ctx.emit({'type':'tool.completed','tool':name,'message':MESSAGES[name].replace('正在','已完成'),'duration_ms':round((time.monotonic()-started)*1000)})

def create_server(ctx):
    from claude_agent_sdk import tool, create_sdk_mcp_server
    registered=[]
    for name,model in MODELS.items():
        async def handler(args,_name=name):return await dispatch(ctx,_name,args)
        registered.append(tool(name,DESCRIPTIONS[name],model.model_json_schema())(handler))
    return create_sdk_mcp_server(name='tagpilot',version='1.0.0',tools=registered)

