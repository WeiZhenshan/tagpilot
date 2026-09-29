import { useEffect, useRef, useState } from "react";
import type { Plan, Thread } from "./agentTypes";
import { clauses, clauseSentence, expressionText, planDiff, treeSentence } from "./agentTypes";
import { PlanIcon } from "./ClauseSummary";

type Detail = "versions" | "requirement" | "technical";
const titles: Record<Detail, string> = { versions: "版本历史", requirement: "原始需求", technical: "技术详情" };

export function PlanMenu({ thread, plan, historical, dirty, onVersion }: {
  thread: Thread | null; plan?: Plan; historical: boolean; dirty: boolean; onVersion: (revision?: number) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [detail, setDetail] = useState<Detail>();
  const [copyNotice, setCopyNotice] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!menu) return;
    const outside = (e: PointerEvent) => { if (!root.current?.contains(e.target as Node)) setMenu(false); };
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") { setMenu(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [menu]);
  useEffect(() => {
    if (!detail) return;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); trigger.current?.focus(); };
  }, [detail]);
  useEffect(() => { setMenu(false); setDetail(undefined); setCopyNotice(""); }, [thread?.thread_id]);
  const versions = [...new Map([...(thread?.versions || []), ...(thread?.plan ? [thread.plan] : [])].map((p) => [p.revision, p])).values()]
    .sort((a, b) => (b.revision || 0) - (a.revision || 0));
  async function copy() {
    setMenu(false);
    try { if (plan) await navigator.clipboard.writeText(`圈选方案 v${plan.revision || "草稿"}\n${treeSentence(plan.tree)}`); setCopyNotice("已复制方案文字"); }
    catch { setCopyNotice("未能复制，请重试或从详情中选取文字。"); }
  }
  return <div className="plan-menu" ref={root}>
    <button ref={trigger} className="plan-icon-button" aria-label="方案更多操作" aria-expanded={menu} aria-controls="plan-more-actions" onClick={() => { setMenu(!menu); setCopyNotice(""); }}><PlanIcon kind="more" /></button>
    {menu ? <div id="plan-more-actions" className="plan-menu-options" aria-label="方案更多操作">
      {(["versions", "requirement", "technical"] as Detail[]).map((key) => <button key={key} disabled={!plan && key !== "requirement"} onClick={() => { setMenu(false); setDetail(key); }}>{titles[key]}</button>)}
      <button disabled={!plan} onClick={() => void copy()}>复制方案文字</button>
    </div> : null}
    {copyNotice ? <span className="plan-copy-notice" role="status">{copyNotice}</span> : null}
    {detail ? <dialog className="plan-detail-dialog" ref={dialog} aria-label={titles[detail]} onCancel={() => setDetail(undefined)}>
      <div className="panel-heading"><h2>{titles[detail]}</h2><button autoFocus className="plan-icon-button" aria-label="关闭方案详情" onClick={() => setDetail(undefined)}><PlanIcon kind="close" /></button></div>
      <div className="plan-detail-content">
        {detail === "versions" ? <>
          {dirty ? <p className="muted">请先保存或放弃修改，再切换版本。</p> : null}
          <div className="plan-version-list">{versions.map((p, i) => {
            const changes = planDiff(versions[i + 1], p);
            const summary = ["新增", "修改", "删除"].map((kind) => { const count = changes.filter((s) => s.startsWith(`${kind}：`)).length; return count ? `${kind} ${count} 项` : ""; }).filter(Boolean).join("、") || "条件组合或口径更新";
            return <button key={p.revision} disabled={dirty} aria-pressed={historical ? p.revision === plan?.revision : p.revision === thread?.revision}
              onClick={() => { onVersion(p.revision === thread?.revision ? undefined : p.revision); setDetail(undefined); }}>
              <strong>v{p.revision} {p.revision === thread?.revision ? "· 当前" : ""}</strong><span>{summary}</span>
            </button>;
          })}</div>
        </> : detail === "requirement" ? <>
          <p>{thread?.messages.find((m) => m.role === "user")?.text || "还没有业务需求。在对话里描述想寻找的客户。"}</p>
          {plan?.intent_plan?.requirements?.length ? <section className="plan-detail-section"><h3>本版业务要求</h3>{plan.intent_plan.requirements.map((r) => <p key={r.requirement_id}>{r.business_meaning}</p>)}</section> : null}
        </> : <>
          <dl className="technical-meta"><div><dt>方案版本</dt><dd>v{plan?.revision || "草稿"}{dirty ? " · 有未保存修改" : ""}</dd></div>
            <div><dt>快照 snapshot</dt><dd>{plan?.snapshot_id || "待核验"}</dd></div><div><dt>构建 build</dt><dd>{plan?.build_id || "待核验"}</dd></div>
            <div><dt>方案 hash</dt><dd>{plan?.hash || "待核验"}</dd></div></dl>
          {clauses(plan?.tree).map((c) => <section className="plan-detail-section" key={c.clause_id}><h3>{clauseSentence(c)}</h3>
            <p>依据 evidence：{c.evidence_id || "待核验"}</p>{c.definition ? <p>{c.definition}</p> : null}
            {c.expression ? <p>计算表达式：{expressionText(c.expression)} {c.operator} {c.compare_expression ? expressionText(c.compare_expression) : c.values?.join("、")}</p> : null}
            {c.caliber_struct ? <pre>{JSON.stringify(c.caliber_struct, null, 2)}</pre> : null}
          </section>)}
          {(plan?.diagnostics?.length ? plan.diagnostics : plan?.validation_errors || []).map((d, i) => <section className="plan-detail-section" key={i}><h3>{d.message}</h3>
            {d.code ? <p>诊断：{d.code}</p> : null}{d.expected !== undefined ? <pre>要求：{JSON.stringify(d.expected, null, 2)}</pre> : null}{d.actual !== undefined ? <pre>当前证据：{JSON.stringify(d.actual, null, 2)}</pre> : null}</section>)}
          {plan ? <section className="plan-detail-section"><h3>方案文字</h3><p className="plan-copy-text">{treeSentence(plan.tree)}</p></section> : null}
        </>}
      </div>
    </dialog> : null}
  </div>;
}
