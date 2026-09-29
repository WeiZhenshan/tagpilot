import type {InsightReport} from "./types";
import {formatFact,isReportStale,statementText} from "./types";
export function InsightSummary({report,revision,hash,onExpand}:{report:InsightReport;revision:number;hash:string;onExpand:()=>void}){
 const stale=isReportStale(report,revision,hash),skill=report.results.find(r=>r.status!=="BLOCKED");
 const chart=skill?.charts.find(c=>c.kind==="bar"&&c.series.length===1);
 const points=chart?.series[0].points.filter(p=>p.value!==null).slice(0,3)||[];
 const maximum=Math.max(1,...points.map(p=>p.value!));
 return <div className="insight-summary"><p>{report.cohort.synthetic?"合成数据预览 · ":""}{stale?"洞察已过期，请重新运行":"洞察已保存"} · 数据日期 {report.cohort.data_as_of} · 方案 v{report.cohort.revision}</p>{skill?.cards[0]&&<p>{statementText(skill.cards[0].diagnosis,skill.facts)}</p>}
  {points.length>0&&<div className="insight-mini" aria-label={chart?.title}>{points.map(p=><div key={p.fact_id}><span>{p.category}</span><span className="insight-mini-track"><span style={{width:`${p.value!/maximum*100}%`}}/></span><span>{formatFact(skill!.facts.find(f=>f.id===p.fact_id)!)}</span></div>)}</div>}
  <button type="button" onClick={onExpand}>展开洞察报告</button></div>;
}
