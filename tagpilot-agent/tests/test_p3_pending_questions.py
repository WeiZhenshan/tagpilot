import asyncio
import importlib

from tagpilot_agent.runtime.run_context import RunContext


def context(searches):
    return RunContext(request={'pinned_only': False, 'pinned_tag_ids': []}, retriever=None, emit=lambda event: None, searches=searches)


def test_pending_assumption_requires_question_before_freezing(monkeypatch):
    module=importlib.import_module('tagpilot_agent.tools.submit_result')
    async def check(plan,ctx,strict=False):return plan
    monkeypatch.setattr(module,'check',check)
    plan={'valid':False,'intent_plan':{'requirements':[{'requirement_id':'asset'},{'requirement_id':'app'}],
        'assumptions':[{'requirement_id':'asset','status':'PUBLISHED','definition_ref':{'tag_id':1}}]},
        'tree':{'logic':'AND','children':[
            {'clause_id':'a','requirement_ids':['asset'],'status':'ASSUMED','assumption_confirmed':False},
            {'clause_id':'b','requirement_ids':['app'],'status':'GAP'}]}}
    ctx=context({'asset':{'quick'},'app':{'quick'}})
    question=lambda rid:{'requirement_id':rid,'prompt':'请确定业务阈值','reason':'THRESHOLD_MISSING'}
    args={'plan':plan,'outcome':'NEEDS_USER_INPUT','questions':[question('app')],'gaps':[],'summary':''}
    result=asyncio.run(module.submit_result(ctx,args))
    assert result['ok'] is False and not ctx.submitted.is_set()
    assert result['available_requirement_ids']==['app','asset']
    assert result['searched_requirement_ids']==['app','asset']
    args['questions'].append(question('asset'))
    assert asyncio.run(module.submit_result(ctx,args))['accepted'] is True


def test_unchanged_confirmed_assumption_does_not_need_repeat_question(monkeypatch):
    module=importlib.import_module('tagpilot_agent.tools.submit_result')
    async def check(plan,ctx,strict=False):return plan
    monkeypatch.setattr(module,'check',check)
    plan={'valid':False,'intent_plan':{'requirements':[{'requirement_id':'asset'},{'requirement_id':'app'}],
        'assumptions':[{'requirement_id':'asset','status':'PUBLISHED'}]},
        'tree':{'logic':'AND','children':[
            {'clause_id':'a','requirement_ids':['asset'],'status':'BOUND','assumption_confirmed':True},
            {'clause_id':'b','requirement_ids':['app'],'status':'GAP'}]}}
    ctx=context({'app':{'quick'}})
    args={'plan':plan,'outcome':'NEEDS_USER_INPUT','questions':[{'requirement_id':'app','prompt':'多久未登录',
        'reason':'THRESHOLD_MISSING'}],'gaps':[],'summary':''}
    assert asyncio.run(module.submit_result(ctx,args))['accepted'] is True
