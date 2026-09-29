import json
from pathlib import Path
from tagpilot_eval.contracts import EvalCase
from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p3_demo import build_demo
from tagpilot_eval.oracle import fixture_result
from tagpilot_eval.l2 import _fixture_rows
from tagpilot_eval.validation import verify_package

ROOT=Path(__file__).parents[1]

def test_p3_demo_is_fixed_100_and_truth_precedes_agent(tmp_path):
    p0=ROOT/'data/p3-facts-v2'
    cases=build_demo(p0,tmp_path/'demo')
    assert len(cases)==100
    assert len({c['requirement'] for c in cases})==100
    assert len({c['scenario'] for c in cases})==7
    assert all(c['phase']=='P3' and c['split']=='DEV' for c in cases)
    assert sum(bool(c['turns']) for c in cases)==40
    rows=_fixture_rows(json.loads((p0/'manifest.json').read_text()))
    oracle=read_jsonl(tmp_path/'demo/oracle-results.jsonl')
    for c,result in zip(cases,oracle):
        EvalCase.model_validate(c)
        tree=(c['turns'] or [{'expected':c['expected']}])[-1]['expected']['tree']
        assert fixture_result(tree,rows)['ids_sha256']==result['ids_sha256']

def test_changeset_has_no_composite_alias_or_holdout_query():
    pack=json.loads((ROOT/'changes/p3-semantic-v1/changeset.json').read_text())
    p2={c['case_id']:c for c in read_jsonl(ROOT/'data/p2-cases-v3/cases.jsonl')}
    assert all(p2[cid]['split']!='HOLDOUT' for cid in pack['source_case_ids'])
    for change in pack['changes']:
        assert change['after']['source_ref']
        assert 'before' in change
        if change['table']=='ts_alias':
            assert not any(word in change['after']['alias_text'] for word in ['至少','万元','并且','同时'])


def test_derived_facts_materialize_all_declared_frozen_sources(tmp_path):
    import pytest
    from tagpilot_eval.p3_demo import facts_after
    target=tmp_path/'facts'
    facts_after(ROOT/'data/p0-v2',ROOT/'changes/p3-semantic-v1/changeset.json',target)
    manifest=verify_package(target)
    source=next(s['frozen_copy'] for s in manifest['sources'].values() if s.get('frozen_copy'))
    assert (target/source).is_file()
    (target/source).write_bytes(b'corrupted')
    with pytest.raises((ValueError,OSError,EOFError)):
        verify_package(target)
