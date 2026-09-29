"""洞察画像：沿用同一RunManager准入和加密库，Java一次注入取数计划与聚合。"""
import asyncio
import time
from dataclasses import dataclass,field
from fastapi import Depends,HTTPException
from pydantic import Field
from tagpilot_insight.contracts import Contract,CohortSnapshot,MetricBinding,InsightReport
from tagpilot_insight.planning import MetricPlan,plan_skill
from tagpilot_insight.aggregates import AggregateBatch
from tagpilot_insight.registry import SkillRegistry
from tagpilot_insight.compose import compose
from tagpilot_insight.narration import guarded_narration
from tagpilot_agent.runtime.budget import Budget

class PlanRequest(Contract):
    skill_id:str
    cohort:CohortSnapshot
    bindings:list[MetricBinding] = Field(max_length=60)
    eligible_tag_ids:list[int] = Field(max_length=100000)
    parameters:dict = Field(default_factory=dict)
    published_hash:str | None = None

class InsightRunRequest(Contract):
    run_id:str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    thread_id:str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    owner_id:str = Field(min_length=1,max_length=64)
    plans:list[MetricPlan] = Field(min_length=1,max_length=3)
    aggregates:list[AggregateBatch] = Field(max_length=3)
    narrate:bool=False

@dataclass
class InsightContext:
    request:dict
    emit:object
    cancelled:object
    started:float=field(default_factory=time.monotonic)
    submitted:asyncio.Event=field(default_factory=asyncio.Event)
    budget:Budget=field(default_factory=Budget.from_env)
    stats:dict=field(default_factory=dict)

async def execute_insight(manager,rid,request):
    owner=request['owner_id'];admitted=False
    ctx=InsightContext(request,lambda e:manager.store.emit(rid,e),lambda:manager.store.get(rid,owner)['status']=='CANCELLED')
    manager.contexts[rid]=ctx
    try:
        async with manager.condition:
            manager.waiters.append(rid)
            deadline=time.monotonic()+20
            while manager.active>=manager.limit or manager.users[owner]>=manager.per_user:
                if ctx.cancelled():return
                ctx.emit({'type':'run.queued','message':'洞察已排队，等待可用名额'})
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('洞察排队超时')
                await asyncio.wait_for(manager.condition.wait(),remaining)
            manager.waiters.remove(rid)
            if ctx.cancelled():return
            manager.active+=1;manager.users[owner]+=1;admitted=True
        ctx.started=time.monotonic()
        ctx.emit({'type':'run.started','message':'正在核验洞察数据与版本'})
        async with asyncio.timeout(min(ctx.budget.hard,60)):
            plans=[MetricPlan.model_validate(p) for p in request['plans']]
            if len({p.skill_id for p in plans})!=len(plans) or any(p.cohort!=plans[0].cohort for p in plans):raise ValueError('场景包必须使用同一客群快照且技能不能重复')
            batches={b.skill_id:b for b in [AggregateBatch.model_validate(a) for a in request['aggregates']]}
            results=[]
            for plan in plans:
                if ctx.cancelled():return
                ctx.emit({'type':'insight.composing','skill_id':plan.skill_id,'message':'正在计算事实并核对图表'})
                if plan.status=='READY' and plan.skill_id not in batches:raise ValueError('缺少已就绪技能聚合')
                if plan.status=='BLOCKED':
                    from tagpilot_insight.contracts import SkillResult
                    results.append(SkillResult(skill_id=plan.skill_id,skill_version=plan.skill_version,pack_hash=plan.pack_hash,status='BLOCKED',level='L4',reasons=plan.reasons))
                else:results.append(await asyncio.to_thread(compose,plan,batches[plan.skill_id]))
            report=InsightReport(run_id=rid,cohort=plans[0].cohort,results=results)
            import os
            if request.get('narrate') and os.getenv('TAG_INSIGHT_LLM_ENABLED','false').lower()=='true':
                from tagpilot_agent.runtime.insight_model import structured_once
                candidates=await structured_once('narrate',report.model_dump(mode='json'))
                report,accepted=guarded_narration(report,candidates or {},published_hashes={p.skill_id:p.pack_hash for p in plans})
                if not accepted:ctx.emit({'type':'run.degraded','message':'叙述已回退到确定性模板，数字和图表保留'})
            if ctx.cancelled():return
            manager.store.status(rid,'COMPLETED',report.model_dump(mode='json'))
            ctx.emit({'type':'run.completed','message':'洞察报告已核验并保存','elapsed_s':round(time.monotonic()-ctx.started,3)})
    except asyncio.CancelledError:
        manager.store.status(rid,'INTERRUPTED',error='洞察运行中断，请重新运行');raise
    except Exception as exc:
        manager.store.status(rid,'FAILED',error=str(exc)[:500]);ctx.emit({'type':'run.failed','message':'洞察未完成，请检查版本或数据条件'})
    finally:
        manager.contexts.pop(rid,None)
        async with manager.condition:
            if rid in manager.waiters:manager.waiters.remove(rid)
            if admitted:manager.active-=1;manager.users[owner]-=1
            manager.condition.notify_all()


async def admitted_once(manager,owner,kind,payload):
    # 路由与改图也计入同一并发/用户限额；满额立即使用确定性回退。
    from tagpilot_agent.runtime.insight_model import structured_once
    if not isinstance(owner,str) or not 1<=len(owner)<=64:raise HTTPException(422,'缺少服务端运行身份')
    async with manager.condition:
        if manager.active>=manager.limit or manager.users[owner]>=manager.per_user:return None
        manager.active+=1;manager.users[owner]+=1
    try:
        async with asyncio.timeout(20):return await structured_once(kind,payload)
    except TimeoutError:return None
    finally:
        async with manager.condition:
            manager.active-=1;manager.users[owner]-=1;manager.condition.notify_all()

def register_insight(app,authenticate,runtime):
    @app.get('/agent/insight/catalog',dependencies=[Depends(authenticate)])
    def catalog():
        from tagpilot_insight.metrics import METRICS,BENCHMARKS
        reg=SkillRegistry()
        return {'skills':[{'manifest':reg.get(id).model_dump(mode='json'),'pack_hash':reg.hash(id)} for id in reg.manifests],
                'metrics':[m.model_dump(mode='json') for m in METRICS.values()],'benchmarks':[b.model_dump(mode='json') for b in BENCHMARKS]}
    @app.post('/agent/insight/plan',dependencies=[Depends(authenticate)])
    def plan(request:PlanRequest):
        try:return plan_skill(request.skill_id,request.cohort,request.bindings,set(request.eligible_tag_ids),request.parameters,published_hash=request.published_hash).model_dump(mode='json')
        except ValueError as e:raise HTTPException(422,str(e))
    @app.post('/agent/insight/runs',dependencies=[Depends(authenticate)])
    async def create(request:InsightRunRequest):
        res=runtime();payload={**request.model_dump(mode='json'),'profile':'insight'}
        try:
            try:res['store'].get(request.run_id,request.owner_id)
            except KeyError:res['manager'].capacity()
            if res['store'].create(request.run_id,payload):res['manager'].start(request.run_id,payload)
        except ValueError as e:raise HTTPException(409,str(e))
        return {'run_id':request.run_id}
    @app.post('/agent/insight/route',dependencies=[Depends(authenticate)])
    async def route_endpoint(body:dict):
        from tagpilot_insight.interaction import route
        from tagpilot_agent.runtime.insight_model import structured_once
        utterance=body.get('utterance','')
        if not isinstance(utterance,str) or not 1<=len(utterance)<=2000:raise HTTPException(422,'请填写洞察需求')
        return route(utterance,await admitted_once(runtime()['manager'],body.get('owner_id'),'route',{'utterance':utterance})).model_dump(mode='json')
    @app.post('/agent/insight/edit',dependencies=[Depends(authenticate)])
    async def edit_endpoint(body:dict):
        from tagpilot_insight.interaction import propose_edit
        from tagpilot_agent.runtime.insight_model import structured_once
        try:
            utterance=body['utterance']
            if not isinstance(utterance,str) or not 1<=len(utterance)<=2000:raise ValueError('改图需求超出范围')
            return propose_edit(InsightReport.model_validate(body['report']),body['skill_id'],body['chart_id'],utterance,await admitted_once(runtime()['manager'],body.get('owner_id'),'chart_edit',{'utterance':utterance,'skill_id':body['skill_id'],'chart_id':body['chart_id']}),published_hashes=body.get('published_hashes'))
        except (ValueError,KeyError,StopIteration) as e:raise HTTPException(422,str(e))
    @app.post('/agent/insight/trial',dependencies=[Depends(authenticate)])
    def trial(body:dict):
        from tagpilot_insight.fixtures import synthetic_golden_report
        from tagpilot_insight.evaluation import evaluate_pack
        reg=SkillRegistry();skill=body.get('skill_id');reg.get(skill)
        report=synthetic_golden_report();report.results=[r for r in report.results if r.skill_id==skill]
        return {'sample_only':True,'report':report.model_dump(mode='json'),'evaluation':evaluate_pack(skill)}
    @app.post('/agent/insight/evaluate',dependencies=[Depends(authenticate)])
    def evaluate(body:dict):
        from tagpilot_insight.evaluation import evaluate_pack
        return evaluate_pack(body.get('skill_id'))
