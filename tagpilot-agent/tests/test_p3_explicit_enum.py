from copy import deepcopy
from tagpilot_agent.guards.binding import remove_explicit_enum_assumptions

TAGS={1:{'name':'当前速易贷授信状态','semantic_type':'ENUM_NOMINAL'},
      2:{'name':'当前速易贷额度冻结状态','semantic_type':'ENUM_NOMINAL'}}
CODES=[{'tag_id':1,'code':'NORMAL','label':'正常'},{'tag_id':1,'code':'FROZEN','label':'冻结'}]


def plan(source='当前速易贷授信状态为正常'):
    return {'tree':{'kind':'TAG_PREDICATE','clause_id':'c','tag_id':1,'status':'BOUND',
                   'source_span':source,'operator':'=','values':['NORMAL'],'requirement_ids':['r']},
            'intent_plan':{'assumptions':[{'requirement_id':'r','status':'PUBLISHED',
                                          'definition_ref':{'tag_id':1}}]}}


def test_explicit_field_and_code_are_direct_without_fake_confirmation():
    p=plan();remove_explicit_enum_assumptions(p,TAGS,CODES)
    assert p['intent_plan']['assumptions']==[]
    assert 'assumption_confirmed' not in p['tree']


def test_fuzzy_or_two_explicit_fields_still_require_definition_confirmation():
    for source in ['当前速易贷状态正常','当前速易贷授信状态或当前速易贷额度冻结状态为正常']:
        p=plan(source);remove_explicit_enum_assumptions(p,TAGS,CODES)
        assert p['intent_plan']['assumptions']


def test_missing_value_or_failed_binding_cannot_remove_assumption():
    for change in [{'values':['FROZEN']},{'status':'GAP'},{'values':[]},
                   {'operator':'between'},{'tag_id':2}]:
        p=plan();p['tree'].update(change);remove_explicit_enum_assumptions(p,TAGS,CODES)
        assert p['intent_plan']['assumptions']


def test_numeric_threshold_and_wrong_definition_reference_stay_pending():
    p=plan();tags=deepcopy(TAGS);tags[1]['semantic_type']='NUM_AMOUNT'
    remove_explicit_enum_assumptions(p,tags,CODES);assert p['intent_plan']['assumptions']
    p=plan();p['intent_plan']['assumptions'][0]['definition_ref']['tag_id']=2
    remove_explicit_enum_assumptions(p,TAGS,CODES);assert p['intent_plan']['assumptions']


def test_negative_word_and_numeric_substring_are_not_explicit_equality():
    p=plan('当前速易贷授信状态不是正常');remove_explicit_enum_assumptions(p,TAGS,CODES)
    assert p['intent_plan']['assumptions']
    p=plan('当前速易贷授信状态为30');p['tree']['values']=['0']
    remove_explicit_enum_assumptions(p,TAGS,[{'tag_id':1,'code':'0','label':'零'}])
    assert p['intent_plan']['assumptions']


def test_real_guard_removes_only_the_unnecessary_definition_assumption(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import tagpilot_agent.guards.guard as guard
    async def ensure_details(ctx, ids):
        return None
    monkeypatch.setattr(guard, 'ensure_details', ensure_details)
    tags=deepcopy(TAGS)
    for t in tags.values():
        t.update(unit='NONE', allowed_operators=['=','in'], caliber_struct={})
    p=plan();p['tree'].pop('status');text=p['tree']['source_span'];p['tree']['value_unit']='NONE'
    p['intent_plan'].update(original_request=text,
        requirements=[{'requirement_id':'r','source_spans':[text],'business_meaning':text,'origin':'USER'}],
        logic_tree={'requirement_id':'r'})
    ctx=SimpleNamespace(request={'requirement':text,'build_id':'b','snapshot_id':'s','artifact_hash':'h'},
        eligible={1,2}, tags=tags, codes=CODES, capabilities={}, emit=lambda event:None,
        intent_emitted=False, best_errors=100, best_plan={})
    actual=asyncio.run(guard.check(p,ctx,strict=True))
    assert actual['valid'] and actual['tree']['status']=='BOUND'
    assert actual['intent_plan']['assumptions']==[]

def test_append_selected_explicit_enum_to_saved_group_has_no_source_or_definition_gate(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import tagpilot_agent.guards.guard as guard
    async def ensure_details(ctx, ids):return None
    monkeypatch.setattr(guard,'ensure_details',ensure_details)
    tags=deepcopy(TAGS)
    for t in tags.values():t.update(unit='NONE',allowed_operators=['=','in'],caliber_struct={})
    tags[3]={'tag_id':3,'name':'存款余额','semantic_type':'NUM_AMOUNT','unit':'CNY','allowed_operators':['>'],'caliber_struct':{}}
    old={'kind':'TAG_PREDICATE','clause_id':'all','source_span':'存款超过50万','requirement_ids':['all'],
         'tag_id':3,'operator':'>','values':['500000'],'value_unit':'CNY','value_scale':'1'}
    old_requirement={'requirement_id':'all','source_spans':['存款超过50万'],'business_meaning':'存款','origin':'USER'}
    saved={'valid':True,'tree':old,'intent_plan':{'original_request':'按编辑后的条件核验圈选方案',
        'requirements':[old_requirement],'logic_tree':{'requirement_id':'all'},'assumptions':[]}}
    p=plan();p['tree']['value_unit']='NONE';p['tree'].pop('status')
    text=p['tree']['source_span'];p['tree']={'logic':'AND','children':[deepcopy(old),p['tree']]}
    p['intent_plan'].update(original_request='为正常',requirements=[old_requirement,
        {'requirement_id':'r','source_spans':[text],'business_meaning':text,'origin':'USER'}],
        logic_tree={'logic':'AND','children':[{'requirement_id':'all'},{'requirement_id':'r'}]})
    request={'requirement':'为正常','build_id':'b','snapshot_id':'s','artifact_hash':'h',
        'previous_plan':{**deepcopy(saved),'valid':False},'source_plan':saved,'pinned_tag_ids':[1]}
    ctx=SimpleNamespace(request=request,eligible={1,2,3},tags=tags,codes=CODES,capabilities={},emit=lambda event:None,
        intent_emitted=False,best_errors=100,best_plan={})
    actual=asyncio.run(guard.check(p,ctx,strict=True))
    assert actual['valid'],actual['diagnostics']
    assert actual['intent_plan']['assumptions']==[]
    assert actual['tree']['children'][0]['source_span']=='存款超过50万'
