import { clauses, clauseChanged, clauseSentence, planDiff, toolText, type Plan, type RunEvent, type Thread } from "./agentTypes";

export type TodoStatus = "pending" | "active" | "done" | "blocked";
export type TodoItem = { id: string; label: string; status: TodoStatus; result?: string; children?: TodoItem[] };
export type Action = { kind: "action"; id: string; tool: string; targets: string[]; requirementIds: string[]; status: "running" | "done" | "error" | "stopped"; summary?: string; names: string[]; ms?: number; startedAt?: number; callId?: string; depth?: string };
export type TimelineItem = Action | { kind: "group"; id: string; tool: string; actions: Action[]; status: Action["status"] }
  | { kind: "narration"; id: string; text: string }
  | { kind: "change"; id: string; diff: string[]; clauseIds: string[] }
  | { kind: "status"; id: string; text: string };
export type RunView = { phase: string; todos: TodoItem[]; items: TimelineItem[]; elapsedMs: number; stats: { steps: number; conditions: number }; notice?: string };

export function actionLabel(action: Action): string {
  const target = action.targets.length ? `「${action.targets.join("、")}」` : "";
  if (action.tool === "find_tags") return `${action.depth === "deep" ? "换个角度深入查找" : "查找标签"}${target}`;
  if (action.tool === "get_tag_details") return target ? `核对${target}的口径` : "核对标签口径与取值";
  if (action.tool === "find_capabilities") return `查找业务定义${target}`;
  return toolText[action.tool] || "处理圈选条件";
}
export function groupLabel(item: Extract<TimelineItem, { kind: "group" }>): string {
  const verbs: Record<string, string> = { find_tags: "查找标签", get_tag_details: "核对标签口径", find_capabilities: "查找业务定义", check_plan: "核验圈选条件", submit_result: "整理圈选方案" };
  return `${verbs[item.tool] || "处理圈选条件"} · ${item.actions.length} 次操作`;
}

export function buildRunView(events: RunEvent[], plan?: Plan, running = false, options: { runId?: string; questions?: Thread["questions"]; status?: string; now?: number } = {}): RunView {
  const runId = options.runId || "run";
  const items: TimelineItem[] = [];
  const actions: Action[] = [];
  let observed: Plan | undefined;
  let latestPlan: Plan | undefined;
  let lastNarration = -1;
  let notice: string | undefined;
  for (const [index, event] of events.entries()) {
    const id = `${runId}:${index}`;
    if (event.plan) latestPlan = event.plan;
    if (["run.queued", "run.lean"].includes(event.type)) { notice = event.message; continue; }
    if (event.type === "tool.started" || event.type === "tool.completed") {
      const tool = event.tool || "";
      let action = event.call_id ? actions.find((a) => a.callId === event.call_id)
        : event.type === "tool.completed" ? actions.find((a) => a.tool === tool && a.status === "running") : undefined;
      if (!action) {
        action = { kind: "action", id, tool, callId: event.call_id, targets: [], requirementIds: [], status: "running", names: [] };
        actions.push(action); items.push(action);
      }
      if (event.targets) action.targets = event.targets;
      if (event.requirement_ids) action.requirementIds = event.requirement_ids;
      if (event.depth) action.depth = event.depth;
      if (event.type === "tool.started") action.startedAt = event.occurred_at;
      else {
        action.status = event.ok === false ? "error" : "done";
        action.summary = event.summary || event.message;
        action.names = (event.items || event.candidates || []).map((c) => c.name);
        action.ms = event.duration_ms ?? (action.startedAt && event.occurred_at ? Math.max(0, (event.occurred_at - action.startedAt) * 1000) : undefined);
      }
    } else if (event.type === "narration" && event.text) {
      const item: TimelineItem = { kind: "narration", id, text: event.text };
      // SDK 文本有时晚于 MCP started；只在本段操作内纠正顺序。
      const start = items.findIndex((i, n) => n > lastNarration && i.kind === "action" &&
        (event.call_ids?.length ? !!i.callId && event.call_ids.includes(i.callId) : i.status === "running"));
      if (start >= 0) { items.splice(start, 0, item); lastNarration = start; }
      else { items.push(item); lastNarration = items.length - 1; }
    } else if (event.type === "plan.observed" && event.plan) {
      const diff = planDiff(observed, event.plan);
      const before = new Map(clauses(observed?.tree).map((c) => [c.clause_id, c]));
      const clauseIds = clauses(event.plan.tree).filter((c) => !before.has(c.clause_id) || clauseChanged(before.get(c.clause_id)!, c)).map((c) => c.clause_id);
      const businessDiff: string[] = [];
      const afterIds = new Set(clauses(event.plan.tree).map((c) => c.clause_id));
      for (const c of clauses(event.plan.tree)) {
        const prior = before.get(c.clause_id);
        if (!prior) businessDiff.push(`新增条件：${clauseSentence(c)}`);
        else if (clauseIds.includes(c.clause_id)) businessDiff.push(`修改条件：${clauseSentence(prior)} → ${clauseSentence(c)}`);
      }
      for (const c of before.values()) if (!afterIds.has(c.clause_id)) businessDiff.push(`删除条件：${clauseSentence(c)}`);
      if (diff.includes("条件组合结构已变化")) businessDiff.push("条件组合结构已变化");
      if (diff.length) items.push({ kind: "change", id, diff: businessDiff, clauseIds });
      observed = event.plan;
    } else if (["run.cancelled", "run.failed", "run.interrupted"].includes(event.type)) {
      items.push({ kind: "status", id, text: { "run.cancelled": "本轮处理已停止", "run.failed": "本轮暂未完成，已保留进度", "run.interrupted": "处理已中断，可从保存位置继续" }[event.type]! });
    }
  }
  if (!running) for (const a of actions) if (a.status === "running") { a.status = "stopped"; a.summary = "本次操作未完成"; }
  // 结束后的当前方案可能已被用户编辑；事件快照仅代表当时版本。
  const currentPlan = (!running && plan) || latestPlan || plan;
  const nodes = clauses(currentPlan?.tree);
  const temp = new Map<string, string>();
  for (const e of events.filter((e) => e.type === "tool.started" && e.tool === "find_tags")) {
    if (e.queries?.length) for (const q of e.queries) temp.set(q.requirement_id || `query:${q.text}`, q.text);
    else for (const [i, target] of (e.targets || []).entries()) temp.set(e.requirement_ids?.[i] || `query:${target}`, target);
  }
  const rawRequirements = currentPlan?.intent_plan?.requirements || (temp.size ? [...temp].map(([requirement_id, business_meaning]) => ({ requirement_id, business_meaning }))
    : nodes.flatMap((c) => (c.requirement_ids || [c.clause_id]).map((requirement_id) => ({ requirement_id, business_meaning: c.source_span || c.query || c.name || "圈选条件" }))));
  const requirements = [...new Map(rawRequirements.map((r) => [r.requirement_id, r])).values()];
  const children: TodoItem[] = requirements.map((r) => {
    const matches = nodes.filter((c) => (c.requirement_ids || [c.clause_id]).includes(r.requirement_id));
    const asked = options.questions?.some((q) => q.requirement_id === r.requirement_id || matches.some((c) => c.clause_id === q.clause_id));
    const assumed = currentPlan?.intent_plan?.assumptions?.some((a) => a.requirement_id === r.requirement_id && ["PENDING", "PUBLISHED"].includes(a.status) && (!matches.length || !matches.every((c) => c.assumption_confirmed)));
    const blocked = asked || assumed || matches.some((c) => c.unresolved || c.gap_reason || c.status === "NEEDS_DECISION" || (c.status === "ASSUMED" && !c.assumption_confirmed));
    const done = matches.length > 0 && matches.every((c) => c.status === "BOUND");
    const active = running && actions.some((a) => a.status === "running" && (a.requirementIds.includes(r.requirement_id) || a.targets.includes(r.business_meaning)));
    return { id: r.requirement_id, label: done ? matches.map((c) => c.name || r.business_meaning).join("、") : r.business_meaning,
      result: matches.length ? matches.map(clauseSentence).join("；") : undefined,
      status: blocked ? "blocked" : done ? "done" : active ? "active" : "pending" };
  });
  const validated = events.some((e) => e.type === "plan.validated");
  const terminal = !running && options.status !== "WAITING" && (events.length > 0 || !!currentPlan);
  const done = [events.some((e) => e.type === "intent.ready" || (e.type === "tool.started" && e.tool === "find_tags")),
    (children.length > 0 && children.every((c) => c.status === "done")) || validated,
    validated && !!currentPlan?.valid && !children.some((c) => c.status === "blocked"), terminal];
  const labels = ["理解需求", "匹配标签与口径", "校验圈选方案", "整理结果"];
  const first = done.findIndex((d) => !d);
  const todos: TodoItem[] = labels.map((label, i) => ({ id: `phase:${i}`, label, status: done[i] ? "done" : running && i === first ? "active" : !running && i === first ? "blocked" : "pending", ...(i === 1 ? { children } : {}) }));
  const grouped: TimelineItem[] = [];
  for (const item of items) {
    const last = grouped.at(-1);
    if (item.kind === "action" && (last?.kind === "action" || last?.kind === "group") && last.tool === item.tool) {
      const groupActions = last.kind === "group" ? [...last.actions, item] : [last, item];
      grouped[grouped.length - 1] = { kind: "group", id: last.id, tool: item.tool, actions: groupActions,
        status: groupActions.some((a) => a.status === "running") ? "running" : groupActions.some((a) => a.status === "error") ? "error" : groupActions.some((a) => a.status === "stopped") ? "stopped" : "done" };
    } else grouped.push(item);
  }
  const times = events.map((e) => e.occurred_at).filter((t): t is number => typeof t === "number" && t > 0);
  const elapsedMs = times.length ? Math.max(0, ((running ? options.now || Date.now() / 1000 : Math.max(...times)) - Math.min(...times)) * 1000) : 0;
  if (actions.length) notice = undefined;
  return { phase: running ? labels[first < 0 ? 3 : first] : options.status === "WAITING" ? "等待业务选择" : "已处理", todos, items: grouped, elapsedMs,
    stats: { steps: actions.length, conditions: requirements.length || nodes.length }, notice };
}
