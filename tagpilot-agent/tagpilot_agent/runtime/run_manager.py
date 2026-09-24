"""单进程有界调度；排队不占 SDK 子进程，冷恢复不依赖图检查点。"""
import asyncio
from collections import Counter
from copy import deepcopy
import os
import time
from fastapi import HTTPException
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.agent.context_builder import build_context
from tagpilot_agent.agent.outcome import result_for
from tagpilot_agent.guards.guard import check
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from .claude_runner import ClaudeRunner

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
            ctx.started=time.monotonic();ctx.emit({'type':'run.started','message':'正在理解圈选需求'})
            async with asyncio.timeout(float(os.getenv('TAG_AGENT_HARD_TIMEOUT','90'))+5):
                if request.get('edited_plan'):
                    request['_manual_edit']=True
                    plan=await check(request['edited_plan'],ctx,True,True)
                    ctx.accepted={'outcome':'READY' if plan['valid'] else 'PARTIAL','plan':plan,'questions':[],'gaps':[]}
                else:
                    prompt=await build_context(ctx)
                    for attempt in range(2):
                        try:
                            await self.runner.run(ctx,prompt)
                            break
                        except Exception:
                            if ctx.accepted or ctx.cancelled() or ctx.stats.get('fatal_status'):break
                            if attempt:raise
                            ctx.stats['cli_retries']=1
            if ctx.stats.get('fatal_status'):raise SemanticRetrieveError(ctx.stats['fatal_status'],'权限或发布版本发生变化')
            failure=ctx.stats.get('stop_reason') in {'memory_limit','timeout'}
            self.finish(ctx,'运行资源或时间预算已耗尽，已保存进度' if failure else None)
        except asyncio.CancelledError:
            self.store.status(rid,'INTERRUPTED',self.fallback(ctx,'服务重启，已保存进度'))
            raise
        except SemanticRetrieveError as exc:
            if exc.status_code in {401,403,409}:
                self.store.status(rid,'FAILED',error='权限或发布版本发生变化，请重新核验')
                ctx.emit({'type':'run.failed','message':'权限或发布版本发生变化，请重新核验'})
            else:self.finish(ctx,'检索暂不可用，已保存进度')
        except Exception:
            self.finish(ctx,'处理暂未完成，已保存进度供重试')
        finally:
            self.contexts.pop(rid,None)
            async with self.condition:
                if rid in self.waiters:self.waiters.remove(rid)
                if admitted:self.active-=1;self.users[owner]-=1
                self.condition.notify_all()

    def fallback(self,ctx,message):
        result=result_for(ctx);plan=result['plan']=deepcopy(result['plan'])
        if not plan.get('tree'):
            text=ctx.request['requirement']
            plan.update(schema_version=3,tree={'kind':'TAG_PREDICATE','clause_id':'pending','source_span':text,
                'requirement_ids':['pending'],'status':'GAP','gap_reason':'RETRIEVAL_UNAVAILABLE'},
                intent_plan={'original_request':text,'requirements':[{'requirement_id':'pending','source_spans':[text],'business_meaning':text,'origin':'USER'}],
                             'logic_tree':{'requirement_id':'pending'},'assumptions':[]},
                **{k:ctx.request[k] for k in ('build_id','snapshot_id','artifact_hash')})
        plan.update(valid=False,plan_status='RETRYABLE_FAILURE' if ctx.stats.get('stop_reason') in {'memory_limit','timeout'} or ctx.stats.get('cli_retries') else 'DRAFT')
        plan.setdefault('diagnostics',[]).append({'code':'TRANSIENT_FAILURE','message':message,'retryable':True})
        result['outcome']['outcome']='PARTIAL';ctx.stats['agent_failure']=True
        return result

    def finish(self,ctx,error=None):
        rid=ctx.request['run_id']
        if ctx.cancelled():return
        result=result_for(ctx) if ctx.accepted else self.fallback(ctx,error or '运行已结束，保留当前最佳草案')
        status='WAITING' if result['interrupt_id'] else 'FAILED' if error else 'COMPLETED'
        self.store.status(rid,status,result,error=error)
        ctx.emit({'type':'run.'+status.lower(),'message':'等待业务选择' if status=='WAITING' else '圈选方案与处理进度已保存','stats':ctx.stats})
