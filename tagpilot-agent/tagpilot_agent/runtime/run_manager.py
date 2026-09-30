"""单进程有界调度；排队不占 SDK 子进程，冷恢复不依赖图检查点。"""
import asyncio
from collections import Counter
from copy import deepcopy
import os
import time
import logging
from fastapi import HTTPException
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.agent.context_builder import build_context
from tagpilot_agent.agent.outcome import result_for
from tagpilot_agent.agent.clarification import clarification_state
from tagpilot_agent.guards.guard import check
from tagpilot_agent.guards.plan_validator import leaves
from tagpilot_agent.domain.expressions import plan_tag_ids
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from tagpilot_agent.skills.packages import extract_result
from .claude_runner import ClaudeRunner
from .budget import Budget
from .degrade import Reason, BUDGET_REASONS, LEAN_REASONS, MESSAGES, classify, degraded_info, progress

logger=logging.getLogger(__name__)

class RunManager:
    def __init__(self,store,retriever_for,runner=None):
        self.store=store;self.retriever_for=retriever_for;self.runner=runner or ClaudeRunner()
        self.limit=max(1,int(os.getenv('TAG_AGENT_MAX_CONCURRENCY','2')))
        self.queue_max=max(0,int(os.getenv('TAG_AGENT_QUEUE_MAX','24')))
        self.per_user=max(1,int(os.getenv('TAG_AGENT_PER_USER_MAX','2')))
        self.condition=asyncio.Condition();self.active=0;self.users=Counter();self.waiters=[];self.tasks={};self.contexts={}

    def capacity(self):
        if len(self.tasks)>=self.limit+self.queue_max:raise HTTPException(429,'当前使用人数较多，请稍后重试')

    def start(self,rid,request):
        task=asyncio.create_task(self.execute(rid,deepcopy(request)))
        self.tasks[rid]=task
        task.add_done_callback(lambda t:self.tasks.pop(rid,None))

    async def cancel(self,rid):
        ctx=self.contexts.get(rid)
        if ctx:ctx.submitted.set()
        async with self.condition:self.condition.notify_all()

    async def close(self):
        for task in list(self.tasks.values()):task.cancel()
        await asyncio.gather(*list(self.tasks.values()),return_exceptions=True)

    async def execute(self,rid,request):
        if request.get("profile") == "insight":
            from tagpilot_agent.api.insight import execute_insight
            return await execute_insight(self,rid,request)
        owner=request['owner_id'];admitted=False
        ctx=RunContext(request,self.retriever_for(request['library_id'],request['build_id']),
                       lambda e:self.store.emit(rid,e),lambda:self.store.get(rid,owner)['status']=='CANCELLED')
        self.contexts[rid]=ctx
        try:
            async with self.condition:
                self.waiters.append(rid)
                if self.active>=self.limit or self.users[owner]>=self.per_user:
                    ctx.emit({'type':'run.queued','position':len(self.waiters),'message':f'排队中，第 {len(self.waiters)} 位'})
                deadline=time.monotonic()+float(os.getenv('TAG_AGENT_QUEUE_TIMEOUT','20'))
                while self.active>=self.limit or self.users[owner]>=self.per_user:
                    if ctx.cancelled():return
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('queue')
                    await asyncio.wait_for(self.condition.wait(),remaining)
                self.waiters.remove(rid)
                if ctx.cancelled():return
                self.active+=1;self.users[owner]+=1;admitted=True
            ctx.started=time.monotonic()
            previous=progress(request.get('previous_plan'))
            loaded=len(self.waiters)>=max(1,int(os.getenv('TAG_AGENT_LEAN_QUEUE_DEPTH',str(self.limit))))
            ctx.lean=previous.get('reason') in LEAN_REASONS or loaded
            ctx.budget=Budget.from_env(lean=ctx.lean,skill=request.get('profile')=='skill')
            ctx.stats['lean']=ctx.lean
            ctx.emit({'type':'run.started','message':'正在运行客群技能' if request.get('profile')=='skill' else '正在理解圈选需求'})
            if request.get('profile')=='skill':
                async with asyncio.timeout(ctx.budget.hard+5):
                    output=await self.runner.run_skill(ctx)
                if not ctx.cancelled():
                    result,text=extract_result(output)
                    payload={'skill_output':text if result is not None else output}
                    if result is not None:payload['skill_result']=result
                    self.store.status(rid,'COMPLETED',payload)
                    ctx.emit({'type':'run.completed','message':'技能分析已保存'})
                return
            if ctx.lean:ctx.emit({'type':'run.lean','message':'当前使用人数较多，已启用快速模式' if loaded else '正在补全尚未确定的条件'})
            async with asyncio.timeout(ctx.budget.hard+5):
                if request.get('edited_plan'):
                    request['_manual_edit']=True
                    plan=await check(request['edited_plan'],ctx,True,True)
                    ctx.accepted={'outcome':'READY' if plan['valid'] else 'PARTIAL','plan':plan,'questions':[],'gaps':[]}
                else:
                    pending=clarification_state(request).get('pending_questions',[]) if request.get('continuation_of') else []
                    if pending:
                        plan=deepcopy(request.get('previous_plan') or {})
                        if not plan.get('tree'):self.placeholder(ctx,plan,'BUDGET_EXHAUSTED')
                        plan.update(valid=False,plan_status='NEEDS_DECISION')
                        ctx.accepted={'outcome':'NEEDS_USER_INPUT','plan':plan,'questions':pending,'gaps':[]}
                    prompt=await build_context(ctx) if not ctx.accepted else ''
                    for attempt in range(0 if ctx.accepted else 2):
                        try:
                            await self.runner.run(ctx,prompt)
                            break
                        except Exception as exc:
                            if ctx.accepted or ctx.cancelled() or ctx.stats.get('fatal_status'):break
                            if isinstance(exc,SemanticRetrieveError):raise
                            if attempt or classify(ctx,exc) in BUDGET_REASONS or ctx.budget.salvage_at()-ctx.budget.elapsed(ctx)<float(os.getenv('TAG_AGENT_RETRY_MIN_S','25')):raise
                            ctx.stats['cli_retries']=1
                            await asyncio.sleep(.5)
            if ctx.stats.get('fatal_status'):raise SemanticRetrieveError(ctx.stats['fatal_status'],'权限或发布版本发生变化')
            self.finish(ctx,classify(ctx))
        except asyncio.CancelledError:
            self.store.status(rid,'INTERRUPTED',{'skill_output':'技能运行中断，请重新选择技能后重试。'} if request.get('profile')=='skill' else self.fallback(ctx,'服务重启，已保存进度'))
            raise
        except SemanticRetrieveError as exc:
            if exc.status_code in {401,403,409}:
                self.store.status(rid,'FAILED',error='权限或发布版本发生变化，请重新核验')
                ctx.emit({'type':'run.failed','message':'权限或发布版本发生变化，请重新核验'})
            else:self.finish(ctx,classify(ctx,exc,admitted))
        except Exception as exc:
            if request.get('profile')=='skill':
                if not ctx.cancelled():
                    logger.exception('技能运行失败 run=%s stop_reason=%s stats=%s', rid, ctx.stats.get('stop_reason'),
                                     {k: v for k, v in ctx.stats.items() if k in ('cli_peak_rss_mb', 'llm_turns', 'tools', 'stopped_at', 'sdk_error')})
                    self.store.status(rid,'FAILED',error='技能运行未完成，请重新选择技能后重试')
                    ctx.emit({'type':'run.failed','message':'技能运行未完成，请重新选择技能后重试'})
            else:self.finish(ctx,classify(ctx,exc,admitted))
        finally:
            self.contexts.pop(rid,None)
            async with self.condition:
                if rid in self.waiters:self.waiters.remove(rid)
                if admitted:self.active-=1;self.users[owner]-=1
                self.condition.notify_all()

    def placeholder(self,ctx,plan,reason):
        text=ctx.request['requirement']
        plan.update(schema_version=3,tree={'kind':'TAG_PREDICATE','clause_id':'pending','source_span':text,
            'requirement_ids':['pending'],'status':'GAP','gap_reason':reason},
            intent_plan={'original_request':text,'requirements':[{'requirement_id':'pending','source_spans':[text],'business_meaning':text,'origin':'USER'}],
                         'logic_tree':{'requirement_id':'pending'},'assumptions':[]},
            **{k:ctx.request[k] for k in ('build_id','snapshot_id','artifact_hash')})

    def salvage(self,ctx,reason):
        """仅消费已有校验结果；中断 SDK 后不再触发网络或业务执行。"""
        plan=deepcopy(ctx.best_plan or ctx.request.get('previous_plan') or {})
        prior=progress(ctx.request.get('previous_plan'))
        attempt=int(prior.get('attempt',0))+1
        kept=[];unresolved=[];gaps=[];level='L2'
        if not plan.get('tree'):
            if not ctx.tags:return None
            level='L3'
            self.placeholder(ctx,plan,'BUDGET_EXHAUSTED')
            candidates=[tid for tid in ctx.tags if tid in ctx.eligible][:5]
            plan['tree']['candidates']=[{'tag_id':tid,'name':ctx.tags[tid].get('name',str(tid))} for tid in candidates]
            unresolved=['pending']
        else:
            diagnostics=plan.get('diagnostics',[])
            blocked={d['clause_id'] for d in diagnostics if d.get('clause_id')}
            same_version=all(plan.get(k)==ctx.request[k] for k in ('build_id','snapshot_id','artifact_hash'))
            for node in leaves(plan['tree']):
                cid=node['clause_id']
                pre_status=node.get('status')
                refs={cid,*node.get('requirement_ids',[])}
                blocked_hit=bool(refs & blocked)
                # 方案级诊断（无 clause_id）只说明整方案未 READY，不能把已 BOUND 的存量条件误标为预算耗尽。
                ok=same_version and not blocked_hit and pre_status=='BOUND' and plan_tag_ids([node])<=ctx.eligible
                (kept if ok else unresolved).append(cid)
                if not ok:
                    node.update(status='GAP',gap_reason='BUDGET_EXHAUSTED')
            # 历史预算诊断只能用最新一条；保留原校验诊断作为解释依据。
            if not kept:
                level='L3'
                nodes=leaves(plan['tree'])
                for node in nodes:
                    refs=set(node.get('requirement_ids',[])) | {node['clause_id']}
                    candidates=[tid for tid in ctx.tags if tid in ctx.eligible and
                                (len(nodes)==1 or refs & set(ctx.tag_requirements.get(tid,[])))][:5]
                    node['candidates']=[{'tag_id':tid,'name':ctx.tags[tid].get('name',str(tid))} for tid in candidates]
        plan['diagnostics']=[d for d in plan.get('diagnostics',[]) if d.get('code')!='BUDGET_EXHAUSTED']
        plan['diagnostics'].append({'code':'BUDGET_EXHAUSTED','reason':reason,'attempt':attempt,
                                    'message':MESSAGES[reason],'retryable':reason!=Reason.MEMORY})
        # 预算耗尽不等于已证实无业务能力，候选仍需澄清和权威核验。
        plan.update(valid=False,plan_status='DRAFT')
        ctx.stats['degraded']=degraded_info(ctx,reason,level,kept,unresolved,attempt)
        state=clarification_state(ctx.request)
        return {'plan':plan,'questions':[], 'clarification_state':state,'interrupt_id':None,
                'outcome':{'outcome':'PARTIAL','gaps':gaps,'stats':ctx.stats}}

    def fallback(self,ctx,message,reason=None):
        result=result_for(ctx);plan=result['plan']=deepcopy(result['plan'])
        if not plan.get('tree'):
            self.placeholder(ctx,plan,'RETRIEVAL_UNAVAILABLE')
        plan.update(valid=False,plan_status='RETRYABLE_FAILURE' if reason else 'DRAFT')
        plan.setdefault('diagnostics',[]).append({'code':'TRANSIENT_FAILURE','message':message,'retryable':True})
        result['outcome']['outcome']='PARTIAL';ctx.stats['agent_failure']=True
        result['questions']=[];result['interrupt_id']=None
        if reason:ctx.stats['degraded']=degraded_info(ctx,reason,'L4',[],[n['clause_id'] for n in leaves(plan['tree'])])
        return result

    def finish(self,ctx,reason=None):
        rid=ctx.request['run_id']
        if ctx.cancelled():return
        error=None
        if ctx.accepted and (reason not in BUDGET_REASONS or ctx.accepted['outcome']!='PARTIAL'):result=result_for(ctx)
        elif reason in BUDGET_REASONS:
            ctx.stats['stop_reason']=reason
            result=self.salvage(ctx,reason)
            if result is None:
                ctx.stats['budget_stop_reason']=reason
                reason=Reason.RETRIEVAL
                ctx.stats['stop_reason']=reason
                error=MESSAGES[reason];result=self.fallback(ctx,error,reason)
                if ctx.stats['budget_stop_reason']==Reason.MEMORY:
                    ctx.stats['degraded'].update(ops_alert=True,resumable=False,resume_mode='manual')
        else:
            if reason:ctx.stats['stop_reason']=reason;error=MESSAGES[reason]
            result=self.fallback(ctx,error or '运行已结束，保留当前最佳草案',reason)
        ctx.stats['elapsed_s']=round(ctx.budget.elapsed(ctx),3)
        if ctx.stats.get('degraded',{}).get('ops_alert'):
            logger.warning('Agent 内存预算超限，run_id=%s peak_rss_mb=%s',rid,ctx.stats.get('cli_peak_rss_mb'))
        status='WAITING' if result['interrupt_id'] else 'FAILED' if error else 'COMPLETED'
        self.store.status(rid,status,result,error=error)
        degraded=ctx.stats.get('degraded')
        ctx.emit({'type':'run.degraded' if degraded and status=='COMPLETED' else 'run.'+status.lower(),
                  'message':degraded['user_message'] if degraded else '等待业务选择' if status=='WAITING' else '圈选方案与处理进度已保存','stats':ctx.stats})
