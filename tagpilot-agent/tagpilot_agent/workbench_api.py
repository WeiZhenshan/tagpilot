"""内部运行协议；只有 Java 服务可访问，归属由可信网关注入。"""
from __future__ import annotations
import os
import sqlite3
import threading
import fcntl
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from .workbench_store import RunStore, CipherSerializer
from .workbench_graph import build_workbench


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    thread_id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    owner_id: str = Field(min_length=1, max_length=64)
    library_id: int = Field(gt=0)
    build_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    snapshot_id: str
    artifact_hash: str
    eligible_tag_ids: list[int] = Field(max_length=100000)
    requirement: str = Field(min_length=1, max_length=2000)
    previous_plan: dict = Field(default_factory=dict)
    edited_plan: dict | None = None
    history: list[dict] = Field(default_factory=list, max_length=20)


class RepairRequest(BaseModel):
    owner_id: str
    diagnostics: list[dict] = Field(min_length=1, max_length=20)
    eligible_tag_ids: list[int] = Field(max_length=100000)


class ResumeRequest(BaseModel):
    owner_id: str
    answer: str | dict | None = None
    eligible_tag_ids: list[int] = Field(default_factory=list, max_length=100000)


def register_workbench(app, authenticate, retriever_for, secret, storage_path=None, planner=None):
    lock = threading.Lock()
    resources = {}

    def runtime():
        with lock:
            if not resources:
                if not secret:
                    raise HTTPException(503, '编排层认证未配置')
                path = Path(storage_path or os.getenv('TAG_AGENT_DB', './data/agent/workbench.sqlite')).resolve()
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                lease = open(str(path) + '.lock', 'a')
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lease.close()
                    raise HTTPException(503, '该检查点库已有运行进程；请使用单个 Agent 服务进程')
                store = RunStore(str(path), os.getenv('TAG_AGENT_STORAGE_KEY') or secret)
                checkpoint_path = str(path) + '.checkpoints'
                conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
                os.chmod(checkpoint_path, 0o600)
                saver = SqliteSaver(conn, serde=CipherSerializer(os.getenv('TAG_AGENT_STORAGE_KEY') or secret))
                saver.setup()
                resources.update(store=store, saver=saver, lease=lease, pool=ThreadPoolExecutor(max_workers=4, thread_name_prefix='agent-v2'))
            return resources

    def close():
        if resources:
            resources['pool'].shutdown(wait=True)
            resources['store'].db.close()
            resources['saver'].conn.close()
            resources['lease'].close()
    original_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            try:
                yield
            finally:
                close()
    app.router.lifespan_context = lifespan

    def lookup(rid, owner):
        try:
            return runtime()['store'].get(rid, owner)
        except KeyError:
            raise HTTPException(404, '运行不存在')

    def execute(rid, req, answer=None, resume=False, repair=None):
        res = runtime(); store = res['store']
        graph = build_workbench(retriever_for(req['library_id'], req['build_id']), res['saver'],
            lambda event: store.emit(rid, event), lambda: store.get(rid, req['owner_id'])['status']=='CANCELLED', planner)
        config = {'configurable': {'thread_id': rid}, 'recursion_limit': 240}
        try:
            if repair:
                snapshot = graph.get_state(config)
                values = snapshot.values
                plan = dict(values.get('plan') or {})
                plan.update(valid=False, plan_status='DRAFT', diagnostics=repair, validation_errors=repair)
                graph.update_state(config, {'request': req, 'plan': plan, 'done': False, 'terminal': False,
                    'no_progress': 0, 'repairs': 0, 'authority_repairs': values.get('authority_repairs', 0)+1,
                    'questions': [], 'action': {'action': 'continue'}}, as_node='replan')
                arg = None
            elif resume:
                snapshot = graph.get_state(config)
                # 权限可收紧；检查点不保留旧的资格来绕过最新授权。
                graph.update_state(config, {'request': req})
                arg = Command(resume=answer) if snapshot.interrupts else None
            else:
                arg = {'request': req}
            result = graph.invoke(arg, config)
            if store.get(rid, req['owner_id'])['status'] == 'CANCELLED':
                return
            interrupts = result.get('__interrupt__') or []
            output = {'plan': result.get('plan', {}), 'questions': [], 'interrupt_id': None}
            if interrupts:
                output.update(interrupt_id=interrupts[0].id, **interrupts[0].value)
            status = 'WAITING' if interrupts else 'COMPLETED'
            store.status(rid, status, output)
            ready = output['plan'].get('valid')
            store.emit(rid, {'type': 'run.'+status.lower(), 'message': '等待业务选择' if interrupts else '圈选方案已生成' if ready else '已保留方案与待处理事项'})
        except InterruptedError:
            store.cancel(rid, req['owner_id'])
        except Exception as exc:
            # 不向客户端泄露请求凭据、模型供应商响应或内部栈。
            message = str(exc) if isinstance(exc, ValueError) else '处理暂未完成，可从已保存状态重试'
            store.status(rid, 'FAILED', error=message)
            store.emit(rid, {'type': 'run.failed', 'message': message})

    @app.post('/agent/v2/runs', dependencies=[Depends(authenticate)])
    def create_run(request: RunRequest):
        res = runtime(); payload = request.model_dump()
        try:
            if res['store'].create(request.run_id, payload):
                res['pool'].submit(execute, request.run_id, payload)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return {'run_id': request.run_id}

    @app.get('/agent/v2/runs/{rid}', dependencies=[Depends(authenticate)])
    def get_run(rid: str, owner_id: str, after: int = 0):
        row = lookup(rid, owner_id)
        return {'run_id': rid, 'status': row['status'], 'result': row['result'], 'error': row['error'],
                'events': runtime()['store'].events(rid, after)}

    @app.post('/agent/v2/runs/{rid}/resume', dependencies=[Depends(authenticate)])
    def resume_run(rid: str, request: ResumeRequest):
        row = lookup(rid, request.owner_id); res = runtime()
        if not res['store'].claim(rid, request.owner_id):
            raise HTTPException(409, '该运行当前不能恢复')
        req = row['payload']
        req['eligible_tag_ids'] = sorted(set(req['eligible_tag_ids']) & set(request.eligible_tag_ids))
        res['pool'].submit(execute, rid, req, request.answer, True)
        return {'run_id': rid}


    @app.post('/agent/v2/runs/{rid}/repair', dependencies=[Depends(authenticate)])
    def repair_run(rid: str, request: RepairRequest):
        row = lookup(rid, request.owner_id); res = runtime()
        config = {'configurable': {'thread_id': rid}}
        graph = build_workbench(retriever_for(row['payload']['library_id'], row['payload']['build_id']), res['saver'], lambda e:None, lambda:False, planner)
        snapshot = graph.get_state(config)
        if snapshot.values.get('authority_repairs', 0) >= 2:
            raise HTTPException(409, '权威校验自动修复次数已用完')
        if row['status'] != 'COMPLETED' or not res['store'].claim(rid, request.owner_id, completed=True):
            raise HTTPException(409, '当前运行不能自动修复')
        req = row['payload']; req['eligible_tag_ids'] = sorted(set(req['eligible_tag_ids']) & set(request.eligible_tag_ids))
        res['store'].emit(rid, {'type':'plan.repairing','message':'正在根据服务端核验结果修复方案'})
        res['pool'].submit(execute, rid, req, repair=request.diagnostics)
        return {'run_id': rid}

    @app.post('/agent/v2/runs/{rid}/cancel', dependencies=[Depends(authenticate)])
    def cancel_run(rid: str, request: ResumeRequest):
        lookup(rid, request.owner_id)
        runtime()['store'].cancel(rid, request.owner_id)
        runtime()['store'].emit(rid, {'type': 'run.cancelled', 'message': '已停止；已完成条件保留'})
        return {'run_id': rid, 'status': 'CANCELLED'}
