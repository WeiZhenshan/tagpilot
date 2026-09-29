import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from tagpilot_eval.cli import main
from tagpilot_eval.contracts import CONTRACTS, EvalCase, Tree, Expression
from tagpilot_eval.io import read_jsonl, file_hash
from tagpilot_eval.validation import expected_shape, validate_package, validate_cases, verify_package

PACKAGE=Path(__file__).resolve().parents[1]
P0=PACKAGE/'data/p0-v1'
CAL=PACKAGE/'data/calibration-v1'
EXPECT=expected_shape(json.loads((CAL/'manifest.json').read_text()))


def test_delivered_cases_validate_with_both_contracts():
    cases=read_jsonl(CAL/'cases.jsonl')
    validator=Draft202012Validator(EvalCase.model_json_schema())
    for case in cases:
        EvalCase.model_validate(case)
        validator.validate(case)
    result=validate_package(P0,CAL)
    assert result['passed'] and result['case_count']==200
    assert result['formal_cases']==0


@pytest.mark.parametrize('command',['propose','compare','apply'])
def test_p3_commands_require_concrete_inputs_before_side_effect(command,tmp_path,monkeypatch,capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:main([command])
    assert error.value.code==2
    assert 'required' in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('argv',[
    ['generate','--p0','data/p0-v2','--split','data/p2-split-v1','--root','..'],
    ['case-review','--p0','data/p0-v2','--cases','data/p2-split-v1','--root','..'],
    ['run','--p0','data/p0-v2','--cases','data/p2-split-v1'],
])
def test_paid_commands_require_an_explicit_budget(argv,tmp_path,monkeypatch,capsys):
    """未设置预算只做估价、不发起调用（方案 §五.5）。"""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:main([*argv,'--output',str(tmp_path/'out')])
    assert error.value.code==2
    assert 'budget-usd' in capsys.readouterr().err
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('count',[0,199,201,2000,10000])
def test_seeding_cannot_expand_scope(count,tmp_path):
    from tagpilot_eval.seeds import seed_cases
    with pytest.raises(ValueError,match='200'):
        seed_cases(P0,PACKAGE.parent,tmp_path/'output',count)
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('field,value',[('status','APPROVED'),('secret','bad')])
def test_case_cannot_forge_approval_or_hide_fields(field,value):
    c=deepcopy(read_jsonl(CAL/'cases.jsonl')[0]);c[field]=value
    with pytest.raises(ValidationError):EvalCase.model_validate(c)


@pytest.mark.parametrize('field,value',[('phase','P2'),('split','DEV'),('split','REGRESSION'),('split','HOLDOUT')])
def test_p2_phase_and_partitions_are_accepted(field,value):
    c=deepcopy(read_jsonl(CAL/'cases.jsonl')[0]);c[field]=value
    assert EvalCase.model_validate(c).model_dump()[field]==value


def test_unknown_partition_rejected():
    c=deepcopy(read_jsonl(CAL/'cases.jsonl')[0]);c['split']='TEST'
    with pytest.raises(ValidationError):EvalCase.model_validate(c)


def test_unauthorized_gold_rejected():
    cases=read_jsonl(CAL/'cases.jsonl');cases[0]['eligible_tag_ids']=[]
    facts={r['tag_id']:r for r in read_jsonl(P0/'facts.jsonl')}
    result=validate_cases(cases,facts,file_hash(P0/'manifest.json'),EXPECT)
    assert any(e['code']=='FALSE_READY' for e in result['errors'])


def test_field_mismatch_rejected():
    cases=read_jsonl(CAL/'cases.jsonl');cases[0]['expected']['tree']['expression']['field_name']='CUST_ID'
    facts={r['tag_id']:r for r in read_jsonl(P0/'facts.jsonl')}
    assert any(e['code']=='FIELD_BINDING' for e in validate_cases(cases,facts,file_hash(P0/'manifest.json'),EXPECT)['errors'])


def test_leading_zero_cannot_be_coerced():
    case=next(c for c in read_jsonl(CAL/'cases.jsonl') if c['scenario']=='前导零码值')
    case['expected']['tree']['values']=[3]
    with pytest.raises(ValidationError):EvalCase.model_validate(case)


def test_corrupt_package_fails(tmp_path):
    (tmp_path/'cases.jsonl').write_text('altered')
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{'cases.jsonl':'0'*64}}))
    with pytest.raises(ValueError,match='hash'):verify_package(tmp_path)


def test_inputs_do_not_contain_answers():
    inputs=read_jsonl(CAL/'inputs.jsonl')
    for row in inputs:
        assert set(row)=={'input_id','requirement','reference_date','timezone'}
        assert 'expected' not in row and 'target_tag_ids' not in row


def test_shapes_reject_hidden_fields():
    with pytest.raises(ValidationError):Tree.model_validate({'kind':'SCOPE_ALL','values':['1']})
    with pytest.raises(ValidationError):Expression.model_validate({'kind':'TAG','tag_id':1,'field_name':'A','value':'3'})
    with pytest.raises(ValidationError):Expression.model_validate({'kind':'DIV','args':[]})


def test_all_public_schemas_are_valid():
    for contract in CONTRACTS.values():Draft202012Validator.check_schema(contract.model_json_schema())


@pytest.mark.parametrize('value',['bad','NaN','Infinity','1e9999999999999999999'])
def test_invalid_numeric_literal_is_validation_error(value):
    with pytest.raises(ValidationError):Expression.model_validate({'kind':'CONST','value':value})


def test_frozen_source_tampering_rejected(tmp_path):
    import gzip
    (tmp_path/'sources').mkdir()
    (tmp_path/'sources/snapshot.gz').write_bytes(gzip.compress(b'changed'))
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{},'sources':{'snapshot':{'frozen_copy':'sources/snapshot.gz','sha256':'0'*64}}}))
    with pytest.raises(ValueError,match='hash'):verify_package(tmp_path)
