import { describe, expect, it } from "vitest";
import type { Thread } from "./agentTypes";
import { conversationRuns, reportMessageId } from "./conversationRuns";

const fixture = (): Thread => ({
  library_id: 107, title: "合成测试", archived: false, pinned: false, revision: 1,
  versions: [], capabilities: { count: true, preview: true, create: true },
  thread_id: "thread", status: "RUNNING", run_id: "skill", run_profile: "skill",
  events: [{ seq: 1, type: "skill.resource", message: "正在读取技能参考资料" }],
  run_history: [{ run_id: "audience", events: [] }],
  messages: [
    { id: "u1", role: "user", run_id: "audience", text: "圈选客户", created_at: "2026-09-30T00:00:00Z" },
    { id: "a1", role: "assistant", run_id: "audience", text: "圈选完成", created_at: "2026-09-30T00:00:01Z" },
    { id: "u2", role: "user", run_id: "skill", text: "分析客户", created_at: "2026-09-30T00:00:02Z" },
  ],
});

describe("对话轮次归属", () => {
  it("历史记录留在原需求之后，技能流式记录跟随本轮需求", () => {
    expect(conversationRuns(fixture()).map((run) => [run.run_id, run.afterMessageId])).toEqual([["audience", "u1"], ["skill", "u2"]]);
  });
  it("完成、归档后保持同一位置，报告摘要跟随技能答复", () => {
    const thread = fixture();
    thread.status = "COMPLETED";
    thread.messages.push({ id: "a2", role: "assistant", run_id: "skill", text: "技能完成", created_at: "" });
    expect(reportMessageId(thread, "skill")).toBe("a2");
    thread.run_history!.push({ run_id: "skill", events: thread.events, profile: "skill" });
    thread.run_id = "next"; thread.events = []; thread.status = "RUNNING";
    thread.messages.push({ id: "u3", role: "user", run_id: "next", text: "修改条件", created_at: "" });
    expect(conversationRuns(thread).map((run) => run.afterMessageId)).toEqual(["u1", "u2", "u3"]);
    expect(reportMessageId(thread, "skill")).toBe("a2");
  });
  it("兼容旧消息及恢复运行时未携带 run_id 的业务补充", () => {
    const thread = fixture();
    thread.messages.forEach((message) => delete message.run_id);
    expect(conversationRuns(thread).map((run) => run.afterMessageId)).toEqual(["u1", "u2"]);
    thread.messages.push({ id: "answer", role: "user", text: "采用已发布口径", created_at: "" });
    expect(conversationRuns(thread).at(-1)?.afterMessageId).toBe("answer");
  });
  it("不重复展示当前运行，孤立历史保留可回放记录", () => {
    const thread = fixture(); thread.run_history!.push({ run_id: "skill", events: [] });
    expect(conversationRuns(thread)).toHaveLength(2);
    thread.messages = [];
    expect(conversationRuns(thread).every((run) => !run.afterMessageId)).toBe(true);
  });
});
