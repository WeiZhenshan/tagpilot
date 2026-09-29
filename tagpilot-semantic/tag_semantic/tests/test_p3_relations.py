import copy
import json
import pytest
from tag_semantic.snapshot.schema import validate_catalog
from tag_semantic.snapshot.loader import Catalog
from tag_semantic.retrieve.service import visible_candidates, RetrieveService

def test_p3_fullwidth_alias_normalization_is_versioned():
    from tag_semantic.index.alias_index import AliasIndex
    index=AliasIndex();index.build([{'review_status':'REVIEWED','alias_type':'FORMAL',
        'alias_text':'当前时点AUM（本行）','alias_norm':'当前时点aum(本行)','target_type':'TAG','target_id':'735'}])
    assert index.lookup('当前时点AUM（本行）至少50万')==[]
    assert index.lookup('当前时点ＡＵＭ（本行）至少５０万','nfkc-v1')[0]['target_id']=='735'

def test_relation_candidates_are_eligible_and_not_exact_tag_alias():
    catalog=Catalog(meta={'schema_version':'v2'},concepts={1:{},2:{}},tags={
        10:{'tag_id':10,'concept_id':1,'name':'公开'},20:{'tag_id':20,'concept_id':1,'name':'隐藏'}},
        concept_tag_relations=[{'concept_id':2,'tag_id':10},{'concept_id':2,'tag_id':20}])
    hits=[{'doc':{'doc_type':'concept','concept_id':2},'rrf_score':1}]
    assert [t['tag_id'] for t in visible_candidates(hits,catalog,{10},20)]==[10]
    assert catalog.visible_concepts(set())==set()
    assert RetrieveService._unique_longest_alias_hits([{'doc':{'doc_type':'concept','tag_id':-1},'alias_norm':'业务入口'}])==[]

def test_snapshot_v2_relation_reference_and_v1_compatibility():
    from pathlib import Path
    path=Path(__file__).parents[2]/'out/full-20260919/snapshots/L107-20260919-002.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    validate_catalog(copy.deepcopy(rows))
    meta=next(r for r in rows if r['kind']=='meta');meta['schema_version']='v2'
    tag=next(r for r in rows if r['kind']=='tag')
    relation={'kind':'concept_tag_relation','library_id':107,'concept_id':tag['concept_id'],'tag_id':tag['tag_id'],
        'review_status':'REVIEWED','relation_note':'候选，不是等价','source_ref':'source-test','version':1}
    rows.append(relation);meta.setdefault('counts',{})['concept_tag_relation']=1
    validate_catalog(copy.deepcopy(rows))
    relation['tag_id']=-1
    with pytest.raises(ValueError,match='两端已发布'):validate_catalog(rows)

def test_specific_term_only_resolves_covered_occurrences():
    from tag_semantic.retrieve.facets import matched_terms,parse_facets
    terms=[{'term':'理财','policy':'ASK'},{'term':'持有理财','policy':'RESOLVE_BY_FIELD'},
        {'term':'理财风评','policy':'RESOLVE_BY_FIELD'}]
    assert parse_facets('没持有理财且理财风评C3',terms,'specific-v1')['unresolved_fuzzy_terms']==[]
    assert parse_facets('没持有理财，也想找理财比较多的',terms,'specific-v1')['unresolved_fuzzy_terms']==['理财']
    assert parse_facets('理财比较多',terms,'specific-v1')['unresolved_fuzzy_terms']==['理财']
    assert parse_facets('持有理财',terms)['unresolved_fuzzy_terms']==['理财']

def test_shared_models_are_keyed_by_verified_content_hash(monkeypatch,tmp_path):
    import sys,types
    from tag_semantic.index import embedder as module
    calls=[]
    class Model:
        def __init__(self,path,**kwargs):calls.append(path)
    monkeypatch.setitem(sys.modules,'FlagEmbedding',types.SimpleNamespace(BGEM3FlagModel=Model,FlagReranker=Model))
    module._shared_embedding.cache_clear();module._shared_reranker.cache_clear()

    (tmp_path/'weights').write_text('version1')
    a=module.BGEEmbedder(str(tmp_path));b=module.BGEEmbedder(str(tmp_path))
    assert a._model is b._model and len(calls)==1
    (tmp_path/'weights').write_text('version2')
    c=module.BGEEmbedder(str(tmp_path));assert c._model is not a._model and len(calls)==2
    module._shared_embedding.cache_clear();module._shared_reranker.cache_clear()

def test_selection_context_preserves_candidate_rank():
    from tag_semantic.retrieve.service import selection_context
    catalog=Catalog(meta={},concepts={},tags={1:{'tag_id':1,'name':'低排名'},9:{'tag_id':9,'name':'首选'}})
    assert [t['tag_id'] for t in selection_context([{'tag_id':9},{'tag_id':1},{'tag_id':9}],catalog)['tags']]==[9,1]
