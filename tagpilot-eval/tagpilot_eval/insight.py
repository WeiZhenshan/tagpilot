"""固定小范围洞察验收，读取真实Java合成SQL输出，期望值独立于执行器。"""
from __future__ import annotations
import argparse,json
from pathlib import Path

# 240人客群/800人基准，由Java测试材料手算；不从被测函数生成期望。
EXPECTED={
 'asset_structure_profile':{'customers':240,'total_aum':120_000_000,'average_aum':500_000,'median_aum':500_000,'liquid_share':60,'liquid_gap':0},
 'product_holding_gap':{'customers':240,'wealth_holders':60,'wealth_valid':240,'wealth_rate':25,'wealth_benchmark_rate':70,'wealth_gap':45,'wealth_opportunity':120},
 'opportunity_priority':{'customers':240,'marketable':180,'high':80,'medium':60,'low':40},
}

def verify_sql_outputs(source:Path):
 from tagpilot_insight.planning import MetricPlan
 from tagpilot_insight.aggregates import AggregateBatch
 from tagpilot_insight.compose import compose
 from tagpilot_insight.contracts import InsightReport
 from tagpilot_insight.guards import validate_report
 cases=json.loads(source.read_text());results=[];cohort=None
 if {c['plan']['skill_id'] for c in cases}!=set(EXPECTED) or len(cases)!=3:raise ValueError('跨语言材料必须恰好覆盖三个黄金技能')
 for case in cases:
  plan=MetricPlan.model_validate(case['plan']);batch=AggregateBatch.model_validate(case['batch']);result=compose(plan,batch)
  if result.status!='COMPLETE':raise ValueError(f'{plan.skill_id} 未完整完成：{result.reasons}')
  if compose(plan,batch)!=result:raise ValueError('确定性复跑不一致')
  facts={f.id:f for f in result.facts}
  for key,expected in EXPECTED[plan.skill_id].items():
   if abs(facts[key].value-expected)>1e-8:raise ValueError(f'{plan.skill_id}.{key} 与独立手算不一致')
  if plan.skill_id=='product_holding_gap':
   if not all(c.diagnosis.basis=='STAT' and c.diagnosis.statistical_evidence for c in result.cards):raise ValueError('G2统计证明缺失')
   # 独立已知Wilson 60/240的95%区间；比较基准采用多格同时区间加权包络。
   proof=result.cards[0].diagnosis.statistical_evidence
   if not 19.94<proof.cohort_interval[0]<19.96:raise ValueError('Wilson下界错误')
   if not 30.8<proof.cohort_interval[1]<30.9 or not proof.cohort_interval[1]<proof.benchmark_interval[0]:raise ValueError('区间规则错误')
  if plan.skill_id=='opportunity_priority':
   if sum(facts[t].value for t in ('high','medium','low'))!=facts['marketable'].value:raise ValueError('分档不对账')
   reason_chart=next(c for c in result.charts if c.id=='reason_table')
   if sum(p.value for p in reason_chart.series[0].points)!=180:raise ValueError('前两项原因组合不对账')
  results.append(result);cohort=plan.cohort
 results.sort(key=lambda r:list(EXPECTED).index(r.skill_id))
 report=InsightReport(run_id='independent-sql-reference',cohort=cohort,results=results);validate_report(report)
 return report

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--java-aggregates',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 report=verify_sql_outputs(args.java_aggregates)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'scope':'H2合成SQL → Python确定性执行器；非银行/真实MySQL验收','passed':True,'llm':False,'report':report.model_dump(mode='json')},ensure_ascii=False,indent=2)+'\n')
 print('PASS: 3 skills, independent SQL numbers, deterministic replay, statistical evidence and charts')
if __name__=='__main__':main()
