import pytest
from runtime_support import runtime_case
from tagpilot_insight.compose import compose
from tagpilot_insight.contracts import InsightReport
from tagpilot_insight.guards import validate_report,GuardError
from tagpilot_insight.interaction import route,propose_edit
from tagpilot_insight.narration import guarded_narration

def report(skill='product_holding_gap'):
 p,b=runtime_case(skill);return InsightReport(run_id='interaction',cohort=p.cohort,results=[compose(p,b)])

def test_real_compose_uses_java_published_hash_not_yaml_draft_state():
 p,b=runtime_case('asset_structure_profile');p.cohort.synthetic=False;r=compose(p,b)
 assert r.status=='COMPLETE'
 real=InsightReport(run_id='java',cohort=p.cohort,results=[r])
 with pytest.raises(GuardError,match='UNPUBLISHED_SKILL'):validate_report(real)
 validate_report(real,published_hashes={r.skill_id:r.pack_hash})

def test_forged_statistical_proof_rejected_and_narration_cannot_replace_it():
 r=report();card=r.results[0].cards[0]
 assert card.diagnosis.basis=='STAT'
 candidates={r.results[0].skill_id:[c.model_dump(mode='json') for c in r.results[0].cards]}
 candidates[r.results[0].skill_id][0]['diagnosis']['statistical_evidence']['cohort_interval']=[0,1]
 restored,accepted=guarded_narration(r,candidates)
 assert not accepted and restored.results[0].facts==r.results[0].facts
 card.diagnosis.statistical_evidence.cohort_rate_id='missing'
 with pytest.raises(GuardError,match='UNKNOWN_FACT'):validate_report(r)

def test_weight_mutation_and_unknown_category_do_not_enter_execution():
 r=report();f=next(f for f in r.results[0].facts if f.id=='wealth_benchmark_rate');f.weights[next(iter(f.weights))]=.9
 with pytest.raises(GuardError,match='INVALID_WEIGHTS'):validate_report(r)
 out=route('看产品持仓',{'skills':['product_holding_gap'],'parameters':{'product_holding_gap':{'categories':['sql']}}})
 assert out.skills==['product_holding_gap'] and not out.parameters and out.needs_confirmation

def test_view_sort_preserves_every_fact_and_data_change_requires_confirmation():
 r=report();edited=propose_edit(r,'product_holding_gap','coverage','按升序排序')
 assert not edited['requires_confirmation'] and edited['report']['results'][0]['facts']==r.model_dump(mode='json')['results'][0]['facts']
 blocked=propose_edit(r,'product_holding_gap','coverage','只看高资产客户',{'classification':'view','operation':'sort','chart_id':'coverage','parameters':{'descending':True}})
 assert blocked['requires_confirmation'] and blocked['report'] is None and blocked['change']['classification']=='data'
 boundary=propose_edit(r,'product_holding_gap','coverage','改用同机构基准')
 assert boundary['requires_confirmation'] and boundary['change']['classification']=='definition'
 with pytest.raises(ValueError):propose_edit(r,'product_holding_gap','wealth_funnel','按降序排序')

def test_reason_combinations_aggregate_and_channel_fact_ids_are_unique():
 p,b=runtime_case('opportunity_priority');query=b.queries[1];row=query.rows[0]
 row.n=40;other=row.model_copy(deep=True);other.n=40;other.dimensions[1]='phone';query.rows.append(other)
 result=compose(p,b)
 assert result.status=='COMPLETE'
 facts={f.id:f for f in result.facts};assert len(facts)==len(result.facts)
 assert sum(p.value for p in next(c for c in result.charts if c.id=='reason_table').series[0].points)==180
