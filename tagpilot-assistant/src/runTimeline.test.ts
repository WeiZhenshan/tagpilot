import { describe, expect, it } from "vitest";
import { buildRunView } from "./runTimeline";
import type { Plan, RunEvent } from "./agentTypes";
const plan: Plan = { valid: true, intent_plan: { requirements: [{ requirement_id: "R1", business_meaning: "近30天转入" }, { requirement_id: "R2", business_meaning: "排除销户" }] }, tree: { logic: "AND", children: [
  { clause_id: "c1", requirement_ids: ["R1"], name: "转入金额", status: "BOUND", operator: ">", values: ["50000"], unit: "CNY" },
  { clause_id: "c2", requirement_ids: ["R2"], name: "客户状态", status: "BOUND", operator: "not_in", values: ["CLOSED"], code_options: [{ code: "CLOSED", label: "已销户" }] },
] } };
const start = (call_id: string, refs = ["R1"]): RunEvent => ({ seq: 1, type: "tool.started", tool: "find_tags", call_id, requirement_ids: refs, targets: ["近30天转入"], occurred_at: 100 });
const end = (call_id: string, ok = true): RunEvent => ({ seq: 2, type: "tool.completed", tool: "find_tags", call_id, ok, summary: "找到 5 个相关标签", duration_ms: 400, occurred_at: 101 });

describe("处理记录视图", () => {
  it("配对并行调用，按开始顺序合并同类动作", () => {
    const v = buildRunView([start("a"), start("b"), end("b"), end("a")], undefined, true);
    expect(v.stats.steps).toBe(2);
    const group = v.items[0];
    expect(group.kind).toBe("group");
    if (group.kind === "group") expect(group.actions.map((a) => [a.callId, a.ms, a.status])).toEqual([["a", 400, "done"], ["b", 400, "done"]]);
  });
  it("旧事件按工具配对，独立 completed 仍可回放", () => {
    const events = [start("a"), end("a"), { seq: 3, type: "tool.completed", message: "已核对口径" }].map(({ call_id: _, ...e }) => e);
    const v = buildRunView(events);
    expect(v.stats.steps).toBe(2);
    expect(v.items.length).toBe(2);
  });
  it("检索查询先生成临时需求，再用台账和绑定条件替换", () => {
    const initial = buildRunView([{ ...start("a"), queries: [{ text: "资金转入", requirement_id: "R1" }] }], undefined, true);
    expect(initial.todos[0].status).toBe("done");
    expect(initial.todos[1].children?.[0]).toMatchObject({ label: "资金转入", status: "active" });
    const v = buildRunView([start("a"), { seq: 2, type: "intent.ready", plan }], plan, true);
    expect(v.todos[1].children?.[0]).toMatchObject({ label: "转入金额", status: "done", result: "转入金额 大于 50000元" });
  });
  it.each(["ASSUMED", "NEEDS_DECISION"])("%s 保持受阻", (status) => {
    const p = structuredClone(plan); if ("children" in p.tree) p.tree.children[0] = { ...p.tree.children[0], status };
    expect(buildRunView([], p).todos[1].children?.[0].status).toBe("blocked");
  });
  it("有 unresolved、gap 或问题时，不能因 BOUND 误报完成", () => {
    const p = structuredClone(plan); if ("children" in p.tree) p.tree.children[0] = { ...p.tree.children[0], unresolved: "口径待定" };
    expect(buildRunView([], p).todos[1].children?.[0].status).toBe("blocked");
    const v = buildRunView([], plan, false, { questions: [{ clause_id: "c2", prompt: "是否排除？" }], status: "WAITING" });
    expect(v.todos[1].children?.[1].status).toBe("blocked");
    expect(v.todos[3].status).toBe("pending");
    expect(v.phase).toBe("等待业务选择");
  });
  it("阶段校验需要 plan.valid，终止后不保留转圈", () => {
    const p = { ...plan, valid: false };
    const v = buildRunView([start("a"), { seq: 2, type: "plan.validated", plan: p }], p, false, { status: "FAILED" });
    expect(v.todos.map((t) => t.status)).toEqual(["done", "done", "blocked", "done"]);
    expect(v.items[0]).toMatchObject({ status: "stopped" });
  });
  it("当前方案阻断不能被旧事件快照覆盖", () => {
    const p = { ...plan, valid: false };
    const v = buildRunView([{ seq: 1, type: "intent.ready", plan }, { seq: 2, type: "plan.validated", plan }], p, false, { status: "WAITING", questions: [{ clause_id: "c1", prompt: "请确认口径" }] });
    expect(v.todos[2].status).toBe("blocked");
    expect(v.todos[1].children?.[0].status).toBe("blocked");
  });
  it("完整运行四个阶段完成，正确统计耗时", () => {
    const v = buildRunView([start("a"), end("a"), { seq: 3, type: "plan.validated", plan, occurred_at: 134 }], plan, false);
    expect(v.todos.every((t) => t.status === "done")).toBe(true);
    expect(v.elapsedMs).toBe(34000);
    expect(v.stats.conditions).toBe(2);
  });
  it("错误完成事件不会显示成功", () => expect(buildRunView([start("a"), end("a", false)]).items[0]).toMatchObject({ status: "error" }));
  it("方案变化插入变更，重复相同方案不插入", () => {
    const updated = structuredClone(plan); if ("children" in updated.tree) updated.tree.children[0] = { ...updated.tree.children[0], values: ["60000"] };
    const events = [plan, plan, updated].map((p, seq) => ({ seq, type: "plan.observed", plan: p }));
    const changes = buildRunView(events).items.filter((i) => i.kind === "change");
    expect(changes).toHaveLength(2);
    expect(changes[1]).toMatchObject({ clauseIds: ["c1"] });
  });
  it("晚到的叙述插在尚未结束的动作之前", () => {
    const v = buildRunView([start("a"), { seq: 2, type: "narration", text: "先核对转入的统计口径" }, end("a")]);
    expect(v.items.map((i) => i.kind)).toEqual(["narration", "action"]);
  });
  it("重复取消 seq=-1 和不同轮次均有唯一 key", () => {
    const events = [{ seq: -1, type: "run.cancelled" }, { seq: -1, type: "run.cancelled" }];
    const a = buildRunView(events, undefined, false, { runId: "a" });
    const b = buildRunView(events, undefined, false, { runId: "b" });
    expect(new Set([...a.items, ...b.items].map((i) => i.id)).size).toBe(4);
  });
  it("过滤无展示价值的事件，排队保留状态条", () => {
    const v = buildRunView([{ seq: 1, type: "run.queued", message: "排队中，第 2 位" }, { seq: 2, type: "telemetry.span" }, { seq: 3, type: "run.started" }], undefined, true);
    expect(v.items).toEqual([]); expect(v.notice).toBe("排队中，第 2 位");
  });
  it("没有叙述和新字段时也有动作描述", () => {
    const v = buildRunView([{ seq: 1, type: "tool.started", tool: "find_tags" }], undefined, true);
    expect(v.items[0]).toMatchObject({ kind: "action", status: "running" });
  });
});
