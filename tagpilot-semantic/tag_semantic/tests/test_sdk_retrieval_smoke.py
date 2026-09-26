"""新增渐进检索接口的有限冒烟，复用开发金标目录。"""
from fastapi.testclient import TestClient
from tag_semantic.server import create_app
from tag_semantic.tests.test_pipeline import _pilot_bundle

def test_lookup_batch_evidence_flow(tmp_path):
    _pilot_bundle(tmp_path)
    with TestClient(create_app(tmp_path,tmp_path,'secret')) as client:
        req={'requirement':'女性','library_id':107,'build_id':'b1','eligible_tag_ids':[526]}
        headers={'authorization':'Bearer secret'}
        quick=client.post('/lookup',json=req,headers=headers)
        assert quick.status_code==200,quick.text
        quick_data=quick.json()
        context_tags=quick_data['selection_context']['tags']
        assert {t['tag_id'] for t in context_tags}=={526}
        assert all({'dir_path','concept_name','update_cycle','confusable_notes'}<=set(t) for t in context_tags)
        terms=quick_data['terms']
        assert terms and terms[0]['term']=='女性'
        assert terms[0]['type']=='FUZZY_CATEGORY' and terms[0]['options']==['GENDER=F']
        assert terms[0]['policy']=='RESOLVE'
        assert terms[0]['applicable_semantic_types']==['ENUM_NOMINAL']
        assert all(set(t)=={'term','type','options','policy','applicable_semantic_types'} for t in terms)
        batch=client.post('/retrieve_batch',json={**req,'queries':['女性','男性'],'mode':'fast'},headers=headers)
        assert batch.status_code==200,batch.text
        assert len(batch.json()['results'])==2
        assert all(set(t['tag_id'] for t in r['selection_context']['tags'])<={526} for r in batch.json()['results'])
        evidence=client.post('/evidence',json={**req,'tag_ids':[526],'value_query':'女','max_values':1},headers=headers)
        assert evidence.status_code==200,evidence.text
        evidence_data=evidence.json()
        assert len(evidence_data['code_values'])<=1
        assert evidence_data['terms'][0]['term']=='女性' and evidence_data['terms'][0]['options']==['GENDER=F']
        assert client.post('/lookup',json={**req,'library_id':108},headers=headers).status_code==409
        assert client.post('/evidence',json={**req,'eligible_tag_ids':[],'tag_ids':[526]},headers=headers).status_code==403
