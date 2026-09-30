from tagpilot_insight.contracts import CohortSnapshot
from tagpilot_insight.planning import MetricPlan
from tagpilot_insight.registry import SkillRegistry
from tagpilot_insight.aggregates import AggregateBatch

def runtime_case(skill,parameters=None):
 reg=SkillRegistry();manifest=reg.get(skill)
 cohort=CohortSnapshot(audience_id='test-cohort',audience_name='固定合成取数客群',library_id=107,revision=1,plan_hash='a'*64,snapshot_id='test-snapshot',count=240,data_as_of='2026-09-28',reference_date='2026-09-29',binding_version='0.1.0',synthetic=True)
 plan=MetricPlan(skill_id=skill,skill_version=manifest.version,pack_hash=reg.hash(skill),snapshot_id=cohort.snapshot_id,binding_version=cohort.binding_version,cohort=cohort,parameters=reg.parameters(skill,parameters),status='READY',reasons=[],queries=manifest.queries)
 nodes=[]
 def add(qid,rows,category=None,status='AVAILABLE',reason=''):
  nodes.append(dict(query_id=qid,category=category,rows=[{'status':'AVAILABLE',**r} for r in rows],status=status,reason=reason,evidence_id='java-test-'+qid))
 add('customers',[dict(n=240,value=240)])
 if skill=='asset_structure_profile':
  for q,v in [('total_aum',120000000),('average_aum',500000),('median_aum',500000),('liquid',72000000),('fixed',24000000),('investment',24000000)]:add(q,[dict(n=240,value=v)])
  add('aum_bands',[dict(dimensions=['0'],n=120,value=120),dict(dimensions=['1'],n=120,value=120)])
  add('benchmark_bands',[dict(dimensions=['0'],n=200,value=200),dict(dimensions=['1'],n=400,value=400),dict(dimensions=['2'],n=200,value=200)])
  add('benchmark_assets',[dict(dimensions=['0'],n=400,value=200000000),dict(dimensions=['1'],n=400,value=200000000)])
  add('benchmark_count',[dict(n=800,value=800)])
  for q,v in [('liquid',156000000),('fixed',124000000),('investment',120000000)]:add('benchmark_'+q,[dict(n=800,value=v)])
  for c,v in [('liquid',180),('fixed',120),('investment',90)]:add('holders',[dict(n=240,holders=v,missing=0)],c)
  add('high_liquid',[dict(n=240,holders=120,missing=0)])
  add('missing',[dict(n=240,holders=0,missing=0)])
 elif skill=='product_holding_gap':
  for c in plan.parameters['categories']:
   add('coverage',[dict(dimensions=['0','3'],n=120,holders=30,missing=0),dict(dimensions=['1','3'],n=120,holders=30,missing=0)],c)
   add('benchmark_coverage',[dict(dimensions=['0','3'],n=400,holders=300,missing=0),dict(dimensions=['1','3'],n=400,holders=300,missing=0)],c)
   add('opportunity',[dict(n=240,holders=60,missing=0,unheld=180,suitable=160,opportunity=120)],c)
 elif skill=='opportunity_priority':
  names=['value_score','demand_event','product_gap','historical_response','channel_reach','disturbance_penalty']
  rows=[]
  for tier,n,values,reasons in [('high',80,[25,20,20,15,10,0],['value_score','demand_event']),('medium',60,[15,0,20,0,10,0],['product_gap','value_score']),('low',40,[5,0,20,0,10,0],['product_gap','channel_reach'])]:rows.append(dict(dimensions=[tier,'app'],n=n,reasons=reasons,contributions=dict(zip(names,values))))
  for reason in ['risk_mismatch','do_not_disturb','recent_contact']:rows.append(dict(dimensions=['excluded:'+reason,'none'],n=20,reasons=['unknown','unknown'],contributions=dict.fromkeys(names,0)))
  add('priority',rows)
 batch=AggregateBatch(skill_id=skill,pack_hash=plan.pack_hash,snapshot_id=cohort.snapshot_id,binding_version=cohort.binding_version,plan_hash=cohort.plan_hash,data_as_of=cohort.data_as_of,queries=nodes,benchmark_definition='同数据日按客群结构标准化的固定参考',benchmark_version='0.1.0',scope_hash='b'*64)
 return plan,batch
