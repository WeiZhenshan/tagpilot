"""有限冒烟：金标 A01 + SDK 工具循环、版本/权限边界、编辑路径。"""
import asyncio
import copy
import json
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tagpilot_agent.api.runs import register_workbench
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.tools.registry import dispatch
from tagpilot_agent.guards.guard import check
from tests.test_workbench import REQ, TAG

class Evidence:
    base_url='test-smoke'
    def evidence(self,ids,*args):return {'build_id':'b1','snapshot_id':'s1','artifact_hash':'h1','tags':[TAG] if 1 in ids else [],'code_values':[]}
    def lookup(self,*args):return {**self.evidence([1]),'candidates':[{'tag_id':1}], 'selection_context':{'tags':[TAG],'code_values':[]}}
    def retrieve_batch(self,queries,*args):return [self.lookup() for q in queries]
    def capabilities(self,*args):return {**self.evidence([]),'capabilities':[]}

ALL={'tree':{'kind':'SCOPE_ALL','clause_id':'all','source_span':'全部客户'},'summary':'全部客户'}
class GoldRunner:
    async def run(self,ctx,prompt):
        result=await dispatch(ctx,'submit_result',{'outcome':'READY','plan':ALL,'summary':'全部客户'})
        assert not result['is_error'],result

def test_gold_a01_api_and_edit(tmp_path):
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Evidence(),'secret',tmp_path/'runs.sqlite',GoldRunner())
    req={**REQ,'requirement':'全部客户'}
    with TestClient(app) as client:
        assert client.post('/agent/v2/runs',json=req).status_code==200
        for _ in range(100):
            result=client.get('/agent/v2/runs/'+req['run_id'],params={'owner_id':'7'}).json()
            if result['status']!='RUNNING':break
            time.sleep(.01)
        assert result['result']['plan']['valid'],result
        assert result['result']['outcome']['outcome']=='READY'
        assert client.get('/agent/v2/runs/'+req['run_id'],params={'owner_id':'other'}).status_code==404
        assert client.post('/agent/v2/runs',json=req).status_code==200
        edited={**req,'run_id':'edit-1','edited_plan':result['result']['plan']}
        assert client.post('/agent/v2/runs',json=edited).status_code==200
        for _ in range(100):
            result=client.get('/agent/v2/runs/edit-1',params={'owner_id':'7'}).json()
            if result['status']!='RUNNING':break
            time.sleep(.01)
        assert result['result']['plan']['valid'],result
        assert not (tmp_path/'runs.sqlite.checkpoints').exists()

def test_submit_requires_deep_evidence():
    async def run():
        ctx=RunContext({**REQ,'requirement':'全部客户'},Evidence())
        result=await dispatch(ctx,'submit_result',{'outcome':'CAPABILITY_GAP','plan':ALL,'gaps':[{'requirement_id':'all','reason':'NO_CAPABILITY'}]})
        assert result['is_error'] and not ctx.accepted
        await dispatch(ctx,'find_tags',{'queries':[{'text':'客户','requirement_id':'all'}],'depth':'deep'})
        result=await dispatch(ctx,'submit_result',{'outcome':'CAPABILITY_GAP','plan':ALL,'gaps':[{'requirement_id':'all','reason':'NO_CAPABILITY'}]})
        assert not result['is_error'] and ctx.accepted['plan']['valid'] is False
    asyncio.run(run())

def test_no_silent_literal_change():
    async def run():
        ctx=RunContext(REQ,Evidence())
        plan={'tree':{'kind':'TAG_PREDICATE','clause_id':'a','source_span':'转入超过50万','tag_id':1,'operator':'>','values':['600000']}}
        result=await check(plan,ctx)
        assert not result['valid'] and any(d['code']=='LITERAL_DRIFT' for d in result['diagnostics'])
    asyncio.run(run())

def test_business_codes_are_not_numeric_thresholds():
    from tagpilot_agent.guards.literals import check_literals
    plan={'tree':{'kind':'TAG_PREDICATE','clause_id':'risk','source_span':'理财风评是 C3、C4 或 C5',
                  'values':['C3','C4','C5'],'status':'BOUND'}}
    assert check_literals(plan,{**REQ,'requirement':'理财风评是 C3、C4 或 C5'}, {})==[]


def test_frozen_clause_needs_current_authorization():
    from tagpilot_agent.guards.ledger import frozen_errors
    old={'tree':{'kind':'TAG_PREDICATE','clause_id':'c','source_span':'金额50万','tag_id':1,'operator':'>','values':['500000']}}
    new=copy.deepcopy(old);new['tree']['values']=['600000']
    assert frozen_errors(old,new,'请继续')
    new['intent_changes']=[{'operation':'MODIFY','clause_ids':['c'],'source_span':'改为60万'}]
    assert not frozen_errors(old,new,'金额改为60万')


def test_api_waiting_cold_resume_and_repair(tmp_path):
    class WaitingRunner:
        async def run(self,ctx,prompt):
            if ctx.request.get('_answer') or ctx.request.get('_repair'):
                await GoldRunner().run(ctx,prompt)
            else:
                await dispatch(ctx,'submit_result',{'outcome':'NEEDS_USER_INPUT','plan':ALL,
                    'questions':[{'requirement_id':'all','clause_id':'all','prompt':'是否圈选全部客户？','options':['全部客户','部分客户'],'reason':'GOAL_UNCLEAR'}]})
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Evidence(),'secret',tmp_path/'runs.sqlite',WaitingRunner())
    req={**REQ,'requirement':'全部客户'};url='/agent/v2/runs/'+req['run_id']
    with TestClient(app) as client:
        def done():
            for _ in range(100):
                row=client.get(url,params={'owner_id':'7'}).json()
                if row['status']!='RUNNING':return row
                time.sleep(.01)
            raise AssertionError('运行未结束')
        assert client.post('/agent/v2/runs',json=req).status_code==200
        assert done()['status']=='WAITING'
        assert client.post(url+'/resume',json={'owner_id':'7','answer':'全部客户','eligible_tag_ids':[1]}).status_code==200
        assert done()['result']['plan']['valid']
        for _ in range(2):
            assert client.post(url+'/repair',json={'owner_id':'7','eligible_tag_ids':[1],'diagnostics':[{'code':'INVALID_OPERATOR','clause_id':'all','message':'核验'}]}).status_code==200
            assert done()['result']['plan']['valid']
        assert client.post(url+'/repair',json={'owner_id':'7','eligible_tag_ids':[1],'diagnostics':[{'code':'INVALID_OPERATOR'}]}).status_code==409
        assert client.post('/agent/v2/runs',json=req).status_code==200


def test_threshold_authorization_does_not_change_logic():
    from tagpilot_agent.guards.ledger import frozen_errors
    old={'tree':{'logic':'AND','children':[
        {'kind':'TAG_PREDICATE','clause_id':'a','source_span':'金额50万','tag_id':1,'operator':'>','values':['500000']},
        {'kind':'SCOPE_ALL','clause_id':'b','source_span':'全部客户'}]}}
    new=copy.deepcopy(old);new['tree']['logic']='OR'
    new['intent_changes']=[{'operation':'MODIFY','clause_ids':['a'],'source_span':'改为60万'}]
    assert any(e['code']=='LOGIC_CHANGED' for e in frozen_errors(old,new,'改为60万'))


def test_langgraph_runtime_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('TAG_AGENT_RUNTIME','langgraph')
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Evidence(),'secret',tmp_path/'runs.sqlite',GoldRunner())
    with TestClient(app) as client:
        assert client.post('/agent/v2/runs',json=REQ).status_code==503


def test_second_process_lease_is_rejected(tmp_path):
    import fcntl
    path=tmp_path/'lease.sqlite'
    holder=open(str(path)+'.lock','a')
    fcntl.flock(holder,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Evidence(),'secret',path,GoldRunner())
        with TestClient(app) as client:
            assert client.post('/agent/v2/runs',json=REQ).status_code==503
    finally:
        holder.close()


def test_assumption_confirmation_is_bound_to_previous_condition():
    from tagpilot_agent.guards.guard import unchanged_confirmations
    from tagpilot_agent.domain.plan_model import AudiencePlan
    from tagpilot_agent.domain.normalize import normalize_plan
    plan=AudiencePlan.model_validate(normalize_plan(ALL)).model_dump(exclude_none=True)
    req={'previous_plan':plan,'confirmed_clause_ids':['all']}
    assert unchanged_confirmations(plan,req)=={'all'}
    edited=copy.deepcopy(plan);edited['tree']['source_span']='所有高价值客户'
    assert unchanged_confirmations(edited,req)==set()


def test_published_assumption_manual_confirmation_flow():
    async def run():
        ctx=RunContext(REQ,Evidence())
        plan={'tree':{'kind':'TAG_PREDICATE','clause_id':'c','requirement_ids':['R1'],'source_span':'转入超过50万',
                      'tag_id':1,'operator':'>','values':['500000']},
              'intent_plan':{'original_request':'转入超过50万','requirements':[{'requirement_id':'R1','source_spans':['转入超过50万'],'business_meaning':'转入超过50万'}],
                             'logic_tree':{'requirement_id':'R1'},'assumptions':[{'requirement_id':'R1','status':'PUBLISHED','definition_ref':{'tag_id':1}}]}}
        draft=await check(plan,ctx)
        assert not draft['valid'] and draft['tree']['status']=='ASSUMED'
        confirm=RunContext({**REQ,'_manual_edit':True,'previous_plan':draft,'confirmed_clause_ids':['c']},Evidence())
        confirmed=await check(draft,confirm,trusted=True)
        assert confirmed['valid'] and confirmed['tree']['assumption_confirmed'],confirmed['diagnostics']
        edited=copy.deepcopy(draft);edited['tree']['values']=['600000']
        changed=await check(edited,confirm,trusted=True)
        assert not changed['valid'] and changed['tree']['status']=='ASSUMED'
    asyncio.run(run())
