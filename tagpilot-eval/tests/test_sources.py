from pathlib import Path
import json
import pytest
from tagpilot_eval.sources import parse_values, load_ddl, load_code_maps
from tagpilot_eval.io import read_jsonl

ROOT=Path(__file__).resolve().parents[2]
P0=ROOT/'tagpilot-eval/data/p0-v1'


def test_sql_parser_preserves_null_codes_and_decimals():
    assert parse_values("'03',NULL,'NULL',0.05,'a,b','O''Brien'")==['03',None,'NULL','0.05','a,b',"O'Brien"]


@pytest.mark.parametrize('value',["NOW()","1); DROP TABLE x",'NaN','true','1e5'])
def test_parser_does_not_execute_or_guess(value):
    with pytest.raises(ValueError):parse_values(value)


def test_source_denominators_and_leading_zeros():
    path=ROOT/'sql/indiv_cust'
    assert len(load_ddl(path/'01_create_L_INDVCST_LABEL.sql'))==970
    codes=load_code_maps([path/n for n in ['03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql','04_insert_L_INDVCST_LABEL_CODE_MAP_OPTION.sql','05_insert_L_INDVCST_LABEL_CODE_MAP_BRANCH.sql']])
    assert len(codes)==177 and sum(map(len,codes.values()))==1723
    assert '03' in {c['code'] for c in codes['OUTSIDE_ASSET_WAN_KYC']}
    assert any(c['status']=='DEMO_CONVENTION' for c in codes['OUTSIDE_ASSET_WAN_KYC'])


def test_real_conflicts_are_visible_not_patched():
    facts={f['tag_id']:f for f in read_jsonl(P0/'facts.jsonl')}
    assert len(facts)==969 and 525 not in facts
    assert facts[1291]['fact_status']=='UNRESOLVED'
    assert facts[1073]['fact_status']=='UNRESOLVED'
    assert facts[1076]['fact_status']=='UNRESOLVED'
    assert facts[1448]['fact_status']=='VERIFIED_SOURCE'  # DAY是计数的合法量纲
    assert not any(f['official_bank_verified'] for f in facts.values())


def test_old_dictionary_is_not_execution_truth():
    summary=json.loads((P0/'summary.json').read_text())
    assert summary['issue_codes']['FIXTURE_DICTIONARY_DRIFT']>0
    assert summary['fixture_rows_parsed']==2000
    assert summary['live_customer_content_verified'] is False
