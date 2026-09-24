"""兼容 /agent/v2 协议；Java 保存长期会话，Python 只保存短期运行。"""
import fcntl
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import Depends, HTTPException
from .schemas import RunRequest, ResumeRequest, RepairRequest
from tagpilot_agent.runtime.run_store import RunStore
from tagpilot_agent.runtime.run_manager import RunManager


def register_workbench(app,authenticate,retriever_for,secret,storage_path=None,runner=None):
    resources={}
    def runtime():
        if not resources:
            if not secret:raise HTTPException(503,'编排层认证未配置')
            if os.getenv('TAG_AGENT_RUNTIME','claude_sdk')!='claude_sdk':
                raise HTTPException(503,'当前版本仅支持 claude_sdk；旧图运行时请使用迁移前版本')
            path=Path(storage_path or os.getenv('TAG_AGENT_DB','./data/agent/workbench.sqlite')).resolve()
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            lease=open(str(path)+'.lock','a')
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                lease.close();raise HTTPException(503,'运行库已被占用；请使用单个 Agent 服务进程')
            store=RunStore(str(path),os.getenv('TAG_AGENT_STORAGE_KEY') or secret)
            resources.update(store=store,lease=lease,manager=RunManager(store,retriever_for,runner))
        return resources
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            try:yield
            finally:
                if resources:
                    await resources['manager'].close()
                    resources['store'].db.close();resources['lease'].close();resources.clear()
    app.router.lifespan_context=lifespan

    def lookup(rid,owner):
        try:return runtime()['store'].get(rid,owner)
        except KeyError:raise HTTPException(404,'运行不存在')

    @app.post('/agent/v2/runs',dependencies=[Depends(authenticate)])
    async def create(request:RunRequest):
        res=runtime();payload=request.model_dump()
        try:
            try:
                row=res['store'].get(request.run_id,request.owner_id)
            except KeyError:row=None
            if row is None:res['manager'].capacity()
            if res['store'].create(request.run_id,payload):res['manager'].start(request.run_id,payload)
        except ValueError as exc:raise HTTPException(409,str(exc))
        return {'run_id':request.run_id}

    @app.get('/agent/v2/runs/{rid}',dependencies=[Depends(authenticate)])
    async def get(rid:str,owner_id:str,after:int=0):
        row=lookup(rid,owner_id)
        return {'run_id':rid,'status':row['status'],'result':row['result'],'error':row['error'],'events':runtime()['store'].events(rid,after)}

    @app.delete('/agent/v2/threads/{thread_id}',dependencies=[Depends(authenticate)])
    async def delete(thread_id:str,owner_id:str):
        try:ids=runtime()['store'].delete_thread(thread_id,owner_id)
        except ValueError as exc:raise HTTPException(409,str(exc))
        return {'thread_id':thread_id,'deleted_runs':len(ids)}

    def claim(rid,row,request,repair=False):
        res=runtime();res['manager'].capacity()
        if rid in res['manager'].tasks:raise HTTPException(409,'运行尚未释放，请稍后重试')
        if not res['store'].claim(rid,request.owner_id,completed=repair):raise HTTPException(409,'当前运行不能恢复')
        req=row['payload'];result=row['result'] or {}
        req['eligible_tag_ids']=sorted(set(req['eligible_tag_ids'])&set(request.eligible_tag_ids))
        req['confirmed_clause_ids']=request.confirmed_clause_ids
        req['previous_plan']=result.get('plan') or req.get('previous_plan',{})
        req['_generation']=req.get('_generation',0)+1
        req['edited_plan']=None
        return res,req,result

    @app.post('/agent/v2/runs/{rid}/resume',dependencies=[Depends(authenticate)])
    async def resume(rid:str,request:ResumeRequest):
        row=lookup(rid,request.owner_id)
        if row['status']=='WAITING' and request.answer in (None,'',{}):raise HTTPException(422,'请填写回答')
        res,req,result=claim(rid,row,request)
        req['_questions']=result.get('questions',[]);req['_answer']=request.answer
        if isinstance(request.answer,dict) and request.answer.get('plan'):req['edited_plan']=request.answer['plan']
        elif request.answer:
            req['_utterance']=str(request.answer)
            req['history']=[*req.get('history',[]),{'role':'user','text':req['requirement']},{'role':'user','text':str(request.answer)}][-20:]
        res['store'].update_payload(rid,req);res['manager'].start(rid,req)
        return {'run_id':rid}

    @app.post('/agent/v2/runs/{rid}/repair',dependencies=[Depends(authenticate)])
    async def repair(rid:str,request:RepairRequest):
        row=lookup(rid,request.owner_id)
        if row['payload'].get('_authority_repairs',0)>=2:raise HTTPException(409,'权威校验自动修复次数已用完')
        if any(d.get('code') in {'PERMISSION_DENIED','INELIGIBLE_TAG','VERSION_MISMATCH'} for d in request.diagnostics):raise HTTPException(409,'权限或版本错误不能自动修复')
        res,req,result=claim(rid,row,request,True)
        req['_repair']=request.diagnostics;req['_authority_repairs']=req.get('_authority_repairs',0)+1
        res['store'].update_payload(rid,req)
        res['store'].emit(rid,{'type':'plan.repairing','message':'正在根据服务端诊断修复方案'})
        res['manager'].start(rid,req)
        return {'run_id':rid}

    @app.post('/agent/v2/runs/{rid}/cancel',dependencies=[Depends(authenticate)])
    async def cancel(rid:str,request:ResumeRequest):
        lookup(rid,request.owner_id);res=runtime()
        ctx=res['manager'].contexts.get(rid)
        if ctx and ctx.best_plan:res['store'].status(rid,'RUNNING',{'plan':ctx.best_plan,'questions':[],'interrupt_id':None})
        res['store'].cancel(rid,request.owner_id);await res['manager'].cancel(rid)
        res['store'].emit(rid,{'type':'run.cancelled','message':'已停止；已完成条件保留'})
        return {'run_id':rid,'status':'CANCELLED'}
