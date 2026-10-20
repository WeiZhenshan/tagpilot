"""有界分析中继。Java 在已认证的会话读取中执行，工具不持有用户/数据库凭据。"""
import asyncio
import time
import uuid
from typing import Literal
from pydantic import Field
from tagpilot_agent.domain.plan_model import StrictModel, AudiencePlan
from tagpilot_agent.tools.cards import observation


class AnalysisContext(StrictModel):
    scope: Literal['current', 'all', 'subset', 'selection'] = 'current'
    plan: AudiencePlan | None = None
    tag_ids: list[int] = Field(default_factory=list, max_length=10)
    target_artifact_id: str | None = Field(default=None,max_length=120)
    target_artifact_version: int | None = Field(default=None,gt=0)


class RouteRequest(StrictModel):
    intent: Literal['audience', 'analysis', 'audience_then_analysis', 'view', 'clarify']


class AggregateQuery(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,30}$')
    population: Literal['target', 'all'] = 'target'
    tag_id: int | None = Field(default=None, gt=0)
    operation: Literal['count', 'sum', 'avg', 'min', 'max', 'median', 'distribution']
    dimensions: list[int] = Field(default_factory=list, max_length=2)


class QueryAggregates(StrictModel):
    queries: list[AggregateQuery] = Field(min_length=1, max_length=12)


class DeriveFacts(StrictModel):
    id: str = Field(pattern=r'^f-[a-z][a-z0-9-]{0,50}$')
    label: str = Field(min_length=1, max_length=80)
    operation: Literal['difference', 'ratio']
    fact_ids: list[str] = Field(min_length=2, max_length=2)


class SubmitInsight(StrictModel):
    blocks: list[dict] = Field(min_length=1, max_length=12)
    complete: bool = True


MODELS = {'route_request': RouteRequest, 'get_analysis_context': AnalysisContext, 'query_aggregates': QueryAggregates,
          'derive_facts': DeriveFacts, 'submit_insight_result': SubmitInsight}
MESSAGES = {'route_request':'正在确认本轮任务', 'get_analysis_context': '正在核对分析范围与指标', 'query_aggregates': '正在查询并核验聚合数据',
            'derive_facts': '正在计算同口径差异', 'submit_insight_result': '正在核验回答与图表'}
DESCRIPTIONS = {
    'route_request': '本轮第一个工具：选择纯圈选audience、已有范围分析analysis、先圈选再分析audience_then_analysis、仅改图view或需澄清clarify。用户同时要求圈选和分析时必须选择audience_then_analysis，不能只完成圈选。',
    'get_analysis_context': '读取服务端分析范围、当前图表与证据。无范围须澄清；用户明确要求全量才用all。新筛选须提供完整已核验plan；subset与现有条件取交集，不改变原圈选。多图澄清后可用target_artifact_id和target_artifact_version选择本会话图表，不能覆盖用户显式选定的引用。',
    'query_aggregates': '执行声明式聚合，累计最多5标签、二维分组、12查询节点。相同id替换节点；每次返回重算后的完整活动证据快照，旧派生事实作废。无SQL或物理列。',
    'derive_facts': '用本批两个事实计算difference或ratio。返回服务端生成的事实和单位；差值不是因果证据。',
    'submit_insight_result': '发布核验内容块，可分次complete=false，最后complete=true。text:{text,basis:OBSERVED|HYPOTHESIS}，数字只能{fact:id}。chart/table:{title,query_ids,kind:kpi|bar|table|heatmap|stacked_bar,share?,orientation?}，stacked_bar仅限单维互斥分类构成。已有图只改视图:{type:chart,view_only:true,kind:bar|table,orientation?,sort:descending?}。clarification:{prompt,options}。禁止事实值、SQL、HTML或任意图表配置。',
}


async def dispatch(ctx, name, raw):
    if ctx.analysis_complete or ctx.cancelled():
        return observation({'ok': False, 'message': '运行已结束'}, True)
    ctx.stats['tools'] += 1
    call = uuid.uuid4().hex
    started = time.monotonic()
    try:
        args = MODELS[name].model_validate(raw).model_dump(exclude_none=True)
        if name=='route_request':
            if ctx.conversation_intent and ctx.conversation_intent!=args['intent']:
                return observation({'ok':False,'message':'本轮阶段已锁定，请完成已确认任务'},True)
            if ctx.request.get('intent')=='analysis' and args['intent']=='audience':
                return observation({'ok':False,'message':'用户已指定分析，不能改为纯圈选'},True)
            ctx.conversation_intent=args['intent']
            return observation({'ok':True,'intent':args['intent'],'message':'先圈选再分析时，submit_result READY只保存中间范围，必须继续取数并提交分析内容。' if args['intent']=='audience_then_analysis' else '按本轮任务继续。'})
        if name=='get_analysis_context' and args.get('plan'):
            from tagpilot_agent.guards.guard import check
            checked=await check(args['plan'],ctx,strict=True)
            if not checked.get('valid'):
                return observation({'ok':False,'message':'分析条件未通过校验','diagnostics':checked.get('diagnostics',[])},True)
            args['plan']=checked
        if ctx.stats['tools'] > ctx.budget.max_tools:
            return observation({'ok': False, 'message': '工具预算已用完，请提交已核验结果'}, True)
        if name == 'query_aggregates' and ctx.budget.hard - ctx.budget.elapsed(ctx) < 25:
            return observation({'ok': False, 'message': '请停止新增查询并提交已核验结果'}, True)
        future = asyncio.get_running_loop().create_future()
        ctx.analysis_pending[call] = future
        ctx.emit({'type':'tool.started','call_id':call,'tool':name,'message':MESSAGES[name]})
        ctx.emit({'type': 'analysis.request', 'request_id': call, 'call_id': call, 'tool': name, 'args': args,
                  'expires_at':round((time.time()+min(50,max(.1,ctx.budget.salvage_at()-ctx.budget.elapsed(ctx))))*1000), 'message': MESSAGES[name]})
        remaining = min(50, max(.1, ctx.budget.salvage_at() - ctx.budget.elapsed(ctx)))
        result = await asyncio.wait_for(future, remaining)
        if result.get('ok') and name == 'submit_insight_result' and result.get('complete'):
            ctx.analysis_complete = True
            ctx.submitted.set()
        return observation(result, not result.get('ok'), limit=300000)
    except (ValueError, TypeError):
        return observation({'ok': False, 'message': '分析参数不符合协议'}, True)
    except TimeoutError:
        return observation({'ok': False, 'message': '业务服务未及时应答，请提交已有结果或稍后重试'}, True)
    finally:
        ctx.analysis_pending.pop(call, None)
        ctx.emit({'type': 'telemetry.span', 'name': 'analysis.' + name,
                  'duration_ms': round((time.monotonic() - started) * 1000)})


def create_server(ctx):
    from claude_agent_sdk import tool, create_sdk_mcp_server
    registered = []
    for name, model in MODELS.items():
        async def handler(args, _name=name):
            return await dispatch(ctx, _name, args)
        registered.append(tool(name, DESCRIPTIONS[name], model.model_json_schema())(handler))
    return create_sdk_mcp_server(name='insight', version='1.0.0', tools=registered)
