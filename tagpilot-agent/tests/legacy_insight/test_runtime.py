import pytest
from tagpilot_insight.compose import compose
from tagpilot_insight.statistics import standardize,wilson
from tagpilot_insight.aggregates import AggregateRow
from runtime_support import runtime_case

@pytest.mark.parametrize('skill',['asset_structure_profile','product_holding_gap','opportunity_priority'])
def test_runtime_computation_does_not_load_report_fixture(skill,monkeypatch):
 monkeypatch.setattr('tagpilot_insight.fixtures.synthetic_golden_report',lambda:(_ for _ in ()).throw(AssertionError('运行不能用样例报告替代计算')))
 plan,batch=runtime_case(skill);result=compose(plan,batch)
 assert result.status=='COMPLETE',result.reasons
 facts={f.id:f.value for f in result.facts}
 if skill=='asset_structure_profile':assert facts['total_aum']==120000000 and facts['median_aum']==500000 and facts['liquid_gap']==21
 if skill=='product_holding_gap':assert facts['wealth_rate']==25 and facts['wealth_benchmark_rate']==75 and facts['wealth_gap']==50 and facts['wealth_opportunity']==120 and result.cards[0].diagnosis.basis=='STAT'
 if skill=='opportunity_priority':assert [facts[k] for k in ['marketable','high','medium','low']]==[180,80,60,40]

@pytest.mark.parametrize('field',['pack_hash','snapshot_id','binding_version','plan_hash','data_as_of'])
def test_envelope_mismatch_is_rejected(field):
 plan,batch=runtime_case('asset_structure_profile');data=batch.model_dump();data[field]={'pack_hash':'c'*64,'snapshot_id':'another','binding_version':'0.2.0','plan_hash':'c'*64,'data_as_of':'2026-09-27'}[field]
 with pytest.raises(ValueError,match='版本'):compose(plan,type(batch).model_validate(data))

def test_missing_suitability_degrades_without_opportunity():
 plan,batch=runtime_case('product_holding_gap',{'categories':['wealth']})
 node=next(q for q in batch.queries if q.query_id=='opportunity');node.rows=[];node.status='MISSING';node.reason='适当性映射未复核'
 result=compose(plan,batch);assert result.status=='PARTIAL' and result.level=='L2',result.reasons
 assert not any(f.role=='POST_EXCLUSION' for f in result.facts)
 assert result.cards[0].action.population_fact_id is None

def test_suppressed_cells_never_impute_zero():
 plan,batch=runtime_case('product_holding_gap',{'categories':['wealth']});q=next(q for q in batch.queries if q.query_id=='benchmark_coverage');q.rows=[];q.status='SUPPRESSED'
 result=compose(plan,batch);assert result.status=='BLOCKED' and not result.facts

def test_standardization_uses_target_structure_not_baseline_mix():
 c=[AggregateRow(dimensions=['0','1'],n=180,holders=90,missing=0),AggregateRow(dimensions=['1','1'],n=60,holders=30,missing=0)]
 b=[AggregateRow(dimensions=['0','1'],n=100,holders=80,missing=0),AggregateRow(dimensions=['1','1'],n=900,holders=180,missing=0)]
 assert standardize(c,b)['rate']==65 # 75%×80% + 25%×20%，基准总体26%不能替代

def test_sparse_two_dimensional_falls_back_then_stops():
 c=[AggregateRow(dimensions=['0',r],n=20,holders=10,missing=0) for r in ['1','2']];b=[AggregateRow(dimensions=['0',r],n=100,holders=50,missing=0) for r in ['1','2']]
 assert standardize(c,b)['mode']=='AUM'
 with pytest.raises(ValueError,match='样本'):standardize(c[:1],b[:1])

def test_interval_overlap_cannot_claim_statistical_gap():
 plan,batch=runtime_case('product_holding_gap',{'categories':['wealth']})
 for q in batch.queries:
  if q.query_id=='benchmark_coverage':
   for row in q.rows:row.holders=110
 result=compose(plan,batch);assert result.status=='PARTIAL' and result.cards[0].diagnosis.basis=='RULE',result.reasons
 assert not any(f.role=='POST_EXCLUSION' for f in result.facts)

def test_java_shared_plans_match_current_pack_and_queries():
 from pathlib import Path
 import json
 from tagpilot_insight.registry import SkillRegistry
 reg=SkillRegistry();rows=json.loads((Path(__file__).resolve().parents[3]/'ruoyi-taglibrary/src/test/resources/insight/metric-plans.json').read_text())
 assert {r['skill_id'] for r in rows}==set(reg.manifests)
 for row in rows:
  assert row['pack_hash']==reg.hash(row['skill_id'])
  assert row['queries']==[q.model_dump(mode='json') for q in reg.get(row['skill_id']).queries]
