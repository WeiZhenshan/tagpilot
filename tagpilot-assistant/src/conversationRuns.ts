import { busy, type AgentMessage, type RunEvent, type Thread } from "./agentTypes";
import type { AnalysisPart } from "./insight/analysisTypes";

type ConversationRun = {
  run_id: string; profile?: string; current: boolean; label: string; events: RunEvent[];
  id: string; continued: boolean; afterMessageId?: string; responseParts: AnalysisPart[]; responseMessageId?: string; requestText?: string;
};

function turnEvents(events: RunEvent[], inputs: AgentMessage[]) {
  let start = 0;
  return inputs.map((_, index) => {
    if (index === inputs.length - 1) return events.slice(start);
    // resume 沿用 run_id；等待/失败事件是前一次输入的结束位置。
    const stop = events.findIndex((event, position) => position >= start &&
      ["run.waiting", "run.failed", "run.interrupted", "run.cancelled"].includes(event.type));
    const nextTime = Date.parse(inputs[index + 1].created_at) / 1000;
    const timed = events.findIndex((event, position) => position >= start &&
      event.occurred_at !== undefined && event.occurred_at >= nextTime);
    // 兼容没有终止事件的旧记录；无法分段时让记录跟随最新输入。
    const end = stop >= 0 ? stop + 1 : timed >= 0 ? timed : start;
    const result = events.slice(start, end);
    start = end;
    return result;
  });
}

export function conversationRuns(thread: Thread | null) {
  if (!thread) return [];
  const history = (thread.run_history || []).filter((run, index, all) =>
    run.run_id !== thread.run_id && all.findIndex((item) => item.run_id === run.run_id) === index);
  const runs = history.map((run, index) => ({ ...run, current: false, label: `第 ${index + 1} 轮处理记录` }));
  if (thread.events.length || busy(thread) || thread.status === "WAITING") {
    runs.push({ run_id: thread.run_id || thread.thread_id, events: thread.events, profile: thread.run_profile, current: true, label: `第 ${runs.length + 1} 轮处理记录` });
  }
  const messages = thread.messages;
  const users = messages.map((message, index) => message.role === "user" ? index : -1).filter((index) => index >= 0);
  const anchors = runs.map((run, index) => {
    const user = messages.findIndex((message) => message.run_id === run.run_id && message.role === "user");
    if (user >= 0) return user;
    const response = messages.findIndex((message) => message.run_id === run.run_id);
    // 兼容早期未保存 run_id 的消息；不影响有明确归属的新消息。
    return response >= 0 ? users.filter((position) => position < response).at(-1) ?? response : users[index] ?? -1;
  });
  return runs.flatMap<ConversationRun>((run, index) => {
    const anchor = anchors[index];
    const end = anchors.slice(index + 1).find((position) => position > anchor) ?? messages.length;
    const inputs = anchor < 0 ? [] : messages.slice(anchor, end).filter((message) =>
      message.role === "user" && (!message.run_id || message.run_id === run.run_id));
    const responses = messages.slice(Math.max(0, anchor), end).filter((message) =>
      message.role === "assistant" && (!message.run_id || message.run_id === run.run_id));
    const responseMessageId = responses.at(-1)?.id;
    const responseParts = responses.flatMap((message) => message.parts || []);
    if (!inputs.length) return [{ ...run, id: run.run_id, continued: false, afterMessageId: messages[anchor]?.id, responseParts, responseMessageId }];
    const events = turnEvents(run.events, inputs);
    // 旧快照可能只有整段事件；不为无法还原步骤的历史输入生成空记录。
    return inputs.map((message, turn) => ({
      ...run, id: `${run.run_id}:${message.id}`, afterMessageId: message.id,
      events: events[turn], continued: turn < inputs.length - 1,
      current: run.current && turn === inputs.length - 1,
      responseParts: turn === inputs.length - 1 ? responseParts : [],
      responseMessageId: turn === inputs.length - 1 ? responseMessageId : undefined,
      requestText: inputs[0]?.text,
    })).filter((turn) => !turn.continued || turn.events.length > 0);
  }).map((run, index) => ({ ...run, label: `第 ${index + 1} 轮处理记录` }));
}

export function reportMessageId(thread: Thread | null, runId?: string) {
  if (!thread || !runId) return undefined;
  return thread.messages.filter((message) => message.run_id === runId).at(-1)?.id
    ?? thread.messages.filter((message) => message.role === "assistant").at(-1)?.id
    ?? thread.messages.at(-1)?.id;
}
