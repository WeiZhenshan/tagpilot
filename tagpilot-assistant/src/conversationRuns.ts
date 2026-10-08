import { busy, type Thread } from "./agentTypes";

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
  return runs.map((run, index) => {
    let anchor = anchors[index];
    const end = anchors.slice(index + 1).find((position) => position > anchor) ?? messages.length;
    // 同一次运行的业务补充属于本轮，记录跟随最后一次补充，仍在答复之前。
    for (let position = anchor + 1; anchor >= 0 && position < end; position++) {
      const message = messages[position];
      if (message.role === "assistant") break;
      if (message.role === "user" && (!message.run_id || message.run_id === run.run_id)) anchor = position;
    }
    return { ...run, afterMessageId: messages[anchor]?.id };
  });
}

export function reportMessageId(thread: Thread | null, runId?: string) {
  if (!thread || !runId) return undefined;
  return thread.messages.filter((message) => message.run_id === runId).at(-1)?.id
    ?? thread.messages.filter((message) => message.role === "assistant").at(-1)?.id
    ?? thread.messages.at(-1)?.id;
}
