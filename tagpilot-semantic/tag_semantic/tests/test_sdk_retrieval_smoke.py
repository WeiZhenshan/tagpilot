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
        assert {t['tag_id'] for t in quick.json()['selection_context']['tags']}=={526}
        batch=client.post('/retrieve_batch',json={**req,'queries':['女性','男性'],'mode':'fast'},headers=headers)
        assert batch.status_code==200,batch.text
        assert len(batch.json()['results'])==2
        assert all(set(t['tag_id'] for t in r['selection_context']['tags'])<={526} for r in batch.json()['results'])
        evidence=client.post('/evidence',json={**req,'tag_ids':[526],'value_query':'女','max_values':1},headers=headers)
        assert evidence.status_code==200,evidence.text
        assert len(evidence.json()['code_values'])<=1
        assert client.post('/lookup',json={**req,'library_id':108},headers=headers).status_code==409
        assert client.post('/evidence',json={**req,'eligible_tag_ids':[],'tag_ids':[526]},headers=headers).status_code==403
