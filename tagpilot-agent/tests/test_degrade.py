"""降级只保存可核验进度，不放宽条件、不触发网络或业务执行。"""
import asyncio
from copy import deepcopy
import json
import time

import pytest

from tagpilot_agent.agent.context_builder import build_context
from tagpilot_agent.domain.normalize import input_plan
from tagpilot_agent.guards.guard import check
from tagpilot_agent.guards.plan_validator import leaves
from tagpilot_agent.retrieval.cache import details_cache
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from tagpilot_agent.runtime.budget import Budget
from tagpilot_agent.runtime.claude_runner import ClaudeRunner
from tagpilot_agent.runtime.degrade import Reason, classify
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.tools.registry import dispatch
from tests.test_sdk_integration import PLAN, manager_for, request_for
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ, TAG


def payload(result):return json.loads(result['content'][0]['text'])


@pytest.mark.parametrize('stats,exc,admitted,reason',[
    ({'stop_reason':'memory_limit'},None,True,Reason.MEMORY),
    ({'sdk_result':'error_max_turns'},None,True,Reason.MAX_TURNS),
    ({'sdk_result':'error_max_budget_usd'},None,True,Reason.MAX_BUDGET),
    ({'tool_budget_hit':True},None,True,Reason.TOOL_BUDGET),
    ({'stop_reason':'timeout','sdk_error':'api_error'},None,True,Reason.GATEWAY),
    ({},TimeoutError(),False,Reason.QUEUE_TIMEOUT),
    ({},TimeoutError(),True,Reason.TIMEOUT),
    ({},SemanticRetrieveError(503,'unavailable'),True,Reason.RETRIEVAL),
    ({},RuntimeError('gateway'),True,Reason.GATEWAY),
    ({},None,True,None),
])
def test_classify(stats,exc,admitted,reason):
    ctx=RunContext(REQ,Evidence());ctx.stats.update(stats)
    assert classify(ctx,exc,admitted)==reason


def test_converge_blocks_expensive_tools_but_keeps_local_exit():
    async def scenario():
        events=[];ctx=RunContext(REQ,Evidence(),events.append)
        ctx.started-=100
        for name,args in [('find_tags',{'queries':[{'text':'转入'}],'depth':'deep'}),
                          ('get_tag_details',{'tag_ids':[1]}),('find_capabilities',{'query':'转入'})]:
            result=await dispatch(ctx,name,args)
            assert result['is_error'] and payload(result)['code']=='BUDGET_CONVERGE'
            assert payload(result)['budget']['mode']=='converge'
        quick=await dispatch(ctx,'find_tags',{'queries':[{'text':'转入'}]})
        assert not quick['is_error'] and 'budget' in payload(quick)
        checked=await dispatch(ctx,'check_plan',{'plan':PLAN})
        assert not checked['is_error'],payload(checked)
        assert not (await dispatch(ctx,'get_tag_details',{'tag_ids':[1]}))['is_error']
        submitted=await dispatch(ctx,'submit_result',{'outcome':'PARTIAL','plan':PLAN})
        assert not submitted['is_error'] and 'budget' in payload(submitted)
        assert len([e for e in events if e['type']=='budget.converging'])==1
    asyncio.run(scenario())


def test_every_error_observation_has_remaining_budget():
    ctx=RunContext(REQ,Evidence())
    malformed=asyncio.run(dispatch(ctx,'find_tags',{'queries':[]}))
    assert malformed['is_error'] and 'budget' in payload(malformed)
    ctx.stats['tools']=ctx.budget.max_tools
    blocked=asyncio.run(dispatch(ctx,'find_tags',{'queries':[{'text':'转入'}]}))
    assert ctx.stats['tool_budget_hit'] and payload(blocked)['budget']['remaining_tools']==0


@pytest.mark.parametrize('reason',[Reason.TIMEOUT,Reason.MEMORY,Reason.MAX_TURNS,Reason.MAX_BUDGET,Reason.TOOL_BUDGET])
def test_salvage_preserves_bound_and_never_valid(tmp_path,reason):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence())
    asyncio.run(check(PLAN,ctx))
    original=deepcopy(ctx.best_plan)
    ctx.best_plan['tree']={'logic':'AND','children':[ctx.best_plan['tree'],
        {'kind':'TAG_PREDICATE','clause_id':'b','source_span':'未知条件','requirement_ids':['R2'],'status':'GAP'}]}
    result=manager.salvage(ctx,reason)
    assert result['plan']['valid'] is False and result['plan']['plan_status']=='DRAFT'
    assert result['outcome']['stats']['degraded']['kept_clauses']==['a']
    assert result['outcome']['stats']['degraded']['unresolved_clause_ids']==['b']
    assert leaves(result['plan']['tree'])[1]['gap_reason']=='BUDGET_EXHAUSTED'
    assert leaves(result['plan']['tree'])[0]==original['tree']
    assert result['outcome']['stats']['degraded']['ops_alert']==(reason==Reason.MEMORY)
    store.db.close()


def test_salvage_preserves_bound_despite_global_diagnostic(tmp_path):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence())
    asyncio.run(check(PLAN,ctx))
    original=deepcopy(ctx.best_plan)
    ctx.best_plan['tree']={'logic':'AND','children':[ctx.best_plan['tree'],
        {'kind':'TAG_PREDICATE','clause_id':'b','source_span':'未知条件','requirement_ids':['R2'],'status':'GAP'}]}
    ctx.best_plan.setdefault('diagnostics',[]).append({'code':'LITERAL_DRIFT','message':'方案遗漏原始需求中的数值'})
    result=manager.salvage(ctx,Reason.TOOL_BUDGET)
    assert result['outcome']['stats']['degraded']['kept_clauses']==['a']
    assert result['outcome']['stats']['degraded']['unresolved_clause_ids']==['b']
    assert leaves(result['plan']['tree'])[0]==original['tree']
    assert leaves(result['plan']['tree'])[1]['gap_reason']=='BUDGET_EXHAUSTED'
    store.db.close()


def test_salvage_no_network_and_does_not_trust_stale_previous(tmp_path):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence());asyncio.run(check(PLAN,ctx))
    previous=deepcopy(ctx.best_plan);previous['artifact_hash']='old'
    class NoNetwork:
        def evidence(self,*args):raise AssertionError('salvage called network')
    cold=RunContext({**REQ,'previous_plan':previous},NoNetwork())
    result=manager.salvage(cold,Reason.TIMEOUT)
    assert result['outcome']['stats']['degraded']['kept_clauses']==[]
    assert result['plan']['tree']['status']=='GAP'
    store.db.close()


def test_l3_candidates_are_eligible_and_not_executable(tmp_path):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence());asyncio.run(build_context(ctx))
    result=manager.salvage(ctx,Reason.TIMEOUT)
    assert result['outcome']['stats']['degraded']['level']=='L3'
    assert result['outcome']['gaps']==[]
    assert result['plan']['tree']['candidates'][0]['name']==TAG['name']
    assert not result['plan']['valid'] and result['plan']['plan_status']=='DRAFT'
    store.db.close()


def test_retrieval_failure_returns_l4(tmp_path):
    class Unavailable(Evidence):
        def lookup(self,*args):raise SemanticRetrieveError(503,'down')
    class NoDraft:
        async def run(self,ctx,prompt):ctx.stats['stop_reason']='timeout'
    store,manager=manager_for(tmp_path,NoDraft());manager.retriever_for=lambda a,b:Unavailable()
    request=request_for('unavailable');store.create('unavailable',request)
    asyncio.run(manager.execute('unavailable',request))
    row=store.get('unavailable','7')
    assert row['status']=='FAILED' and row['result']['outcome']['stats']['degraded']['level']=='L4'
    assert row['result']['plan']['tree']['gap_reason']=='RETRIEVAL_UNAVAILABLE'
    assert row['result']['outcome']['stats']['stop_reason']=='retrieval'
    store.db.close()


def partial_plan(manager):
    ctx=RunContext(REQ,Evidence());asyncio.run(check(PLAN,ctx))
    ctx.best_plan['tree']={'logic':'AND','children':[ctx.best_plan['tree'],
        {'kind':'TAG_PREDICATE','clause_id':'b','source_span':'转入超过50万','requirement_ids':['b'],'status':'GAP','tag_id':1}]}
    ctx.best_plan['intent_plan']['requirements'].append({'requirement_id':'b','source_spans':['转入超过50万'],'business_meaning':'转入超过50万','origin':'USER'})
    ctx.best_plan['intent_plan']['logic_tree']={'logic':'AND','children':[{'requirement_id':'a'},{'requirement_id':'b'}]}
    return manager.salvage(ctx,Reason.TIMEOUT)['plan']


def test_resume_preloads_only_unresolved_and_freezes_kept(tmp_path):
    store,manager=manager_for(tmp_path);previous=partial_plan(manager);details_cache.data.clear()
    class Counting(Evidence):
        def __init__(self):self.reads=[]
        def evidence(self,ids,*args):self.reads.append(set(ids));return super().evidence(ids,*args)
        def lookup(self,*args):return {**{k:REQ[k] for k in ('build_id','snapshot_id','artifact_hash')},'tags':[]}
    evidence=Counting();ctx=RunContext({**REQ,'previous_plan':previous},evidence)
    context=json.loads(asyncio.run(build_context(ctx)))
    assert context['resume']['unresolved_clause_ids']==['b'] and context['resume']['kept_clause_ids']==['a']
    assert evidence.reads==[{1}]
    proposed=input_plan(previous)
    unresolved=proposed['tree']['children'][1]
    unresolved.pop('gap_reason',None);unresolved.update(operator='>',values=['500000'])
    repaired=asyncio.run(check(proposed,ctx))
    assert repaired['valid'],repaired['diagnostics']
    proposed['tree']['children'][0]['values']=['600000']
    invalid=asyncio.run(check(proposed,ctx))
    assert any(d['code']=='FROZEN_CLAUSE_CHANGED' for d in invalid['diagnostics'])
    proposed['tree']['children'][0]['values']=['500000'];proposed['tree']['logic']='OR'
    invalid=asyncio.run(check(proposed,ctx))
    assert any(d['code']=='LOGIC_CHANGED' for d in invalid['diagnostics'])
    store.db.close()


def test_resume_does_not_preload_kept_details(tmp_path):
    store,manager=manager_for(tmp_path);previous=partial_plan(manager)
    previous['tree']['children'][1].pop('tag_id');details_cache.data.clear()
    class NoReads(Evidence):
        def evidence(self,*args):raise AssertionError('preloaded kept tag')
        def lookup(self,*args):return {**{k:REQ[k] for k in ('build_id','snapshot_id','artifact_hash')},'tags':[]}
    context=json.loads(asyncio.run(build_context(RunContext({**REQ,'previous_plan':previous},NoReads()))))
    assert context['resume']['kept_clause_ids']==['a']
    store.db.close()


def test_resume_cap_and_manual_edit(tmp_path):
    store,manager=manager_for(tmp_path);previous=partial_plan(manager)
    for attempt in (2,3):
        ctx=RunContext({**REQ,'previous_plan':previous},Evidence())
        result=manager.salvage(ctx,Reason.TIMEOUT)
        assert result['outcome']['stats']['degraded']['attempt']==attempt
        assert result['outcome']['stats']['degraded']['resumable']==(attempt<=2)
        previous=result['plan']
    edited=input_plan(previous)
    edited['tree']['children'][1].update(tag_id=1,operator='>',values=['500000'])
    edited['tree']['children'][1].pop('gap_reason',None)
    ctx=RunContext({**REQ,'previous_plan':previous,'_manual_edit':True},Evidence())
    checked=asyncio.run(check(edited,ctx,trusted=True))
    assert checked['valid'],checked['diagnostics']
    store.db.close()


def test_lean_on_resume_or_load_and_idle_standard(tmp_path):
    class Capture:
        def __init__(self):self.contexts=[]
        async def run(self,ctx,prompt):self.contexts.append(ctx)
    capture=Capture();store,manager=manager_for(tmp_path,capture)
    previous=partial_plan(manager)
    async def run(rid,**kwargs):
        req=request_for(rid,**kwargs);store.create(rid,req);await manager.execute(rid,req)
    asyncio.run(run('idle'))
    asyncio.run(run('resume',previous_plan=previous))
    manager.waiters=['load-a','load-b']
    asyncio.run(run('loaded'))
    idle,resume,loaded=capture.contexts
    assert not idle.lean and idle.budget.hard==90
    assert resume.lean and resume.budget.max_deep==0 and resume.budget.hard==60
    assert loaded.lean and any(e['type']=='run.lean' for e in store.events('loaded'))
    store.db.close()


def test_retry_skipped_when_remaining_budget_short(tmp_path):
    class Crash:
        calls=0
        async def run(self,ctx,prompt):
            self.calls+=1;ctx.started-=80;raise RuntimeError('crash')
    runner=Crash();store,manager=manager_for(tmp_path,runner)
    req=request_for('retry');store.create('retry',req);asyncio.run(manager.execute('retry',req))
    assert runner.calls==1 and store.get('retry','7')['result']['outcome']['stats']['stop_reason']=='gateway'
    store.db.close()


def test_watch_stops_before_hard(monkeypatch):
    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT','0.5')
    class Client:
        interrupted=False
        async def interrupt(self):self.interrupted=True
    client=Client();ctx=RunContext(REQ,Evidence())
    asyncio.run(ClaudeRunner().watch(client,ctx))
    assert client.interrupted and ctx.stats['stop_reason']=='timeout'
    assert ctx.stats['stopped_at']<ctx.budget.hard


def test_lean_never_enlarges_configured_budget(monkeypatch):
    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT','3')
    monkeypatch.setenv('TAG_AGENT_SOFT_TIMEOUT','2')
    lean=Budget.from_env(lean=True)
    assert lean.hard==3 and lean.soft==2 and lean.max_deep==0


def test_guard_evidence_budget_is_shared_and_records_stop():
    from tagpilot_agent.retrieval.working_set import ensure_details
    ctx=RunContext(REQ,Evidence());ctx.stats['evidence_requests']=ctx.budget.max_details
    with pytest.raises(ValueError,match='详情读取预算已用完'):
        asyncio.run(ensure_details(ctx,{1}))
    assert ctx.stats['tool_budget_hit'] and classify(ctx)=='tool_budget'


@pytest.mark.parametrize('subtype,reason',[('error_max_turns','max_turns'),('error_max_budget_usd','max_budget')])
def test_sdk_result_records_budget_reason(monkeypatch,subtype,reason):
    import tagpilot_agent.runtime.claude_runner as module
    from claude_agent_sdk import ResultMessage
    options=[]
    class Client:
        def __init__(self,options):self.options=options
        async def __aenter__(self):options.append(self.options);return self
        async def __aexit__(self,*args):pass
        async def query(self,prompt):pass
        async def receive_response(self):
            yield ResultMessage(subtype,1,1,True,1,'fake-session')
    monkeypatch.setattr(module,'ClaudeSDKClient',Client)
    monkeypatch.setenv('ANTHROPIC_BASE_URL','http://fake.invalid')
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake')
    ctx=RunContext(REQ,Evidence());ctx.stats['llm_turns']=2
    asyncio.run(module.ClaudeRunner().session(ctx,'test','http://fake.invalid','fake'))
    assert ctx.stats['stop_reason']==reason and ctx.stats['llm_turns']==3
    assert options[0].max_turns==ctx.budget.max_turns-2


def test_partial_budget_gap_can_submit_without_claiming_capability_gap(tmp_path):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence());ctx.started-=50
    partial={'tree':{'kind':'TAG_PREDICATE','clause_id':'a','source_span':REQ['requirement'],'gap_reason':'BUDGET_EXHAUSTED'}}
    result=asyncio.run(dispatch(ctx,'submit_result',{'outcome':'PARTIAL','plan':partial}))
    assert not result['is_error'],payload(result)
    saved=manager.salvage(ctx,classify(ctx))
    assert saved['outcome']['stats']['degraded']['level']=='L3'
    assert not saved['plan']['valid'] and saved['plan']['diagnostics'][-1]['code']=='BUDGET_EXHAUSTED'
    normal=RunContext(REQ,Evidence())
    rejected=asyncio.run(dispatch(normal,'submit_result',{'outcome':'CAPABILITY_GAP','plan':partial,'gaps':[{'requirement_id':'a','reason':'NO_PUBLISHED_TAG'}]}))
    assert rejected['is_error'] and normal.accepted is None
    store.db.close()


def test_budget_resume_does_not_unlock_kept_sibling_of_same_requirement():
    from tagpilot_agent.guards.ledger import frozen_errors
    previous={'tree':{'logic':'AND','children':[
        {'kind':'TAG_PREDICATE','clause_id':'kept','requirement_ids':['R1'],'tag_id':1,'values':['500000']},
        {'kind':'TAG_PREDICATE','clause_id':'pending','requirement_ids':['R1'],'gap_reason':'BUDGET_EXHAUSTED'}]},
        'intent_plan':{'requirements':[{'requirement_id':'R1','business_meaning':'原始要求'}]}}
    proposed=deepcopy(previous);proposed['tree']['children'][1].update(tag_id=1,values=['500000'])
    assert frozen_errors(previous,proposed,'请补全',budget_clause_ids=['pending'])==[]
    proposed['tree']['children'][0]['values']=['600000']
    assert any(d['clause_id']=='kept' for d in frozen_errors(previous,proposed,'请补全',budget_clause_ids=['pending']))
    proposed['tree']['children'][0]['values']=['500000']
    proposed['intent_plan']['requirements'][0]['business_meaning']='放宽后的要求'
    assert any(d['code']=='REQUIREMENT_MISSING' for d in frozen_errors(previous,proposed,'请补全',budget_clause_ids=['pending']))


def test_existing_zero_condition_tree_recovers_candidates(tmp_path):
    store,manager=manager_for(tmp_path)
    ctx=RunContext(REQ,Evidence());asyncio.run(build_context(ctx))
    ctx.request={**REQ,'previous_plan':{'tree':{'kind':'TAG_PREDICATE','clause_id':'C1',
        'source_span':'高价值客户','requirement_ids':['R1'],'status':'GAP','values':[]},
        'intent_plan':{'original_request':'高价值客户'}}}
    saved=manager.salvage(ctx,Reason.TIMEOUT)
    info=saved['outcome']['stats']['degraded']
    assert info['level']=='L3' and info['usable_condition_count']==0
    assert '尚未形成可用条件' in info['user_message']
    assert saved['plan']['tree']['candidates']==[{'tag_id':1,'name':TAG['name']}]
    assert saved['plan']['intent_plan']['original_request']=='高价值客户'
    assert saved['plan']['valid'] is False and saved['outcome']['gaps']==[]
    store.db.close()
