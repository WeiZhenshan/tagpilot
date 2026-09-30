import { useState } from "react";
import type { ChartChange } from "./insightApi";
import type { InsightReport } from "./types";
import { isReportStale, statementText } from "./types";
import { InsightChart } from "./InsightChart";
import "./insight.css";

const names: Record<string, string> = { asset_structure_profile: "资产结构", product_holding_gap: "产品缺口", opportunity_priority: "机会排序" };
const basis = { RULE: "规则", STAT: "统计参考", HYPOTHESIS: "假设" };
const skillName = (skill: InsightReport["results"][number]) => skill.display_name || names[skill.skill_id] || skill.skill_id;

export function InsightReportPanel({ report, currentRevision, currentPlanHash, onEdit, onReviewChange, onFeedback, onConfirmRerun }: { report: InsightReport; currentRevision: number; currentPlanHash: string; onConfirmRerun?: (skill:string,parameters:Record<string,unknown>) => Promise<void>; onEdit?: (skill: string, chart: string, utterance: string) => Promise<ChartChange>; onReviewChange?: (utterance: string) => void; onFeedback?: (rating:number,category:string,comment:string) => Promise<unknown> }) {
  const [selected, setSelected] = useState(report.results[0]?.skill_id);
  const [editText,setEditText] = useState("");
  const [chartId,setChartId] = useState("");
  const [proposal,setProposal] = useState<ChartChange>();
  const [working,setWorking] = useState(false);
  const [rating,setRating] = useState(4);
  const [feedback,setFeedback] = useState("");
  const [notice, setNotice] = useState("");
  const skill = report.results.find((r) => r.skill_id === selected) || report.results[0];
  const stale = isReportStale(report, currentRevision, currentPlanHash);
  const cohort = report.cohort;
  const context = `${cohort.synthetic ? "合成数据 · " : ""}${cohort.data_as_of} · Skill ${skill.skill_version} · 方案 v${cohort.revision}`;
  const kpis = skill.charts.filter((c) => c.kind === "kpi");
  const charts = skill.charts.filter((c) => c.kind !== "kpi");
  async function copySummary() {
    try {
      const summary = [cohort.synthetic ? "合成数据预览，非业务洞察结果" : cohort.audience_name, context,
        ...skill.cards.flatMap((card) => [card.title, statementText(card.facts, skill.facts), statementText(card.comparison, skill.facts),
          statementText(card.diagnosis, skill.facts), statementText(card.action, skill.facts), card.boundary.text])].join("\n");
      await navigator.clipboard.writeText(summary); setNotice("已复制摘要，包含数据日期、版本和适用边界。");
    } catch { setNotice("复制失败，请使用浏览器选择报告文字复制。"); }
  }
  return <div className="insight-report">
    <header className="insight-report-header"><h1>{cohort.audience_name}</h1><p>{cohort.count === null ? "人数未统计" : `${cohort.count.toLocaleString("zh-CN")} 人`} · 数据日期 {cohort.data_as_of || "未接入"} · 方案 v{cohort.revision}</p>{cohort.declared_context && <p>已声明背景：{cohort.declared_context}</p>}</header>
    {report.level && <p className="insight-boundary" role="status">{report.level === "L2" ? "部分洞察可用，请查看各段原因与边界。" : report.level === "L4" ? "本次洞察未出数，请补齐条件后重新运行。" : "叙述使用确定性模板，数字和图表保持原结果。"}</p>}
    {cohort.synthetic && <p className="insight-boundary" role="note">合成聚合数据预览，仅验证事实、卡片与图表链路。此预览使用固定聚合参考，实际取数结果须通过绑定、统计与发布门禁。</p>}
    {stale && <p className="insight-boundary" role="status">已过期，需重新运行。当前方案已变化；导出与复制已暂停。</p>}
    <nav className="insight-sections" aria-label="洞察报告分段">{report.results.map((r) => <button type="button" key={r.skill_id} aria-pressed={r.skill_id === skill.skill_id} onClick={() => { setSelected(r.skill_id); setNotice(""); setChartId(""); setProposal(undefined); setEditText(""); }}>{skillName(r)}</button>)}</nav>
    <section className="insight-skill-section" aria-label={skillName(skill)}>
      <header className="insight-skill-header"><h2>{skillName(skill)}</h2><span>Skill {skill.skill_version}{skill.level ? ` · ${skill.level}` : ""}</span></header>
      {skill.reasons.map((reason) => <p key={reason} className="insight-boundary">{reason}</p>)}
      {skill.status === "BLOCKED" ? <p className="insight-boundary">本段已阻断，不展示数值；请补齐上述条件后重新运行。</p> : <>
        {kpis.length > 0 && <div className="insight-kpis">{kpis.map((spec) => <InsightChart key={spec.id} spec={spec} facts={skill.facts} context={context} stale={stale} />)}</div>}
        {skill.cards.map((card) => <article className="insight-findings" key={card.id} aria-label={card.title}>
          <h3>{card.title}</h3><dl>
            <dt>事实</dt><dd>{statementText(card.facts, skill.facts)}</dd>
            <dt>对比</dt><dd>{statementText(card.comparison, skill.facts)}</dd>
            <dt>诊断 · {basis[card.diagnosis.basis]}</dt><dd>{statementText(card.diagnosis, skill.facts)}</dd>
            <dt>行动</dt><dd>{statementText(card.action, skill.facts)}</dd>
            <dt>证据与边界</dt><dd>{card.boundary.text}</dd>
          </dl><details><summary>查看证据与口径</summary><p>{context} · 样本 {cohort.count === null ? "未统计" : cohort.count} 人</p><ul>{card.boundary.metric_definitions.map((definition) => <li key={definition}>{definition}</li>)}</ul><p className="insight-hash">包 hash：{skill.pack_hash}<br />快照：{cohort.snapshot_id}<br />绑定版本：{cohort.binding_version}</p></details>
        </article>)}
        <div className="insight-dashboard">{charts.map((spec) => <InsightChart key={spec.id} spec={spec} facts={skill.facts} context={context} stale={stale} />)}</div>
        {(skill.followups || []).length > 0 && <div className="insight-followups"><h3>建议下一步</h3><ul>{skill.followups!.map((item) => <li key={item}>{item}</li>)}</ul></div>}
        {onEdit && <form className="insight-feedback" onSubmit={async (e) => { e.preventDefault(); setWorking(true); try { const result = await onEdit(skill.skill_id,chartId || charts[0]?.id,editText); setProposal(result); setNotice(result.message); } catch (error) { setNotice(error instanceof Error ? error.message : "修改失败，请重试"); } finally { setWorking(false); } }}><label>修改哪张图<select aria-label="修改图表" value={chartId || charts[0]?.id || ""} onChange={(e) => setChartId(e.target.value)}>{charts.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><label>改图需求<textarea aria-label="改图需求" maxLength={2000} value={editText} onChange={(e) => setEditText(e.target.value)} placeholder="例如：按降序排序；显示为数据表" /></label><button type="submit" disabled={stale || working || !editText.trim() || !charts.length}>核验并应用</button>{proposal && <p>{proposal.change.classification === "view" ? "视图变化" : proposal.change.classification === "data" ? "数据变化" : "口径变化"} · {proposal.message}</p>}{proposal?.requires_confirmation && <div className="ask-card"><p>当前报告保留。请先确认并核验新的筛选或基准，再重新统计和运行。</p>{proposal.change.parameters && Object.keys(proposal.change.parameters).length > 0 && onConfirmRerun ? <button type="button" disabled={stale || working} onClick={async () => { setWorking(true); try { await onConfirmRerun(skill.skill_id,proposal.change.parameters!); setProposal(undefined); setNotice("已按确认参数重新取数和核验报告。"); } catch (error) { setNotice(error instanceof Error ? error.message : "重跑失败，当前报告保留。"); } finally { setWorking(false); } }}>确认新参数并重跑</button> : <button type="button" disabled={stale} onClick={() => onReviewChange?.(editText)}>回到方案核验</button>}<button type="button" onClick={() => setProposal(undefined)}>保留当前报告</button></div>}</form>}
        {onFeedback && <form className="insight-feedback" onSubmit={async (e) => { e.preventDefault(); setWorking(true); try { await onFeedback(rating,"USEFULNESS",feedback); setNotice("反馈已保存，进入后续复核；当前规则和版本保持不变。"); } catch { setNotice("反馈保存失败，请重试。"); } finally { setWorking(false); } }}><label>本次洞察是否有用<select aria-label="洞察评分" value={rating} onChange={(e) => setRating(Number(e.target.value))}>{[1,2,3,4,5].map((n) => <option key={n} value={n}>{n} 分</option>)}</select></label><textarea aria-label="洞察反馈" maxLength={500} value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="可补充口径、图表或行动建议的问题" /><button type="submit" disabled={stale || working}>保存反馈</button></form>}
        <footer className="insight-report-footer"><button type="button" disabled={stale} onClick={() => void copySummary()}>复制本段摘要</button><p role="status">{notice}</p></footer>
      </>}
    </section>
  </div>;
}
