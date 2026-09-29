import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Plan, RunEvent, Thread } from "./agentTypes";
import { actionLabel, buildRunView, groupLabel, type Action, type TimelineItem, type TodoItem, type TodoStatus } from "./runTimeline";
import { useEventPacer, useNarrationText, useReducedMotion } from "./useEventPacer";

const statusLabels: Record<TodoStatus, string> = { pending: "待办", active: "进行中", done: "完成", blocked: "受阻" };
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
function ActionBody({ action }: { action: Action }) {
  return <div className="run-action-body">
    {action.summary ? <p>{action.summary}</p> : action.status === "running" ? <p>正在核对，请稍候…</p> : null}
    {action.names.length ? <p>相关标签：{action.names.join("、")}</p> : null}
    {action.ms !== undefined ? <small>{(action.ms / 1000).toFixed(1)} 秒</small> : null}
  </div>;
}
function Narration({ text, animate }: { text: string; animate: boolean }) {
  const narration = useNarrationText(text, animate);
  return <span className="run-narration-text">{narration.text}{narration.streaming ? <span className="run-caret" aria-hidden="true" /> : null}</span>;
}
function TimelineRow({ item, expanded, toggle, animate, onReveal }: { item: TimelineItem; expanded: boolean; toggle: () => void; animate: boolean; onReveal?: (ids: string[]) => void }) {
  const action = item.kind === "action" || item.kind === "group";
  return <li className={`run-entry run-entry-${item.kind}`}>
    {action ? <>
      <button type="button" className="run-entry-toggle" aria-expanded={expanded} onClick={toggle}>
        <StatusIcon status={item.status} /><span className={item.status === "running" ? "run-working" : ""}>{item.kind === "action" ? actionLabel(item) : groupLabel(item)}</span>
        {!expanded ? <small>{item.kind === "action" ? item.summary : item.actions.at(-1)?.summary}</small> : null}
        <Chevron open={expanded} />
      </button>
      {expanded ? item.kind === "action" ? <ActionBody action={item} /> : <ol className="run-group-actions">{item.actions.map((a) => <li key={a.id}><div className="run-group-heading"><StatusIcon status={a.status} /><span>{actionLabel(a)}</span></div><ActionBody action={a} /></li>)}</ol> : null}
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
  return <svg className="run-chevron" data-open={open} viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m6 3 5 5-5 5" /></svg>;
}

export function RunTimeline({ events, runId, running, plan, questions, status, label, children, onReveal }: {
  events: RunEvent[]; runId: string; running: boolean; plan?: Plan; questions?: Thread["questions"]; status?: string;
  label?: string; children?: ReactNode; onReveal?: (ids: string[]) => void;
}) {
  const reduced = useReducedMotion();
  const paced = useEventPacer(events, runId, running, reduced);
  // 当前快照中的 live_plan 可能来自尚在队列中的事件，不能提前显示其进度。
  const initialPlan = useRef(plan).current;
  const [now, setNow] = useState(Date.now() / 1000);
  const effectiveStatus = status || [...events].reverse().map((e) => ({ "run.cancelled": "CANCELLED", "run.failed": "FAILED", "run.interrupted": "INTERRUPTED" }[e.type])).find(Boolean);
  const waiting = effectiveStatus === "WAITING";
  const [open, setOpen] = useState(running || waiting);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  useEffect(() => { setOpen(running || waiting); setOverrides({}); }, [runId, running, waiting]);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  const view = buildRunView(paced.events, running ? initialPlan : plan, running, { runId, questions, status: effectiveStatus, now });
  const latest = view.items.at(-1)?.id;
  const narrationId = [...view.items].reverse().find((i) => i.kind === "narration")?.id;
  const summary = running ? `正在${view.phase}` : waiting ? "等待业务选择" : effectiveStatus === "CANCELLED" ? "已停止处理" : ["FAILED", "INTERRUPTED"].includes(effectiveStatus || "") ? "已保存处理进度" : "已处理";
  const progress = view.todos.filter((t) => t.status === "done").length;
  return <section className="run-timeline" aria-label={label || "处理记录"}>
    <button type="button" className="run-heading" aria-expanded={open} onClick={() => setOpen(!open)}>
      <StatusIcon status={running ? "active" : waiting || ["FAILED", "INTERRUPTED", "CANCELLED"].includes(effectiveStatus || "") ? "blocked" : "done"} />
      <span>{label ? `${label} · ` : ""}{view.notice || summary}</span>
      <small>{view.elapsedMs ? `${Math.round(view.elapsedMs / 1000)} 秒 · ` : ""}{view.stats.steps} 步 · {view.stats.conditions} 个条件</small><Chevron open={open} />
    </button>
    <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">{summary}，{progress} 个阶段完成，共 {view.stats.steps} 步。</span>
    {open ? <div className="run-content">
      <div className="run-plan-heading"><span>计划</span><small>{progress}/4 完成</small></div>
      <ol className="run-todos">{view.todos.map((todo) => <Todo key={todo.id} item={todo} />)}</ol>
      <ol className="run-entries">{view.items.map((item) => <TimelineRow key={item.id} item={item}
        expanded={overrides[item.id] ?? item.id === latest}
        toggle={() => setOverrides({ ...overrides, [item.id]: !(overrides[item.id] ?? item.id === latest) })}
        animate={!reduced && running && item.id === narrationId && Number(item.id.split(":").at(-1)) >= paced.liveFrom}
        onReveal={onReveal} />)}</ol>
      {children ? <div className="run-question">{children}</div> : null}
    </div> : null}
  </section>;
}
