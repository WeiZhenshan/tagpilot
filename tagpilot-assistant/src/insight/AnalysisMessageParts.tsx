import { lazy, Suspense, useCallback, useEffect, useId, useRef, useState } from "react";
import type { AnalysisArtifact, AnalysisPart, ArtifactReference } from "./analysisTypes";
import { analysisLimitation, artifactFor } from "./analysisTypes";
import { formatFact } from "./types";
import "./insight.css";
import "./analysis-message.css";

const InsightChart = lazy(() => import("./InsightChart").then((m) => ({ default: m.InsightChart })));
type Props = {
  parts: AnalysisPart[];
  artifacts?: Record<string, AnalysisArtifact>;
  disabled?: boolean;
  revision: number;
  onContinue: (target: ArtifactReference, text?: string) => void;
  onAnswer: (text: string) => void;
  onAdjust?: () => void;
};

function ChartBlock({ artifact, disabled, revision, onContinue, limited }: Omit<Props, "parts" | "artifacts" | "onAnswer"> & { artifact: AnalysisArtifact; limited: boolean }) {
  const [detail, setDetail] = useState<"chart" | "source" | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const selectionRef = useRef<HTMLDivElement>(null);
  const detailTitle = useId();
  const trigger = useRef<HTMLElement | null>(null);
  const selectCategory = useCallback((category: string) => setSelection(category), []);
  useEffect(() => {
    if (!selection) return;
    // 图表较高时确认条可能在视口外，点选后将它带入视野。
    selectionRef.current?.scrollIntoView({ block: "nearest", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [selection]);
  const target: ArtifactReference = { target_artifact_id: artifact.id, target_artifact_version: artifact.version, title: artifact.spec.title };
  const stale = artifact.base_revision !== undefined && artifact.base_revision !== revision;
  const context = artifact.context || "当前分析客群 · 数据日期未知";
  useEffect(() => {
    if (!detail) return;
    trigger.current = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); trigger.current?.focus(); };
  }, [detail]);
  const metricOnly = limited && artifact.spec.kind === "kpi";
  const actions = <div className="analysis-chart-toolbar" aria-label={metricOnly ? "指标操作" : "图表操作"}>
    {!metricOnly ? <button type="button" disabled={disabled || stale} onClick={() => onContinue(target)}>继续分析此图</button> : null}
    <button type="button" onClick={() => setDetail("source")}>查看来源</button>
    {!metricOnly && artifact.spec.kind !== "kpi" ? <button type="button" onClick={() => setDetail("chart")}>放大查看</button> : null}
  </div>;
  return <div className="analysis-chart-block" data-artifact-id={artifact.id} data-artifact-version={artifact.version}>
    <Suspense fallback={<p className="analysis-status" role="status">正在载入图表…</p>}>
      <InsightChart spec={artifact.spec} facts={artifact.facts} context={context} stale={stale} actions={actions} showExport={!metricOnly} onSelectCategory={selectCategory} />
    </Suspense>
    {stale && <p className="analysis-scope-note">这是历史方案下的图表；当前客群已变化，请重新分析。</p>}
    {selection && <div className="analysis-selection" role="status" ref={selectionRef}>
      <span>已选择：{selection}</span>
      <button type="button" disabled={disabled || stale} onClick={() => onContinue(target, `继续分析这张图中「${selection}」的客户，保留原分析范围`)}>按此分类继续分析</button>
      <button type="button" onClick={() => setSelection(null)}>取消选择</button>
    </div>}
    {detail && <dialog ref={dialog} className="analysis-detail-dialog" aria-labelledby={detailTitle} onCancel={() => setDetail(null)}>
      <header><h2 id={detailTitle}>{detail === "source" ? metricOnly ? "指标来源" : "图表来源" : artifact.spec.title}</h2><button type="button" onClick={() => setDetail(null)}>关闭</button></header>
      {detail === "chart" ? <Suspense fallback={<p role="status">正在载入图表…</p>}><InsightChart spec={artifact.spec} facts={artifact.facts} context={context} stale={stale} /></Suspense> : <>
        <dl className="analysis-source"><dt>分析范围</dt><dd>{context}</dd><dt>业务数据日期</dt><dd>{artifact.bundle?.data_as_of || "未知"}</dd><dt>查询时间</dt><dd>{artifact.bundle?.queried_at ? new Date(artifact.bundle.queried_at).toLocaleString("zh-CN") : "未记录"}</dd><dt>图表版本</dt><dd>{artifact.version}</dd><dt>证据快照</dt><dd>{artifact.snapshot_id || "历史报告未登记"}</dd></dl>
        {artifact.bundle?.quality?.note && <p className="analysis-scope-note">{artifact.bundle.quality.note}</p>}
        <div className="insight-table-scroll"><table><caption>本图引用的聚合事实</caption><thead><tr><th scope="col">指标</th><th scope="col">数值</th><th scope="col">来源</th></tr></thead><tbody>{artifact.facts.filter((f) => artifact.spec.series.some((s) => s.fact_ids.includes(f.id))).map((f) => <tr key={f.id}><th scope="row">{f.label}</th><td>{formatFact(f)}</td><td>{f.evidence.join("；")}</td></tr>)}</tbody></table></div>
      </>}
    </dialog>}
  </div>;
}

export function AnalysisMessageParts({ parts, artifacts, disabled, revision, onContinue, onAnswer, onAdjust }: Props) {
  const limitation = analysisLimitation(parts);
  const legacyLimitation = limitation?.status === "COMPLETE";
  const narrative = parts.filter((part) => (part.type === "status" || part.type === "text")
    && (legacyLimitation || analysisLimitation([part])));
  const sampleLimited = limitation && "text" in limitation && /小样本|互补小格|抑制/.test(limitation.text);
  return <div className="analysis-message-parts">
    {limitation ? <section className="analysis-limitation" aria-label="分析受限">
      <strong>{sampleLimited ? "部分分组样本不足，无法展示完整分布" : "部分分析结果暂不可用"}</strong>
      <details><summary>查看原因与可用范围</summary>
        {narrative.map((part) => "text" in part && <p key={part.id}>{part.text}</p>)}
      </details>
      {onAdjust ? <button type="button" className="text-button" disabled={disabled} onClick={onAdjust}>调整分析问题</button> : null}
    </section> : null}
    {parts.map((part) => {
    if (part.type === "text" || part.type === "status") return narrative.includes(part) ? null : <p key={part.id} className={part.type === "status" ? "analysis-status" : "analysis-answer"}>{part.text}</p>;
    if (part.type === "clarification") return <section key={part.id} className="analysis-clarification" aria-label="补充分析信息"><p>{part.prompt}</p><div>{part.options.map((option) => <button key={option} type="button" disabled={disabled} onClick={() => onAnswer(option)}>{option}</button>)}</div><p className="analysis-scope-note">也可以在输入框补充说明。</p></section>;
    if (part.type === "chart" || part.type === "table") {
      if (part.status === "BLOCKED") return null;
      const artifact = artifactFor(artifacts, part.artifact_id, part.artifact_version);
      return artifact ? <ChartBlock key={part.id} artifact={artifact} disabled={disabled} revision={revision} onContinue={onContinue} limited={!!limitation} /> : <p key={part.id} role="alert">图表暂不可用，请刷新会话后重试。</p>;
    }
    return null;
  })}</div>;
}
