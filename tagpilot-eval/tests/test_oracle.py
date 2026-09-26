from copy import deepcopy
from decimal import Decimal
import pytest
from tagpilot_eval.oracle import evaluate, grade_tree, fixture_result, EvidenceError


def p(op='>=',values=None,kind='NUMBER',field='AMT',tid=1):
    return {'kind':'PREDICATE','expression':{'kind':'TAG','tag_id':tid,'field_name':field,'unit':'CNY'},
            'operator':op,'values':values if values is not None else ['500000'],'data_kind':kind}


@pytest.mark.parametrize('value,expected',[(None,False),('499999.99',False),('500000',True),('500000.01',True),('0',False),('-1',False)])
def test_closed_threshold(value,expected):assert evaluate(p(),{'AMT':value}) is expected


def test_strict_and_inclusive_are_not_equivalent():
    result=grade_tree(p(),p('>'))
    assert result['status']=='FAIL' and not result['checks']['boundary_equal']


def test_same_count_different_ids_is_not_pass():
    rows=[{'CUST_ID':'a','AMT':'10'},{'CUST_ID':'b','AMT':'20'}]
    result=grade_tree(p('>=',['20']),p('<',['20']),rows)
    assert result['evidence']['expected_count']==result['evidence']['actual_count']==1
    assert result['status']=='FAIL' and not result['checks']['full_id_set_equal']


def test_equivalent_group_and_code_order_pass():
    a=p('in',['01','02'],'STRING','CODE',2)
    b=p('in',['02','01'],'STRING','CODE',2)
    left={'kind':'GROUP','logic':'AND','children':[p(),a]}
    right={'kind':'GROUP','logic':'AND','children':[b,p()]}
    assert grade_tree(left,right)['status']=='PASS'


def test_null_is_not_zero_or_negative_membership():
    row={'AMT':None}
    assert not evaluate(p('<=',['0']),row)
    assert not evaluate(p('not_in',['C1','C2'],'STRING'),row)
    assert evaluate(p('is_null',[],'STRING'),row)


def test_date_endpoints():
    tree=p('between',['2026-09-19','2026-10-18'],'DATE')
    assert not evaluate(tree,{'AMT':'2026-09-18'})
    assert evaluate(tree,{'AMT':'2026-09-19'})
    assert evaluate(tree,{'AMT':'2026-10-18'})
    assert not evaluate(tree,{'AMT':'2026-10-19'})


def test_decimal_avoids_float_error():
    tree=p('=',['0.3'])
    tree['expression']={'kind':'ADD','args':[{'kind':'CONST','value':'0.1'},{'kind':'CONST','value':'0.2'}]}
    assert evaluate(tree,{})


def test_division_zero_and_unknown():
    tree=p('>=',['0.8'])
    tree['expression']={'kind':'DIV','args':[{'kind':'TAG','tag_id':1,'field_name':'A'},{'kind':'TAG','tag_id':2,'field_name':'B'}]}
    assert not evaluate(tree,{'A':'1','B':'0'})
    assert not evaluate(tree,{'A':None,'B':'10'})
    assert evaluate(tree,{'A':'8','B':'10'})


def test_positive_count_excludes_unknown():
    tree=p('=',['1'])
    tree['expression']={'kind':'COUNT_POSITIVE','args':[{'kind':'TAG','tag_id':1,'field_name':'A'},{'kind':'TAG','tag_id':2,'field_name':'B'}]}
    assert evaluate(tree,{'A':'1','B':'0'})
    assert not evaluate(tree,{'A':'1','B':None})


def test_missing_evidence_is_invalid_not_null():
    with pytest.raises(EvidenceError):evaluate(p(),{})
    assert grade_tree(p(),p(),[{'CUST_ID':'x'}])['status']=='RUN_INVALID'


def test_hallucinated_binding_fails():
    assert grade_tree(p(),p(field='B',tid=2))['status']=='FAIL'


def test_extra_valid_flag_cannot_earn_reward():
    actual=p();actual['valid']=True
    assert grade_tree(p(),actual)['status']=='FAIL'


def test_group_logic_change_fails():
    expected={'kind':'GROUP','logic':'AND','children':[p(),p('<',['600000'])]}
    actual=deepcopy(expected);actual['logic']='OR'
    assert grade_tree(expected,actual)['status']=='FAIL'


def test_two_bounds_keep_both_probe_endpoints():
    from tagpilot_eval.oracle import boundary_rows
    tree={'kind':'GROUP','logic':'AND','children':[p('>=',['3']),p('<=',['10'])]}
    values={r['AMT'] for r in boundary_rows(tree)}
    assert {'2.99','3','3.01','9.99','10','10.01'}<=values


def test_same_tag_wrong_field_is_failure_not_missing_evidence():
    assert grade_tree(p(),p(field='B'))['status']=='FAIL'
