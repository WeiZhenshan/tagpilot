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
  intent_plan?: { requirements: { requirement_id: string; business_meaning: string }[]; assumptions?: { status: string; question?: string }[] };
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
};
export type RunEvent = {
  seq: number;
  type: string;
  message?: string;
  tool?: string;
  clause_id?: string;
  occurred_at?: number;
  steps?: { id: string; label: string; status: string }[];
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
};
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
  questions?: { clause_id?: string; prompt: string; options?: string[] }[];
  interrupt_id?: string;
  error?: string;
  capabilities: { count: boolean; create: boolean; preview: boolean };
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
