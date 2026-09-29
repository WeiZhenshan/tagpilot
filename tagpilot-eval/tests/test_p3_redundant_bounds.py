from copy import deepcopy
import pytest
from tagpilot_eval.oracle import grade_tree,evaluate


def p(op,value,tid=1,field='A'):
    return {'kind':'PREDICATE','expression':{'kind':'TAG','tag_id':tid,'field_name':field,'unit':'CNY'},
        'operator':op,'values':[value],'data_kind':'NUMBER','caliber':{}}


def group(*children,logic='AND'):return {'kind':'GROUP','logic':logic,'children':list(children)}


@pytest.mark.parametrize('weak,strong',[(p('>','0'),p('>=','550000')),
    (p('>=','550000'),p('>','550000')),(p('<=','5'),p('<','3'))])
def test_same_field_and_dominated_boundary_is_proven_equivalent(weak,strong):
    actual=group(weak,strong)
    assert grade_tree(strong,actual)['status']=='PASS'
    for value in [None,'-1','0','2.99','3','5','549999.99','550000','550000.01']:
        assert evaluate(strong,{'A':value})==evaluate(actual,{'A':value})


def test_dominance_does_not_erase_wrong_threshold_or_changed_logic():
    expected=p('>=','550000')
    assert grade_tree(expected,group(p('>','0'),p('>=','540000')))['status']=='FAIL'
    assert grade_tree(expected,group(p('>','0'),expected,logic='OR'))['status']=='FAIL'
    assert grade_tree(expected,group(p('>','0'),p('>','550000')))['status']=='FAIL'


def test_different_binding_unit_caliber_or_null_policy_never_merges():
    expected=p('>=','550000');weak=p('>','0')
    variants=[p('>','0',2,'B'),deepcopy(weak),deepcopy(weak),deepcopy(weak)]
    variants[1]['expression']['unit']='COUNT'
    variants[2]['caliber']={'statistic':'AVG_DAILY'}
    variants[3]['null_policy']='PROPAGATE'
    for variant in variants:assert grade_tree(expected,group(variant,expected))['status']!='PASS'
