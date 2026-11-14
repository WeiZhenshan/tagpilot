import { useEffect, useRef, useState, type ReactNode } from "react";
import { clauses, type Clause, type Plan, type RunEvent, type Thread } from "./agentTypes";
import { ClauseDetails } from "./ClauseSummary";
import { actionLabel, buildRunView, groupLabel, type Action, type TimelineItem, type TodoItem, type TodoStatus, type ResultProgress } from "./runTimeline";
import { useEventPacer, useNarrationText, useReducedMotion } from "./useEventPacer";
import { Presence } from "./Presence";
import { ActionIcon } from "./ActionIcon";

const statusLabels: Record<TodoStatus, string> = { pending: "尚未开始", active: "进行中", done: "已完成", blocked: "待处理" };
export function StatusIcon({ status }: { status: TodoStatus | Action["status"] }) {
  const kind = status === "running" ? "active" : status === "error" || status === "stopped" ? "blocked" : status;
  return <span className={`run-marker marker-${kind}`} aria-hidden="true">
    {kind === "done" ? <svg viewBox="0 0 16 16" fill="none"><path d="m3 8 3 3 7-7" /></svg> : kind === "blocked" ? <svg viewBox="0 0 16 16" fill="none"><path d="M8 3v6M8 12v.1" /></svg> : null}
  </span>;
}
function Todo({ item }: { item: TodoItem }) {
  return <li data-status={item.status}>
    <div className="run-todo-row"><StatusIcon status={item.status} /><span>{item.label}</span><small>{statusLabels[item.status]}</small></div>
    {item.result ? <p className="run-todo-result">{item.result}</p> : null}
    {item.children?.length ? <ol>{item.children.map((child) => <Todo key={child.id} item={child} />)}</ol> : null}
  </li>;
}
function ActionBody({ action, matched }: { action: Action; matched: Map<string, Clause> }) {
  return <div className="run-action-body">
    {action.summary ? <p>{action.summary}</p> : action.status === "running" ? <p>正在核对，请稍候…</p> : null}
    {action.names.length ? <ul className="run-tag-cards" aria-label="相关标签">{action.names.map((name, index) => {
      const clause = matched.get(name);
      return <li key={index}>{clause ? <details><summary>{name}<small>查看口径</small></summary><ClauseDetails clause={clause} /></details> : name}</li>;
    })}</ul> : null}
    {action.ms !== undefined ? <small>{(action.ms / 1000).toFixed(1)} 秒</small> : null}
  </div>;
}
function Narration({ text, animate }: { text: string; animate: boolean }) {
  const narration = useNarrationText(text, animate);
  return <span className="run-narration-text">{narration.text}{narration.streaming ? <span className="run-caret" aria-hidden="true" /> : null}</span>;
}
function TimelineRow({ item, expanded, toggle, animate, matched, onReveal }: { item: TimelineItem; expanded: boolean; toggle: () => void; animate: boolean; matched: Map<string, Clause>; onReveal?: (ids: string[]) => void }) {
  const action = item.kind === "action" || item.kind === "group";
  return <li className={`run-entry run-entry-${item.kind}`}>
    {action ? <>
      <button type="button" className="run-entry-toggle" aria-expanded={expanded} onClick={toggle}>
        <StatusIcon status={item.status} /><span className={item.status === "running" ? "run-working" : ""}>{item.kind === "action" ? actionLabel(item) : groupLabel(item)}</span>
        {!expanded ? <small>{item.kind === "action" ? item.summary : item.actions.at(-1)?.summary}</small> : null}
        <Chevron open={expanded} />
      </button>
      {expanded ? item.kind === "action" ? <ActionBody action={item} matched={matched} /> : <ol className="run-group-actions">{item.actions.map((a) => <li key={a.id}><div className="run-group-heading"><StatusIcon status={a.status} /><span>{actionLabel(a)}</span></div><ActionBody action={a} matched={matched} /></li>)}</ol> : null}
    </> : item.kind === "narration" ? <>
      <button type="button" className="run-entry-toggle narration-toggle" aria-expanded={expanded} onClick={toggle}>
        <span className="run-node" aria-hidden="true" /><Narration text={expanded ? item.text : `已说明：${item.text}`} animate={expanded && animate} /><Chevron open={expanded} />
      </button>
    </> : item.kind === "change" ? <div className="run-change">
      <span className="run-node" aria-hidden="true" /><button type="button" onClick={() => onReveal?.(item.clauseIds)} disabled={!onReveal}>方案变更 · {item.diff.length} 项</button>
      <button type="button" className="text-button" aria-expanded={expanded} onClick={toggle}>{expanded ? "收起" : "查看"}</button>
      {expanded ? <ul>{item.diff.map((d, i) => <li key={i}>{d}</li>)}</ul> : null}
    </div> : <p className="run-state-line"><StatusIcon status="blocked" />{item.text}</p>}
  </li>;
}
function Chevron({ open }: { open: boolean }) {
  return <ActionIcon kind="chevron" className="run-chevron" open={open} />;
}

export function RunTimeline({ events, runId, running, plan, questions, status, label, children, followUp, completionLabel, results, onReveal, skillMode = false, continued = false }: {
  events: RunEvent[]; runId: string; running: boolean; plan?: Plan; questions?: Thread["questions"]; status?: string;
  skillMode?: boolean; continued?: boolean; label?: string; children?: ReactNode; followUp?: ReactNode; completionLabel?: string; results?: ResultProgress; onReveal?: (ids: string[]) => void;
}) {
  const reduced = useReducedMotion();
  const paced = useEventPacer(events, runId, running, reduced);
  // 当前快照中的 live_plan 可能来自尚在队列中的事件，不能提前显示其进度。
  const initialPlan = useRef(plan).current;
  const [now, setNow] = useState(Date.now() / 1000);
  const effectiveStatus = status || [...events].reverse().map((e) => ({ "run.cancelled": "CANCELLED", "run.failed": "FAILED", "run.interrupted": "INTERRUPTED", "run.waiting": "WAITING", "run.degraded": "COMPLETED", "run.completed": "COMPLETED" }[e.type])).find(Boolean);
  const waiting = effectiveStatus === "WAITING" && !continued;
  const [open, setOpen] = useState(running || waiting);
  const [finishing, setFinishing] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const autoOpened = useRef(running || waiting);
  const lastRun = useRef(runId);
  useEffect(() => {
    if (lastRun.current !== runId) {
      lastRun.current = runId;
      autoOpened.current = running || waiting;
      setOpen(running || waiting);
      setOverrides({});
      setFinishing(false);
      return;
    }
    if (running || waiting) {
      autoOpened.current = true;
      setOpen(true);
      setOverrides({});
      setFinishing(false);
      return;
    }
    // 用户手动展开的已完成记录不自动收起；等事件排空后延迟 800ms 收起并短暂高亮。
    if (!autoOpened.current) return;
    if (paced.draining) return;
    setFinishing(true);
    const timer = window.setTimeout(() => {
      setOpen(false);
      setOverrides({});
      setFinishing(false);
      autoOpened.current = false;
    }, 800);
    return () => window.clearTimeout(timer);
  }, [runId, running, waiting, paced.draining]);
  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (!running && !waiting) autoOpened.current = false;
  };
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (skillMode || events.some((event) => event.type.startsWith("skill."))) {
    const summary = continued ? "已继续处理" : waiting ? "等待业务选择" : running ? "正在处理本轮需求" : effectiveStatus === "CANCELLED" ? "已停止处理" : ["FAILED", "INTERRUPTED"].includes(effectiveStatus || "") ? "分析未完成" : completionLabel || "技能分析已完成";
    const records = paced.events.filter((event) => event.message && (event.type.startsWith("skill.") || event.type.startsWith("run.") || event.type.startsWith("analysis.") || event.type === "tool.started"));
    return <section className="run-timeline" aria-label={label || "技能处理记录"}>
      <button type="button" className="run-heading" data-finishing={finishing ? "true" : undefined} aria-expanded={open} onClick={toggle}>
        <StatusIcon status={running ? "active" : (continued || effectiveStatus === "COMPLETED") && completionLabel !== "分析受限" ? "done" : "blocked"} /><span>{label ? `${label} · ` : ""}{summary}</span><Chevron open={open} />
      </button>
      <span className="sr-only" role="status" aria-live="polite">{summary}</span>
      <Presence open={open}>
        <div className="run-content"><ol className="skill-run-records">{records.map((event, index) => <li key={`${event.seq}:${index}`}>{running ? event.message : event.message?.replace(/^正在/, "")}</li>)}</ol>{!records.length ? <p>{running ? "正在准备分析…" : "本轮没有保留处理步骤。"}</p> : null}{children ? <div className="run-question">{children}</div> : null}</div>
      </Presence>
      {followUp}
    </section>;
  }
  const view = buildRunView(paced.events, running ? initialPlan : plan, running, { runId, questions, status: effectiveStatus, now, results });
  const observedPlan = paced.events.slice().reverse().find((event) => event.plan)?.plan;
  const matched = new Map(clauses((observedPlan ?? plan)?.tree)
    .filter((clause) => clause.name && clause.status === "BOUND").map((clause) => [clause.name!, clause]));
  const latest = view.items.at(-1)?.id;
  const narrationId = [...view.items].reverse().find((i) => i.kind === "narration")?.id;
  const summary = continued ? "已继续处理" : running ? `正在${view.phase}` : waiting ? "等待业务选择" : effectiveStatus === "CANCELLED" ? "已停止处理" : ["FAILED", "INTERRUPTED"].includes(effectiveStatus || "") ? "已保存处理进度" : view.degraded ? `部分完成 · 已保留 ${view.degraded.kept_clauses.length} 项条件，${view.degraded.unresolved_clause_ids.length} 项待处理` : completionLabel || "已处理";
  const progress = view.todos.filter((t) => t.status === "done").length;
  return <section className="run-timeline" aria-label={label || "处理记录"}>
    <button type="button" className="run-heading" data-finishing={finishing ? "true" : undefined} aria-expanded={open} onClick={toggle}>
      <StatusIcon status={running ? "active" : waiting || view.degraded || ["FAILED", "INTERRUPTED", "CANCELLED"].includes(effectiveStatus || "") ? "blocked" : "done"} />
      <span>{label ? `${label} · ` : ""}{view.notice || summary}</span>
      <small>{view.elapsedMs ? `${Math.round(view.elapsedMs / 1000)} 秒 · ` : ""}{view.stats.steps} 步 · {view.stats.conditions} 个条件</small><Chevron open={open} />
    </button>
    <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">{summary}，{progress} 个阶段完成，共 {view.stats.steps} 步。</span>
    <Presence open={open}>
      <div className="run-content">
      <div className="run-plan-heading"><span>业务步骤</span><small>{progress}/{view.todos.length} 完成</small></div>
      <ol className="run-todos">{view.todos.map((todo) => <Todo key={todo.id} item={todo} />)}</ol>
      {view.items.length ? <details className="run-operation-details" open={running || !!view.degraded}><summary>执行明细</summary><ol className="run-entries">{view.items.map((item) => <TimelineRow key={item.id} item={item}
        expanded={overrides[item.id] ?? item.id === latest}
        toggle={() => setOverrides({ ...overrides, [item.id]: !(overrides[item.id] ?? item.id === latest) })}
        animate={!reduced && running && item.id === narrationId && Number(item.id.split(":").at(-1)) >= paced.liveFrom}
        matched={matched} onReveal={onReveal} />)}</ol></details> : null}
      {children ? <div className="run-question">{children}</div> : null}
      </div>
    </Presence>
    {followUp}
  </section>;
}
