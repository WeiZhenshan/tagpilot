import { stagedQuestions } from "./clarification";

export type Expression = {
  kind: string;
  tag_id?: number;
  name?: string;
  value?: string;
  unit?: string;
  args?: Expression[];
  capability_id?: string;
  version?: number;
};
export type Diagnostic = {
  clause_id?: string;
  code?: string;
  message: string;
  expected?: unknown;
  actual?: unknown;
  user_decision_required?: boolean;
  resolution?: "AGENT_FIXABLE" | "USER_DECISION" | "CAPABILITY_GAP";
};
export type Clause = {
  kind?: string;
  requirement_ids?: string[];
  expression?: Expression;
  compare_expression?: Expression;
  time_alignment?: string;
  clause_id: string;
  source_span?: string;
  query?: string;
  tag_id?: number;
  name?: string;
  operator?: string;
  values?: string[];
  unresolved?: string | null;
  gap_reason?: string;
  assumption?: { question?: string; status: string };
  assumption_confirmed?: boolean;
  status?: string;
  unit?: string;
  value_unit?: string;
  value_scale?: string;
  expected_caliber?: Record<string, unknown>;
  null_policy?: string;
  unknown_policy?: string;
  definition?: string;
  time_constraint?: string;
  allowed_operators?: string[];
  code_options?: { code: string; label: string }[];
  candidates?: { tag_id: number; name: string }[];
  evidence_id?: string;
  caliber_struct?: Record<string, unknown>;
};
export type Group = { logic: "AND" | "OR"; children: Tree[] };
export type Tree = Clause | Group;
export type Plan = {
  schema_version?: number;
  plan_status?: string;
  intent_plan?: { requirements: { requirement_id: string; business_meaning: string }[]; assumptions?: { requirement_id?: string; status: string; question?: string }[] };
  diagnostics?: Diagnostic[];
  tree: Tree;
  valid?: boolean;
  revision?: number;
  hash?: string;
  summary?: string;
  build_id?: string;
  snapshot_id?: string;
  artifact_hash?: string;
  validation_errors?: Diagnostic[];
  confirmed_clause_ids?: string[];
};
export type RunEvent = {
  seq: number;
  type: string;
  message?: string;
  tool?: string;
  call_id?: string;
  call_ids?: string[];
  targets?: string[];
  requirement_ids?: string[];
  queries?: { text: string; requirement_id?: string }[];
  depth?: "quick" | "deep";
  ok?: boolean;
  summary?: string;
  items?: { name: string }[];
  counts?: { found?: number; pending?: number };
  duration_ms?: number;
  text?: string;
  clause_id?: string;
  occurred_at?: number;
  steps?: { id: string; label: string; status: string }[];
  stats?: Record<string, unknown>;
  plan?: Plan;
  candidates?: { tag_id: number; name: string }[];
};
export type AgentMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  revision?: number;
  run_id?: string;
  created_at: string;
  context_tags?: ContextTag[];
};
export type ContextTag = { id: number; name: string };
export type TagTreeNode = { id: string; label: string; tagId?: number; tagType?: string; dirPath?: string; children?: TagTreeNode[] };
export type Thread = {
  thread_id: string;
  library_id: number;
  title: string;
  archived: boolean;
  pinned: boolean;
  status: string;
  revision: number;
  messages: AgentMessage[];
  plan?: Plan;
  live_plan?: Plan;
  versions: Plan[];
  events: RunEvent[];
  run_history?: { run_id: string; events: RunEvent[] }[];
  run_id?: string;
  questions?: { clause_id?: string; requirement_id?: string; prompt: string; options?: string[]; reason?: string }[];
  interrupt_id?: string;
  error?: string;
  outcome?: { outcome: string; gaps: { requirement_id: string; reason: string; nearest_tag_ids: number[] }[]; stats?: Record<string, unknown> };
  confirmed_clause_ids?: string[];
  capabilities: { count: boolean; create: boolean; update?: boolean; preview: boolean };
  source_group_id?: number;
  source_group_name?: string;
  source_thread_reused?: boolean;
  source_requires_validation?: boolean;
  count?: {
    value: number;
    revision: number;
    executed_at: string;
    data_as_of?: string;
    warning?: string;
  };
  execution?: { group_id: number; revision: number };
};
export type ThreadRow = {
  threadId: string;
  libraryId: number;
  title: string;
  updateTime: string;
  archived: string;
  pinned: string;
};
export const busy = (t?: Thread | null) =>
  !!t && ["RUNNING", "SUBMITTING"].includes(t.status);
export function clauses(tree?: Tree): Clause[] {
  return !tree
    ? []
    : "children" in tree
    ? tree.children.flatMap(clauses)
    : [tree];
}
export const stateText: Record<string, string> = {
  IDLE: "准备就绪",
  RUNNING: "处理中",
  SUBMITTING: "正在提交",
  WAITING: "待业务选择",
  COMPLETED: "处理完成",
  CANCELLED: "已停止",
  FAILED: "暂未完成",
  INTERRUPTED: "可恢复",
};
export const degradedText = {
  timeout: "处理时间较长，已保留已确认的条件",
  memory_limit: "运行资源不足，已保存进度，请手工编辑或稍后重试",
  max_turns: "本轮处理次数已达上限，已保留当前方案",
  max_budget: "本轮模型预算已用完，已保留当前方案",
  tool_budget: "本轮检索与核验预算已用完，已保留当前方案",
  queue_timeout: "当前使用人数较多，排队已超时，请稍后重试",
  gateway: "模型服务暂不可用，已保存进度，请稍后重试",
  retrieval: "标签检索服务暂不可用，已保存进度，请稍后重试",
};
export type Degraded = {
  level: "L2" | "L3" | "L4";
  reason: keyof typeof degradedText;
  kept_clauses: string[];
  unresolved_clause_ids: string[];
  resumable: boolean;
  resume_mode: "lean" | "manual" | "retry";
  attempt: number;
  user_message?: string;
  ops_alert: boolean;
};
export function degradedOf(thread?: Thread | null): Degraded | undefined {
  return parseDegraded(thread?.outcome?.stats?.degraded);
}
export function parseDegraded(value: unknown): Degraded | undefined {
  if (!value || typeof value !== "object") return undefined;
  const d = value as Degraded;
  if (!["L2", "L3", "L4"].includes(d.level) || !Object.hasOwn(degradedText, d.reason) ||
      !Array.isArray(d.kept_clauses) || !Array.isArray(d.unresolved_clause_ids) ||
      !d.kept_clauses.every((id) => typeof id === "string") ||
      !d.unresolved_clause_ids.every((id) => typeof id === "string")) return undefined;
  return { ...d, resumable: d.resumable === true, user_message: typeof d.user_message === "string" ? d.user_message : undefined };
}
export function degradedMessage(d: Degraded): string {
  if (!d.kept_clauses.length && d.level !== "L4") return "尚未形成可用条件，已保存需求和待确认的口径。";
  return d.user_message || degradedText[d.reason];
}
export function runNotice(thread?: Thread | null): "partial" | "failure" | undefined {
  if (!thread) return undefined;
  if (["FAILED", "INTERRUPTED"].includes(thread.status)) return "failure";
  const d = degradedOf(thread);
  if (thread.status === "COMPLETED" && d && d.level !== "L4") return "partial";
  return undefined;
}
export const planStateText: Record<string, string> = {
  DRAFT: "方案草稿", NEEDS_DECISION: "待业务选择", CAPABILITY_GAP: "缺少数据或计算能力",
  READY: "条件已核验", RETRYABLE_FAILURE: "已保存进度，可稍后继续",
};
export function expressionText(e?: Expression): string {
  if (!e) return "待补充计算方式";
  if (e.kind === "TAG") return e.name || "待核验指标";
  if (e.kind === "CONST") return e.value || "0";
  if (e.kind === "CAPABILITY") return e.name || "已发布计算能力";
  const args = (e.args || []).map(expressionText);
  if (e.kind === "COUNT_POSITIVE") return `以下 ${args.length} 类中余额大于零的类数：${args.join("、")}`;
  const signs: Record<string, string> = { ADD: "+", SUB: "−", MUL: "×", DIV: "÷" };
  return `(${args.join(` ${signs[e.kind] || e.kind} `)})`;
}
export function planDiff(before: Plan | undefined, after: Plan): string[] {
  const old = new Map(clauses(before?.tree).map((c) => [c.clause_id, c]));
  const changes: string[] = [];
  for (const c of clauses(after.tree)) {
    const prior = old.get(c.clause_id);
    if (!prior) changes.push(`新增：${c.name || c.source_span || c.clause_id}`);
    else if (
      JSON.stringify([prior.kind, prior.tag_id, prior.operator, prior.values, prior.expression, prior.compare_expression, prior.expected_caliber, prior.time_alignment]) !==
      JSON.stringify([c.kind, c.tag_id, c.operator, c.values, c.expression, c.compare_expression, c.expected_caliber, c.time_alignment])
    )
      changes.push(
        `修改：${c.name || c.source_span || c.clause_id} ${
          prior.operator || ""
        } ${(prior.values || []).join("、")} → ${c.operator || ""} ${(
          c.values || []
        ).join("、")}`
      );
    old.delete(c.clause_id);
  }
  for (const c of old.values())
    changes.push(`删除：${c.name || c.source_span || c.clause_id}`);
  function logic(t?: Tree): unknown {
    return !t
      ? null
      : "children" in t
      ? [t.logic, t.children.map(logic)]
      : t.clause_id;
  }
  if (
    before &&
    JSON.stringify(logic(before.tree)) !== JSON.stringify(logic(after.tree))
  )
    changes.push("条件组合结构已变化");
  return changes;
}

export const operatorNames: Record<string, string> = {
  "=": "等于", "!=": "不等于", ">": "大于", ">=": "至少", "<": "小于", "<=": "不超过",
  in: "属于", not_in: "不属于", between: "介于", contains: "包含", like: "匹配", is_null: "为空", is_not_null: "不为空",
};
export const unitLabels: Record<string, string> = {
  CNY: "元", COUNT: "次", RATIO: "比例", PERSON: "人", DAY: "天", MONTH: "月", POINT: "点", SHARE: "份",
};
export function clauseUnit(c: Clause): string {
  const unit = c.value_unit || c.unit;
  if (!unit || unit === "NONE") return "";
  const scale = Number(c.value_scale || 1);
  return `${scale === 10000 ? "万" : scale !== 1 ? `${c.value_scale} × ` : ""}${unitLabels[unit] || unit}`;
}
export function clauseSentence(c: Clause): string {
  if (c.kind === "SCOPE_ALL") return "当前授权范围内的全部客户";
  const name = c.kind === "DERIVED_PREDICATE" ? expressionText(c.expression) : c.name || c.source_span || c.query || "待选择标签";
  const time = c.time_constraint && !name.includes(c.time_constraint) ? `${c.time_constraint} ` : "";
  if (!c.operator) return `${time}${name}`;
  const op = operatorNames[c.operator] || c.operator;
  if (["is_null", "is_not_null"].includes(c.operator)) return `${time}${name} ${op}`;
  const values = (c.values || []).map((v) => c.code_options?.find((o) => o.code === v)?.label || v);
  const value = c.compare_expression ? expressionText(c.compare_expression)
    : values.length ? `${values.join(c.operator === "between" ? " 至 " : "、")}${c.code_options?.length ? "" : clauseUnit(c) === "比例" ? "（比例）" : clauseUnit(c)}` : "待补充条件值";
  return `${time}${name} ${op} ${value}`;
}
export function clauseChanged(before: Clause, after: Clause): boolean {
  const content = (c: Clause) => [c.kind, c.tag_id, c.name, c.operator, c.values, c.expression, c.compare_expression,
    c.expected_caliber, c.time_alignment, c.time_constraint, c.unit, c.value_unit, c.value_scale, c.null_policy, c.unknown_policy];
  return JSON.stringify(content(before)) !== JSON.stringify(content(after));
}
export function treeSentence(tree: Tree): string {
  if (!("children" in tree)) return clauseSentence(tree);
  return `满足以下${tree.logic === "AND" ? "全部" : "任一"}条件：\n${tree.children.map((child) =>
    "children" in child ? `（${treeSentence(child)}）` : `• ${clauseSentence(child)}`).join("\n")}`;
}
export type PendingItem = {
  id: string;
  kind: "gap" | "assumption" | "clause" | "diagnostic" | "question";
  title: string;
  message: string;
  clause_id?: string;
};
export function pendingItems(thread: Thread | null, plan?: Plan): PendingItem[] {
  const result: PendingItem[] = [];
  const items = clauses(plan?.tree);
  const covered = new Set<string>();
  if (thread?.status === "WAITING") for (const [i, q] of stagedQuestions(thread.questions || []).entries()) {
    result.push({ id: `question:${i}`, kind: "question", title: q.prompt, message: "在对话中确认业务选择后继续。", clause_id: q.clause_id });
    if (q.clause_id) covered.add(q.clause_id);
  }
  for (const gap of thread?.outcome?.gaps || []) {
    const c = items.find((c) => (c.requirement_ids || [c.clause_id]).includes(gap.requirement_id));
    if (c && covered.has(c.clause_id)) continue;
    result.push({ id: `gap:${gap.requirement_id}`, kind: "gap", clause_id: c?.clause_id,
      title: plan?.intent_plan?.requirements.find((r) => r.requirement_id === gap.requirement_id)?.business_meaning || c?.source_span || c?.name || "一项圈选要求",
      message: c?.gap_reason === "BUDGET_EXHAUSTED" ? "这项条件暂未确定，候选标签尚待核验" : gapText[gap.reason] || "当前证据不足" });
    if (c) covered.add(c.clause_id);
  }
  for (const c of items) {
    if (covered.has(c.clause_id)) continue;
    const assumed = c.status === "ASSUMED" && !c.assumption_confirmed;
    const unresolved = !!c.unresolved || !!c.gap_reason || (c.status !== "BOUND" && !plan?.valid);
    if (!assumed && !unresolved) continue;
    result.push({ id: `clause:${c.clause_id}`, kind: assumed ? "assumption" : "clause", clause_id: c.clause_id,
      title: assumed ? c.assumption?.question || `请确认“${c.name || c.source_span || "这项条件"}”的业务定义` : c.name || c.source_span || c.query || "待补充条件",
      message: assumed ? clauseSentence(c) : c.unresolved || gapText[c.gap_reason || ""] || "请选择标签或补充条件，然后重新核验。" });
    covered.add(c.clause_id);
  }
  for (const [i, d] of (plan?.diagnostics?.length ? plan.diagnostics : plan?.validation_errors || []).entries()) {
    if (d.clause_id && covered.has(d.clause_id)) continue;
    if (result.some((item) => item.message === d.message)) continue;
    result.push({ id: `diagnostic:${i}`, kind: "diagnostic", title: "这项条件需要处理", message: d.message, clause_id: d.clause_id });
    if (d.clause_id) covered.add(d.clause_id);
  }
  if (plan && !plan.valid && !result.length) result.push({ id: "validation", kind: "diagnostic", title: "方案尚待核验", message: "核对条件后保存并核验，或在对话中继续补充要求。" });
  return result;
}

export const toolText: Record<string, string> = {
  find_tags: "查找相关标签", get_tag_details: "核对标签口径与码值", find_capabilities: "查找已发布业务能力",
  check_plan: "核验圈选条件", submit_result: "整理圈选方案",
};
export const gapText: Record<string, string> = {
  BUDGET_EXHAUSTED: "本轮预算已用完，这项条件暂未确定",
  RETRIEVAL_UNAVAILABLE: "标签检索暂不可用，请稍后重试",
  NO_PUBLISHED_TAG: "尚无已发布标签覆盖这项要求", NO_CAPABILITY: "尚无已发布计算能力覆盖这项要求",
  CALIBER_UNAVAILABLE: "缺少符合要求的时间或统计口径", METADATA_INCOMPLETE: "发布信息不足，暂时无法核验",
};
