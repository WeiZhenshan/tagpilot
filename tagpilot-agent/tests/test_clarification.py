import asyncio
import pytest
from tagpilot_agent.agent.clarification import staged_questions, validate_staged_answer
import asyncio,json
from tagpilot_agent.agent.clarification import record_answer
from tagpilot_agent.agent.context_builder import build_context
from tagpilot_agent.agent.outcome import result_for
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.runtime.degrade import Reason
from tests.test_sdk_integration import manager_for,request_for
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ


def test_state_survives_history_trimming_and_budget_salvage(tmp_path):
    q={'requirement_id':'a','prompt':'金额阈值','options':['50万','100万'],'reason':'THRESHOLD_MISSING'}
    state=record_answer(REQ,[q],'50万')
    ctx=RunContext({**REQ,'clarification_state':state,'history':[]},Evidence())
    assert json.loads(asyncio.run(build_context(ctx)))['clarification_state']['records'][0]['answer']=='50万'
    store,manager=manager_for(tmp_path)
    saved=manager.salvage(ctx,Reason.TIMEOUT)
    assert saved['clarification_state']==state
    assert result_for(ctx)['clarification_state']['records']==state['records']
    store.db.close()


def test_legacy_conflicting_answer_restores_ask_in_same_thread(tmp_path):
    questions=[{'requirement_id':'R1','prompt':'选择指标','options':['客户等级','潜力等级'],'reason':'MULTIPLE_PUBLISHED_DEFINITIONS'},
               {'requirement_id':'R1','prompt':'选择档位','options':['A级','05极高'],'reason':'THRESHOLD_MISSING'}]
    class MustNotRun:
        async def run(self,*args):raise AssertionError('conflict must ask without model call')
    store,manager=manager_for(tmp_path,MustNotRun())
    prior=request_for('legacy',thread_id='same',_questions=questions,_answer='选择指标：客户等级\n选择档位：05极高')
    store.create('legacy',prior);store.status('legacy','COMPLETED',{})
    state=store.latest_clarification('same','7')
    assert len(state['pending_questions'])==1
    assert not store.latest_clarification('other','7')['records']
    assert not store.latest_clarification('same','8')['records']
    req=request_for('new',thread_id='same',continuation_of='legacy',clarification_state=state)
    store.create('new',req);asyncio.run(manager.execute('new',req))
    row=store.get('new','7')
    assert row['status']=='WAITING' and row['result']['questions']==state['pending_questions']
    assert row['result']['plan']['valid'] is False
    store.db.close()


def test_api_continuation_preserves_answer_and_idempotency(tmp_path):
    import time
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from tagpilot_agent.api.runs import register_workbench
    from tests.test_sdk_smoke import ALL,GoldRunner
    from tagpilot_agent.tools.registry import dispatch
    class Runner:
        async def run(self,ctx,prompt):
            if ctx.request.get('_answer') or ctx.request.get('continuation_of'):
                await GoldRunner().run(ctx,prompt)
            else:
                await dispatch(ctx,'submit_result',{'outcome':'NEEDS_USER_INPUT','plan':ALL,'questions':[
                    {'requirement_id':'all','clause_id':'all','prompt':'范围？','options':['全部客户','部分客户'],'reason':'GOAL_UNCLEAR'}]})
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Evidence(),'secret',tmp_path/'api.sqlite',Runner())
    req={**REQ,'requirement':'全部客户'}
    with TestClient(app) as client:
        def done(rid):
            for _ in range(100):
                row=client.get('/agent/v2/runs/'+rid,params={'owner_id':'7'}).json()
                if row['status']!='RUNNING':return row
                time.sleep(.01)
            raise AssertionError('run stalled')
        assert client.post('/agent/v2/runs',json=req).status_code==200
        assert done(req['run_id'])['status']=='WAITING'
        assert client.post('/agent/v2/runs/'+req['run_id']+'/resume',json={'owner_id':'7','answer':'全部客户','eligible_tag_ids':[1]}).status_code==200
        first=done(req['run_id'])
        assert len(first['result']['clarification_state']['records'])==1
        next_req={**req,'run_id':'continued','continuation_of':req['run_id'],'history':[],'previous_plan':first['result']['plan']}
        assert client.post('/agent/v2/runs',json={**next_req,'thread_id':'other'}).status_code==409
        assert client.post('/agent/v2/runs',json=next_req).status_code==200
        continued=done('continued')
        assert continued['result']['clarification_state']['records'][0]['answer']=='全部客户'
        assert client.post('/agent/v2/runs',json=next_req).status_code==200
        assert client.post('/agent/v2/runs',json={**next_req,'requirement':'部分客户'}).status_code==409
from tagpilot_agent.tools.registry import dispatch
from tests.test_guards import ctx_for, bound_plan, payload

QUESTIONS=[
    {'requirement_id':'a','clause_id':'a','prompt':'采用哪个价值指标？',
     'options':['上12个月最高客户等级','当前客户潜力等级'],'reason':'MULTIPLE_PUBLISHED_DEFINITIONS'},
    {'requirement_id':'a','clause_id':'a','prompt':'高对应哪个档位？',
     'options':['A级','潜力等级05=极高'],'reason':'THRESHOLD_MISSING'},
]


def test_legacy_incompatible_pair_is_staged_and_cannot_be_submitted_together():
    assert staged_questions(QUESTIONS)==QUESTIONS[:1]
    with pytest.raises(ValueError,match='先确认'):
        validate_staged_answer(QUESTIONS,'采用哪个价值指标？：上12个月最高客户等级\n高对应哪个档位？：潜力等级05=极高')
    validate_staged_answer(QUESTIONS,'上12个月最高客户等级')
    assert staged_questions(QUESTIONS[1:])==QUESTIONS[1:]


def test_other_requirement_threshold_is_not_deferred():
    second={**QUESTIONS[1],'requirement_id':'other'}
    assert len(staged_questions([QUESTIONS[0],second]))==2


def test_submit_result_only_publishes_definition_stage():
    ctx=ctx_for();ctx.searches['a']={'quick'}
    result=asyncio.run(dispatch(ctx,'submit_result',{'outcome':'NEEDS_USER_INPUT','plan':bound_plan(),'questions':QUESTIONS}))
    assert not result['is_error'],payload(result)
    assert ctx.accepted['questions']==QUESTIONS[:1]
