import time
from fastapi.testclient import TestClient
from tagpilot_agent.api.app import create_app
from tagpilot_insight.registry import SkillRegistry
from tagpilot_insight.planning import MetricPlan
from tagpilot_insight.aggregates import AggregateBatch
from tagpilot_insight.contracts import CohortSnapshot


def test_insight_profile_uses_authenticated_encrypted_store_without_retrieval(tmp_path,monkeypatch):
 monkeypatch.setenv('TAG_AGENT_DB',str(tmp_path/'runs.sqlite'));monkeypatch.setenv('TAG_INSIGHT_LLM_ENABLED','false')
 app=create_app(token='controlled-test-secret',retriever_factory=lambda *_:(_ for _ in ()).throw(AssertionError('洞察不能进入圈选检索')))
 reg=SkillRegistry();skill='asset_structure_profile';manifest=reg.get(skill)
 cohort=CohortSnapshot(audience_id='test',audience_name='合成验证',library_id=107,revision=1,plan_hash='a'*64,snapshot_id='test',count=240,data_as_of='2026-09-28',reference_date='2026-09-29',binding_version='0.1.0',synthetic=True)
 plan=MetricPlan(skill_id=skill,skill_version=manifest.version,pack_hash=reg.hash(skill),snapshot_id='test',binding_version='0.1.0',cohort=cohort,parameters=reg.parameters(skill),status='BLOCKED',reasons=['指标待绑定'],queries=[])
 headers={'Authorization':'Bearer controlled-test-secret'}
 with TestClient(app) as client:
  assert client.get('/agent/insight/catalog').status_code==401
  assert len(client.get('/agent/insight/catalog',headers=headers).json()['skills'])==3
  body=dict(run_id='insight-test',thread_id='insight-thread',owner_id='test-owner',plans=[plan.model_dump(mode='json')],aggregates=[],narrate=False)
  assert client.post('/agent/insight/runs',headers=headers,json={**body,'sql':'select *'}).status_code==422
  assert client.post('/agent/insight/runs',headers=headers,json=body).status_code==200
  for _ in range(100):
   row=client.get('/agent/v2/runs/insight-test?owner_id=test-owner',headers=headers).json()
   if row['status']!='RUNNING':break
   time.sleep(.01)
  assert row['status']=='COMPLETED' and row['result']['results'][0]['status']=='BLOCKED'
  assert client.get('/agent/v2/runs/insight-test?owner_id=another',headers=headers).status_code==404
  assert client.post('/agent/insight/runs',headers=headers,json=body).status_code==200
  assert client.post('/agent/insight/route',headers=headers,json={'owner_id':'test-owner','utterance':'分析产品持仓'}).json()['skills']==['product_holding_gap']
  assert client.post('/agent/v2/runs/insight-test/resume',headers=headers,json={'owner_id':'test-owner'}).status_code==409
 assert '指标待绑定'.encode() not in (tmp_path/'runs.sqlite').read_bytes()


def test_insight_model_admission_never_calls_provider_when_shared_capacity_is_full(monkeypatch):
 import asyncio
 from collections import defaultdict
 from types import SimpleNamespace
 from tagpilot_agent.api.insight import admitted_once
 calls=[]
 async def provider(*args):calls.append(args);return {'skills':['asset_structure_profile']}
 monkeypatch.setattr('tagpilot_agent.runtime.insight_model.structured_once',provider)
 async def check():
  manager=SimpleNamespace(condition=asyncio.Condition(),active=2,limit=2,per_user=1,users=defaultdict(int))
  assert await admitted_once(manager,'owner','route',{}) is None
  assert manager.active==2 and manager.users['owner']==0 and calls==[]
 asyncio.run(check())


def test_insight_model_timeout_releases_shared_and_user_slots(monkeypatch):
 import asyncio
 from collections import defaultdict
 from types import SimpleNamespace
 from tagpilot_agent.api.insight import admitted_once
 calls=[]
 async def provider(*args):calls.append(args);raise TimeoutError('受控模拟超时')
 monkeypatch.setattr('tagpilot_agent.runtime.insight_model.structured_once',provider)
 async def check():
  manager=SimpleNamespace(condition=asyncio.Condition(),active=0,limit=2,per_user=1,users=defaultdict(int))
  assert await admitted_once(manager,'owner','chart_edit',{}) is None
  assert len(calls)==1 and manager.active==0 and manager.users['owner']==0
 asyncio.run(check())
