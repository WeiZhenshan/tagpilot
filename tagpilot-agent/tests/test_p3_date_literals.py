import pytest
from tagpilot_agent.guards.literals import check_literals

def plan(span,values):
 return {'tree':{'kind':'TAG_PREDICATE','clause_id':'date','tag_id':858,'source_span':span,'values':values,'operator':'between'}}

@pytest.mark.parametrize('text',[
 '到期日[2026-09-19,2026-09-30]',
 '2026年9月19日到2026-09-30到期',
 '9月19号到2026-09-30到期'])
def test_dates_are_atomic_literals(text):
 assert check_literals(plan(text,['2026-09-19','2026-09-30']),{'requirement':text,'reference_date':'2026-09-18'},{858:{'semantic_type':'DATE'}})==[]

@pytest.mark.parametrize('context',[{}, {'reference_date':None}, {'reference_date':'2025-09-18'}])
def test_mixed_year_range_uses_explicit_endpoint_without_reference_date(context):
 text='盯一下下一笔定期，9月19号到2026-09-30到期的，两头都含'
 assert check_literals(plan(text,['2026-09-19','2026-09-30']),{'requirement':text,**context},{858:{'semantic_type':'DATE'}})==[]

@pytest.mark.parametrize('text,values',[
 ('2026年9月19日到9月30号到期',['2026-09-19','2026-09-30']),
 ('12月20号到2026-01-10到期',['2025-12-20','2026-01-10']),
 ('2025-12-20至1月10号到期',['2025-12-20','2026-01-10'])])
def test_omitted_year_preserves_range_order(text,values):
 assert check_literals(plan(text,values),{'requirement':text},{858:{'semantic_type':'DATE'}})==[]

def test_yearless_range_requires_reference_and_never_uses_model_year():
 text='9月19号到9月30号到期'
 p=plan(text,['2026-09-19','2026-09-30'])
 errors=check_literals(p,{'requirement':text,'reference_date':None},{858:{'semantic_type':'DATE'}})
 assert len(errors)==2 and all('缺少年份' in e['message'] for e in errors)
 assert check_literals(p,{'requirement':text,'reference_date':'2026-09-18'},{858:{'semantic_type':'DATE'}})==[]

@pytest.mark.parametrize('text,values',[
 ('9月19号到2026-09-30到期',['2027-09-19','2026-09-30']),
 ('9月19号到2026-09-30到期',['2026-09-19']),
 ('2月30号到2026-03-01到期',['2026-02-28','2026-03-01']),
 ('12月20号到2026-01-10到期',['2026-12-20','2026-01-10'])])
def test_inferred_year_does_not_allow_wrong_or_missing_endpoints(text,values):
 errors=check_literals(plan(text,values),{'requirement':text},{858:{'semantic_type':'DATE'}})
 assert errors and all(e['code']=='LITERAL_DRIFT' for e in errors)
 assert all('原话中的数值' not in e['message'] for e in errors)

def test_wrong_or_omitted_date_endpoint_is_rejected():
 text='到期日[2026-09-19,2026-09-30]'
 assert any(e['code']=='LITERAL_DRIFT' for e in check_literals(plan(text,['2027-09-19','2026-09-30']),{'requirement':text},{858:{'semantic_type':'DATE'}}))
 assert any(e['code']=='LITERAL_DRIFT' for e in check_literals(plan(text,['2026-09-19']),{'requirement':text},{858:{'semantic_type':'DATE'}}))

def test_date_does_not_hide_extra_amount():
 text='2026-09-19到2026-09-30到期，金额20万元'
 assert check_literals(plan(text,['2026-09-19','2026-09-30']),{'requirement':text},{858:{'semantic_type':'DATE'}})

def test_clarification_modify_uses_question_authorization_only():
    from copy import deepcopy
    from tagpilot_agent.guards.ledger import frozen_errors
    old={'tree':{'logic':'AND','children':[
      {'kind':'TAG_PREDICATE','clause_id':'c1','requirement_ids':['R1'],'tag_id':1,'operator':'>=','values':['20']},
      {'kind':'TAG_PREDICATE','clause_id':'c2','requirement_ids':['R2'],'tag_id':2,'operator':'=','values':['0']}]}}
    new=deepcopy(old);new['tree']['children'][0]['values']=['30']
    new['intent_changes']=[{'operation':'MODIFY','clause_ids':['c1'],'source_span':'30万'}]
    assert frozen_errors(old,new,'30万',['R1'])==[]
    assert frozen_errors(old,new,'30万',[])  # 无提问授权的纯数字仍不可修改
    new['tree']['children'][1]['values']=['1']
    assert frozen_errors(old,new,'30万',['R1'])  # 不能修改其它叶子
    new=deepcopy(old);new['tree']['children']=new['tree']['children'][:1]
    new['intent_changes']=[{'operation':'REMOVE','clause_ids':['c2'],'source_span':'30万'}]
    assert frozen_errors(old,new,'30万',['R1','R2'])  # 回答不能授权删除

def test_observation_trims_optional_family_before_requested_tags():
    import json
    from tagpilot_agent.tools.cards import observation
    data={'tags':[{'tag_id':1,'unit':'CNY','caliber_struct':{'statistic':'EOP'},
        'family_members':[{'name':'x'*3000} for _ in range(8)]},
        {'tag_id':2,'unit':'NONE','code_values':[{'code':'C3'},{'code':'C4'},{'code':'C5'}]}]}
    result=json.loads(observation(data)['content'][0]['text'])
    assert [t['tag_id'] for t in result['tags']]==[1,2]
    assert result['tags'][1]['code_values']==data['tags'][1]['code_values']
    assert len(json.dumps(result,ensure_ascii=False).encode())<6144

def test_observation_preserves_each_query_when_candidates_are_large():
    import json
    from tagpilot_agent.tools.cards import observation
    result=json.loads(observation({'results':[{'requirement_id':f'R{i}',
        'cards':[{'tag_id':j,'name':'x'*300} for j in range(8)]} for i in range(3)]})['content'][0]['text'])
    assert [r['requirement_id'] for r in result['results']]==['R0','R1','R2']
    assert all(r['cards'] for r in result['results'])

def test_explicit_name_rejects_similar_field_but_ambiguous_alias_does_not():
    from tagpilot_agent.guards.binding import check_named_binding
    tags={721:{'name':'当前时点AUM'},722:{'name':'当前AUM月日均余额'},735:{'name':'当前时点AUM（本行）'}}
    p={'tree':{'kind':'TAG_PREDICATE','clause_id':'c','tag_id':722,'source_span':'当前时点AUM至少55万'}}
    assert check_named_binding(p,tags)[0]['expected']['tag_id']==721
    p['tree']['source_span']='当前时点AUM（本行）至少55万'
    assert check_named_binding(p,tags)[0]['expected']['tag_id']==735
    p['tree']['tag_id']=735
    assert check_named_binding(p,tags)==[]
    for t in tags.values():t['aliases']=[{'alias_text':'资产余额','review_status':'REVIEWED'}]
    p['tree']['source_span']='资产余额至少55万'
    assert check_named_binding(p,tags)==[]

def test_month_of_year_is_time_not_amount_and_alias_is_checked():
    from tagpilot_agent.domain.expressions import check_caliber,time_signature
    from tagpilot_agent.guards.diagnostics import PlanError
    tag={'caliber_struct':{'time_anchor_type':'YEAR_OFFSET','time_offset_years':1,'month_of_year':12}}
    n={'expected_caliber':{'month':12},'source_span':'上年12月保险购买金额至少10万元',
       'clause_id':'m','tag_id':1009,'operator':'>=','values':['100000'],'caliber_struct':tag['caliber_struct']}
    check_caliber(n,tag)
    assert n['expected_caliber']=={'month_of_year':12}
    assert check_literals({'tree':n},{'requirement':n['source_span']},{1009:{'semantic_type':'NUM_AMOUNT'}})==[]
    assert time_signature(tag['caliber_struct'])!=time_signature({**tag['caliber_struct'],'month_of_year':11})
    with pytest.raises(PlanError):check_caliber({'expected_caliber':{'month':11}},tag)
    with pytest.raises(PlanError):check_caliber({'expected_caliber':{'month':11,'month_of_year':12}},tag)
