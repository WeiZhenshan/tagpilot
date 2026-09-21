import copy
import sqlite3
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from tagpilot_agent.plan import validate_plan, leaves
from tagpilot_agent.workbench_graph import build_workbench
from tagpilot_agent.workbench_store import CipherSerializer, RunStore
from tagpilot_agent.workbench_api import register_workbench

TAG={'tag_id':1,'name':'近30天转入金额','semantic_type':'NUM_AMOUNT','allowed_operators':['>','>=','between'],'unit':'元'}
PLAN={'tree':{'logic':'AND','children':[{'clause_id':'a','source_span':'转入超过50万','query':'近30天转入金额','tag_id':1,'operator':'>','values':['500000']}]}}
REQ={'run_id':'run-0000000000001','thread_id':'thread-1','owner_id':'7','library_id':1,'build_id':'b1','snapshot_id':'s1','artifact_hash':'h1','eligible_tag_ids':[1],'requirement':'转入超过50万','previous_plan':{},'edited_plan':None,'history':[]}
class Retriever:
    def evidence(self,*args): return {'build_id':'b1','snapshot_id':'s1','artifact_hash':'h1','tags':[TAG],'code_values':[]}
    def retrieve(self,*args):return {**self.evidence(),'candidates':[{'tag_id':1,'name':TAG['name']}],'trace_id':'ev1','selection_context':{'tags':[TAG],'code_values':[]}}
class Planner:
    def __init__(self,missing=False):self.calls=0;self.missing=missing
    def decide(self,ctx):
        if ctx['phase']=='understand':return {'action':'plan','plan':copy.deepcopy(PLAN)}
        self.calls+=1
        if self.calls==1:return {'action':'tool','tool':'search_tags','clause_id':'a','query':'转入金额'}
        plan=copy.deepcopy(PLAN)
        if self.missing:plan['tree']['children'][0]['values']=[]
        return {'action':'finish','plan':plan}

def test_tree_and_numeric_boundaries():
    plan=validate_plan(copy.deepcopy(PLAN),{1:TAG},[],{1})
    assert plan['valid'] and leaves(plan['tree'])[0]['operator']=='>'
    bad=copy.deepcopy(PLAN);bad['tree']['children'][0]['values']=['NaN']
    assert not validate_plan(bad,{1:TAG},[],{1})['valid']
    assert not validate_plan(copy.deepcopy(PLAN),{1:TAG},[],set())['valid']
    bad=copy.deepcopy(PLAN);bad['tree']['children'][0].update(operator='between',values=['10','1'])
    assert not validate_plan(bad,{1:TAG},[],{1})['valid']

def test_interrupt_survives_restart_and_resume(tmp_path):
    path=str(tmp_path/'checkpoints.sqlite');config={'configurable':{'thread_id':'t1'}}
    conn=sqlite3.connect(path,check_same_thread=False)
    saver=SqliteSaver(conn,serde=CipherSerializer('private-test-key'))
    events=[];graph=build_workbench(Retriever(),saver,events.append,lambda:False,Planner(missing=True))
    result=graph.invoke({'request':REQ},config)
    assert result['__interrupt__'] and not result['plan']['valid']
    conn.close()
    assert b'500000' not in (tmp_path/'checkpoints.sqlite').read_bytes()
    conn=sqlite3.connect(path,check_same_thread=False)
    graph=build_workbench(Retriever(),SqliteSaver(conn,serde=CipherSerializer('private-test-key')),events.append,lambda:False,Planner())
    result=graph.invoke(Command(resume={'plan':copy.deepcopy(PLAN)}),config)
    assert result['plan']['valid'] and result['plan']['tree']['children'][0]['operator']=='>'
    conn.close()

def test_runtime_owner_idempotence_and_event_replay(tmp_path):
    app=FastAPI();register_workbench(app,lambda:None,lambda a,b:Retriever(),'secret',str(tmp_path/'runtime.sqlite'),Planner())
    client=TestClient(app)
    assert client.post('/agent/v2/runs',json=REQ).status_code==200
    for _ in range(100):
        result=client.get('/agent/v2/runs/'+REQ['run_id'],params={'owner_id':'7'}).json()
        if result['status']!='RUNNING':break
        time.sleep(.02)
    assert result['status']=='COMPLETED',result
    assert result['result']['plan']['valid']
    assert client.get('/agent/v2/runs/'+REQ['run_id'],params={'owner_id':'8'}).status_code==404
    assert client.post('/agent/v2/runs',json=REQ).status_code==200
    seq=result['events'][-1]['seq']
    assert client.get('/agent/v2/runs/'+REQ['run_id'],params={'owner_id':'7','after':seq}).json()['events']==[]
    changed={**REQ,'requirement':'不同内容'}
    assert client.post('/agent/v2/runs',json=changed).status_code==409

def test_store_recovery_cancel_and_encryption(tmp_path):
    path=str(tmp_path/'runs.sqlite');store=RunStore(path,'key');store.create('r',REQ)
    store.emit('r',{'message':'sensitive-customer-text'})
    store.db.close();store=RunStore(path,'key')
    assert store.get('r','7')['status']=='INTERRUPTED'
    assert store.claim('r','7')
    store.cancel('r','7');store.status('r','COMPLETED',{})
    assert store.get('r','7')['status']=='CANCELLED'
    assert b'sensitive-customer-text' not in (tmp_path/'runs.sqlite').read_bytes()

def test_units_and_time_are_not_silently_relaxed():
    p=copy.deepcopy(PLAN);n=leaves(p['tree'])[0]
    n.update(values=['50'],value_unit='CNY',value_scale='10000')
    tag={**TAG,'unit':'CNY','unit_scale':'1','caliber_struct':{'calendar_mode':'ROLLING','time_window_value':30}}
    assert validate_plan(p,{1:tag},[],{1})['valid']
    assert n['values']==['500000']
    assert validate_plan(p,{1:tag},[],{1})['valid'] and n['values']==['500000']
    n.update(time_constraint='上月',expected_caliber={'calendar_mode':'CALENDAR'})
    assert not validate_plan(p,{1:tag},[],{1})['valid']
    n.update(time_constraint=None,expected_caliber={},value_unit='USD')
    assert not validate_plan(p,{1:tag},[],{1})['valid']

def test_cancelled_run_does_not_advance_graph(tmp_path):
    graph=build_workbench(Retriever(),SqliteSaver(sqlite3.connect(str(tmp_path/'c'),check_same_thread=False)),lambda e:None,lambda:True,Planner())
    import pytest
    with pytest.raises(InterruptedError):graph.invoke({'request':REQ},{'configurable':{'thread_id':'cancel'}})

def test_negative_enum_excludes_published_unknown_codes():
    p=copy.deepcopy(PLAN);n=leaves(p['tree'])[0];n.update(operator='not_in',values=['CLOSED'])
    tag={**TAG,'semantic_type':'ENUM_NOMINAL','allowed_operators':['not_in']}
    codes=[{'tag_id':1,'code':'CLOSED'},{'tag_id':1,'code':'UNKNOWN','is_unknown_bucket':1}]
    assert validate_plan(p,{1:tag},codes,{1})['valid']
    assert set(n['values'])=={'CLOSED','UNKNOWN'} and n['null_policy']=='EXCLUDE'
