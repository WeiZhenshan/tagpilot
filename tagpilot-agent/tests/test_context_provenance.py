"""保存来源与标签点选来源不要求重述；新值和伪造来源仍需校验。"""
from copy import deepcopy
from tagpilot_agent.guards.literals import check_literals
from tagpilot_agent.guards.binding import remove_explicit_enum_assumptions

def saved():
    node={'kind':'TAG_PREDICATE','clause_id':'old','requirement_ids':['old'],
          'tag_id':1,'source_span':'存款超过50万','operator':'>','values':['500000']}
    return {'valid':True,'tree':node,'intent_plan':{'original_request':'按编辑后的条件核验圈选方案',
        'requirements':[{'requirement_id':'old','source_spans':['存款超过50万'],'business_meaning':'存款'}]}}

def test_saved_group_sources_survive_revalidation_and_new_utterance():
    source=saved();previous={**deepcopy(source),'valid':False}
    req={'requirement':'增加持卡条件','previous_plan':previous,'source_plan':source}
    assert check_literals(deepcopy(source),req,{})==[]

def test_saved_source_cannot_authorize_changed_values_or_unvalidated_draft():
    source=saved();proposed=deepcopy(source);proposed['tree']['values']=['600000']
    req={'requirement':'增加持卡条件','previous_plan':{**source,'valid':False},'source_plan':source}
    assert any(d['message']=='条件来源必须逐字引用用户原话' for d in check_literals(proposed,req,{}))
    req.pop('source_plan')
    assert any(d['code']=='LITERAL_DRIFT' for d in check_literals(source,req,{}))

def test_selected_label_plus_literal_supplement_is_user_source():
    source=saved();node={'kind':'TAG_PREDICATE','clause_id':'new','requirement_ids':['new'],
        'tag_id':2,'source_span':'当前持有信用卡标志 是','operator':'=','values':['1']}
    proposed={'tree':{'logic':'AND','children':[deepcopy(source['tree']),node]},
        'intent_plan':{'requirements':source['intent_plan']['requirements']+[
            {'requirement_id':'new','source_spans':[node['source_span']],'business_meaning':'持卡'}]}}
    req={'requirement':'是','previous_plan':source,'pinned_tag_ids':[2]}
    tags={2:{'name':'当前持有信用卡标志','semantic_type':'BOOL_FLAG'}}
    assert check_literals(proposed,req,tags)==[]
    req['pinned_tag_ids']=[]
    assert len([d for d in check_literals(proposed,req,tags) if d['code']=='LITERAL_DRIFT'])==2
    req['pinned_tag_ids']=[2];node['source_span']='当前持有信用卡标志 不持有'
    assert any(d['code']=='LITERAL_DRIFT' for d in check_literals(proposed,req,tags))

def test_new_selected_explicit_enum_does_not_reconfirm_old_definitions():
    from tests.test_p3_explicit_enum import plan, TAGS, CODES
    p=plan();p['tree']['clause_id']='new'
    old={'requirement_id':'old','status':'PUBLISHED','definition_ref':{'tag_id':1},'question':'旧口径'}
    p['intent_plan']['assumptions'].append(old)
    remove_explicit_enum_assumptions(p,TAGS,CODES,{'new'})
    assert p['intent_plan']['assumptions']==[old]
