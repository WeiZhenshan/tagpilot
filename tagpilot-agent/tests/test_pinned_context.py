"""所选标签的资格、详情注入及无取值澄清边界；无真实模型或业务执行。"""
import asyncio
import copy
import json
import pytest
from pydantic import ValidationError
from tagpilot_agent.api.schemas import RunRequest
from tagpilot_agent.agent.context_builder import build_context
from tagpilot_agent.guards.guard import check
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from tagpilot_agent.tools.registry import dispatch
from tests.test_workbench import REQ, TAG

NAME='转入金额'
DETAIL={**TAG,'name':NAME,'definition_long':'已发布的金额口径','caliber_struct':{'calendar_mode':'ROLLING','time_window_value':30}}

class Evidence:
    base_url='test-pinned'
    def evidence(self,ids,*args):
        return {'build_id':'b1','snapshot_id':'s1','artifact_hash':'h1','tags':[DETAIL] if 1 in ids else [],'code_values':[]}
    def lookup(self,*args):
        # 模拟轻量 lookup 仅有名称，不能冲掉提前读入的详情。
        return {**self.evidence([]),'tags':[{'tag_id':1,'name':NAME}]}

def request(**extra):
    return {**REQ,'requirement':f'请基于所选标签「{NAME}」帮我梳理圈选条件','pinned_tag_ids':[1],'pinned_only':True,**extra}

@pytest.mark.parametrize('ids',[[1]*6,[0],[-1],[2],[1,1]])
def test_request_rejects_invalid_pinned_tags(ids):
    with pytest.raises(ValidationError):RunRequest.model_validate(request(pinned_tag_ids=ids))

def test_request_keeps_old_clients_compatible():
    assert RunRequest.model_validate(REQ).pinned_tag_ids==[]
    assert RunRequest.model_validate(request()).pinned_tag_ids==[1]

def test_context_loads_pinned_details_and_preserves_them_after_lookup():
    ctx=RunContext(request(),Evidence())
    prompt=json.loads(asyncio.run(build_context(ctx)))
    assert prompt['pinned_only'] and prompt['pinned_tags'][0]['tag_id']==1
    assert prompt['pinned_tags'][0]['allowed_operators']==TAG['allowed_operators']
    assert ctx.tags[1]['definition_long']==DETAIL['definition_long']
    assert ctx.details_loaded=={1}
    assert ctx.stats['evidence_requests']==1

def test_missing_pinned_evidence_fails_closed():
    class Missing(Evidence):
        def evidence(self,*args):return super().evidence([])
    with pytest.raises(SemanticRetrieveError):asyncio.run(build_context(RunContext(request(),Missing())))

def plan():
    return {'tree':{'kind':'TAG_PREDICATE','clause_id':'selected','requirement_ids':['selected'],'source_span':NAME}}

def test_only_selection_cannot_invent_a_threshold_or_ready_plan():
    ctx=RunContext(request(),Evidence())
    guessed=plan();guessed['tree'].update(tag_id=1,operator='>',values=['500000'])
    result=asyncio.run(check(copy.deepcopy(guessed),ctx))
    assert not result['valid']
    assert any(d['code']=='BUSINESS_AMBIGUITY' for d in result['diagnostics'])
    result=asyncio.run(dispatch(ctx,'submit_result',{'outcome':'READY','plan':guessed,'summary':'猜测的条件'}))
    assert result['is_error'] and not ctx.accepted

def test_supplement_without_threshold_cannot_use_number_in_tag_name_as_threshold():
    ctx=RunContext(request(pinned_only=False,requirement=f'请基于所选标签「{NAME}」梳理，阈值请询问我'),Evidence())
    guessed=plan();guessed['tree'].update(tag_id=1,operator='>',values=['500000'])
    result=asyncio.run(check(guessed,ctx))
    assert not result['valid']
    assert any(d['message']=='所选数值标签尚未指定阈值，请先向用户确认' for d in result['diagnostics'])

def test_only_selection_cannot_turn_into_scope_all():
    ctx=RunContext(request(),Evidence())
    guessed={'tree':{'kind':'SCOPE_ALL','clause_id':'all','source_span':NAME}}
    result=asyncio.run(check(guessed,ctx))
    assert not result['valid']

def test_answering_only_logic_cannot_fill_a_pending_numeric_threshold():
    previous=plan();previous['tree']['status']='NEEDS_DECISION'
    ctx=RunContext(request(previous_plan=previous,_answer='同时满足',_utterance='同时满足'),Evidence())
    guessed=plan();guessed['tree'].update(tag_id=1,operator='>',values=['500000'])
    result=asyncio.run(check(guessed,ctx))
    assert not result['valid']
    assert any(d['message']=='所选数值标签尚未指定阈值，请先向用户确认' for d in result['diagnostics'])

def test_selected_details_allow_asking_without_redundant_search():
    ctx=RunContext(request(),Evidence());asyncio.run(build_context(ctx))
    result=asyncio.run(dispatch(ctx,'submit_result',{'outcome':'NEEDS_USER_INPUT','plan':plan(),
        'questions':[{'requirement_id':'selected','clause_id':'selected','prompt':'转入金额采用什么比较方式和阈值？',
                      'options':['大于指定金额','至少指定金额'],'reason':'THRESHOLD_MISSING'}]}))
    assert not result['is_error'],result
    assert ctx.accepted['outcome']=='NEEDS_USER_INPUT'
    assert not ctx.accepted['plan']['valid']
    assert not ctx.accepted['plan']['tree'].get('operator')
    assert not ctx.accepted['plan']['tree'].get('values')

def test_explicit_answer_can_bind_selected_tag():
    ctx=RunContext(request(_answer='转入金额超过50万',_utterance='转入金额超过50万'),Evidence())
    explicit=plan();explicit['tree'].update(source_span='转入金额超过50万',tag_id=1,operator='>',values=['500000'])
    result=asyncio.run(check(explicit,ctx))
    assert result['valid'],result['diagnostics']
