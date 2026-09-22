from types import SimpleNamespace
from copy import deepcopy
from tag_semantic.retrieve.capabilities import search_capabilities
from tag_semantic.snapshot.canonicalize import content_hash


def test_capability_hash_preserves_argument_order():
    a={'kind':'capability','implementation':{'kind':'DIV','args':[{'tag_id':2},{'tag_id':1}]}}
    b=deepcopy(a);b['implementation']['args'].reverse()
    assert content_hash([a])!=content_hash([b])


def test_only_reviewed_visible_capabilities_and_no_physical_implementation():
    cap={'capability_id':'ratio','version':1,'name':'存款占比','definition':'存款占比','input_tag_ids':[1,2],'review_status':'REVIEWED','implementation':{'dataset_id':999}}
    catalog=SimpleNamespace(capabilities={'ratio':cap,'draft':{**cap,'capability_id':'draft','review_status':'DRAFT'}})
    assert not search_capabilities(catalog,'存款',{1})
    result=search_capabilities(catalog,'存款',{1,2})
    assert len(result)==1 and result[0]['capability_id']=='ratio' and 'implementation' not in result[0]
    assert not search_capabilities(catalog,'存款',{1},['ratio'])


def test_capability_survives_snapshot_build_and_authorized_http(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from tag_semantic.server import create_app
    from tag_semantic.tests.test_pipeline import _pilot_bundle
    from tag_semantic.index.builder import build_index
    from tag_semantic.snapshot.loader import load_catalog
    _,_,snapshot=_pilot_bundle(tmp_path)
    rows=deepcopy(snapshot['rows'])
    rows.append({'kind':'capability','capability_id':'customer.example','version':1,'capability_type':'BUSINESS_DEFINITION',
                 'name':'客户示例定义','aliases':['示例客户'],'definition':'合成业务定义','applicability':'单元测试',
                 'source_ref':'synthetic-fixture','review_status':'REVIEWED','input_tag_ids':[526],
                 'plan_template':{'clause_id':'test','tag_id':526,'operator':'=','values':['F']},
                 'implementation':{'private_value':'do-not-expose'}})
    meta=next(r for r in rows if r['kind']=='meta');meta.setdefault('counts',{})['capability']=1
    meta['content_hash']=content_hash(rows)
    path=tmp_path/'cap-snapshot.jsonl';path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
    catalog=load_catalog(path);assert catalog.capabilities['customer.example']['aliases']==['示例客户']
    build_index(catalog,tmp_path/'cap-build','cap-build')
    with TestClient(create_app(tmp_path,tmp_path,'secret')) as client:
        body={'requirement':'示例客户','library_id':107,'build_id':'cap-build','eligible_tag_ids':[526]}
        assert client.post('/capabilities',json=body).status_code==401
        headers={'Authorization':'Bearer secret'}
        result=client.post('/capabilities',json=body,headers=headers)
        assert result.status_code==200,result.text
        assert len(result.json()['capabilities'])==1
        assert 'do-not-expose' not in result.text and 'implementation' not in result.text
        body['eligible_tag_ids']=[]
        assert client.post('/capabilities',json=body,headers=headers).json()['capabilities']==[]
        body['library_id']=108
        assert client.post('/capabilities',json=body,headers=headers).status_code==409
