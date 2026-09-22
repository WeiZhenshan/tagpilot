import copy
import json
import sqlite3
from pathlib import Path
import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from tagpilot_agent.expressions import inspect_expression
from tagpilot_agent.intent import capture_intent
from tagpilot_agent.plan import validate_plan
from tagpilot_agent.workbench_graph import build_workbench
from tests.test_workbench import REQ, PLAN, TAG, Retriever, Planner

FIXTURE=json.loads((Path(__file__).resolve().parents[2]/'docs/design/agent-v3/expression-contract.json').read_text())

@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda c:c['id'])
def test_shared_expression_contract(case):
    tags={t['tag_id']:t for t in FIXTURE['tags']}
    if case['valid']:
        assert inspect_expression(copy.deepcopy(case['expression']),tags,set(tags))['unit']==case['unit']
    else:
        with pytest.raises(ValueError):inspect_expression(copy.deepcopy(case['expression']),tags,set(tags))

def test_logic_and_coverage_are_preserved():
    p=copy.deepcopy(PLAN);p['tree']['children'].append({**copy.deepcopy(p['tree']['children'][0]),'clause_id':'b'})
    p['intent_plan']=capture_intent(p,'原业务要求')
    good=copy.deepcopy(p)
    # 同一业务要求拆成两个执行条件，保留逻辑与来源。
    good['tree']['children'].append({**copy.deepcopy(good['tree']['children'][0]),'clause_id':'a2'})
    assert validate_plan(good,{1:TAG},[],{1})['valid']
    p['tree']['logic']='OR'
    assert 'INTENT_LOGIC_CHANGED' in {e['code'] for e in validate_plan(p,{1:TAG},[],{1})['diagnostics']}
    p['tree']['children'].pop()
    assert 'INTENT_COVERAGE' in {e['code'] for e in validate_plan(p,{1:TAG},[],{1})['diagnostics']}

def test_all_scope_cannot_hide_other_conditions():
    p={'tree':{'clause_id':'all','kind':'SCOPE_ALL'}}
    p['intent_plan']=capture_intent(p,'全部客户')
    assert validate_plan(p,{},[],set())['valid']
    p['tree']={'logic':'AND','children':[p['tree'],copy.deepcopy(PLAN['tree']['children'][0])]}
    assert not validate_plan(p,{1:TAG},[],{1})['valid']

def test_technical_format_errors_repair_without_business_interrupt(tmp_path):
    class RepairPlanner(Planner):
        def decide(self,ctx):
            if ctx['phase']=='understand':return {'action':'plan','plan':copy.deepcopy(PLAN)}
            plan=copy.deepcopy(PLAN)
            if not ctx['validation_errors']:plan['tree']['children'][0]['values']=[]
            return {'action':'finish','plan':plan}
    with sqlite3.connect(tmp_path/'repair.sqlite',check_same_thread=False) as conn:
        graph=build_workbench(Retriever(),SqliteSaver(conn),lambda e:None,lambda:False,RepairPlanner())
        result=graph.invoke({'request':REQ},{'configurable':{'thread_id':'repair'}})
        assert '__interrupt__' not in result and result['plan']['valid']
        assert result['repairs']==2

def test_repeated_evidence_stops_with_saved_draft(tmp_path):
    class RepeatingPlanner(Planner):
        def decide(self,ctx):
            if ctx['phase']=='understand':return {'action':'plan','plan':copy.deepcopy(PLAN)}
            return {'action':'tool','tool':'search_tags','clause_id':'a','query':'近30天转入金额'}
    with sqlite3.connect(tmp_path/'loop.sqlite',check_same_thread=False) as conn:
        result=build_workbench(Retriever(),SqliteSaver(conn),lambda e:None,lambda:False,RepeatingPlanner()).invoke({'request':REQ},{'configurable':{'thread_id':'loop'}})
        assert not result['plan']['valid'] and '__interrupt__' not in result
        assert result['plan']['intent_plan']['requirements']
        assert result['calls']<REQ.get('max_calls',12)


def test_partial_model_intent_is_rebuilt_before_binding():
    p=copy.deepcopy(PLAN);p['intent_plan']={'assumptions':[{'status':'PENDING','question':'范围是否全部？'}]}
    intent=capture_intent(p,'全部客户')
    assert intent['requirements'][0]['requirement_id']=='a' and intent['logic_tree']
    assert not intent['assumptions'] and intent['hypotheses_to_check']


def test_authoritative_feedback_reenters_repair_with_bounded_attempts(tmp_path):
    import time
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from tagpilot_agent.workbench_api import register_workbench
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Retriever(),'secret',str(tmp_path/'api.sqlite'),Planner())
    with TestClient(app) as client:
        client.post('/agent/v2/runs',json=REQ)
        url='/agent/v2/runs/'+REQ['run_id']
        def completed():
            for _ in range(100):
                data=client.get(url,params={'owner_id':'7'}).json()
                if data['status']!='RUNNING':return data
                time.sleep(.01)
            raise AssertionError('repair did not terminate')
        assert completed()['status']=='COMPLETED'
        payload={'owner_id':'7','eligible_tag_ids':[1],'diagnostics':[{'code':'AUTHORITATIVE_VALIDATION','message':'请重新核验阈值'}]}
        assert client.post(url+'/repair',json={**payload,'owner_id':'other'}).status_code==404
        for _ in range(2):
            assert client.post(url+'/repair',json=payload).status_code==200
            result=completed()
            assert result['status']=='COMPLETED' and result['result']['plan']['valid']
        assert client.post(url+'/repair',json=payload).status_code==409

@pytest.mark.parametrize('value', ['not-a-tag',None,0])
def test_invalid_references_become_diagnostics(value):
    p={'tree':{'clause_id':'r','kind':'DERIVED_PREDICATE','expression':{'kind':'TAG','tag_id':value},'operator':'>','values':['0']}}
    p['intent_plan']=capture_intent(p,'余额大于零')
    assert not validate_plan(p,{1:TAG},[],{1})['valid']


def test_incremental_rewrite_cannot_silently_drop_old_condition():
    from tagpilot_agent.intent import transition_errors
    prior=copy.deepcopy(PLAN);prior['tree']['children'].append({**copy.deepcopy(prior['tree']['children'][0]),'clause_id':'b'})
    next_plan=copy.deepcopy(PLAN)
    assert transition_errors(prior,next_plan,'金额改为60万')
    next_plan['intent_changes']=[{'operation':'REMOVE','clause_ids':['b'],'source_span':'去掉风险限制'}]
    assert transition_errors(prior,next_plan,'金额改为60万')
    assert not transition_errors(prior,next_plan,'去掉风险限制')


def test_cached_evidence_for_another_clause_counts_as_coverage_progress(tmp_path):
    p=copy.deepcopy(PLAN)
    p['tree']['children']=[{**copy.deepcopy(p['tree']['children'][0]),'clause_id':f'c{i}'} for i in range(4)]
    class MultiPlanner:
        def decide(self,ctx):return {'action':'plan' if ctx['phase']=='understand' else 'finish','plan':copy.deepcopy(p)}
    with sqlite3.connect(tmp_path/'shared.sqlite',check_same_thread=False) as conn:
        result=build_workbench(Retriever(),SqliteSaver(conn),lambda e:None,lambda:False,MultiPlanner()).invoke({'request':REQ},{'configurable':{'thread_id':'shared'}})
        assert result['plan']['valid'] and result['calls']==1
