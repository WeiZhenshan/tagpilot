import { apiRequest, readAdminToken } from "./api";
import type { Thread, ThreadRow, Plan } from "./agentTypes";
const prefix = "/taglibrary/agent/threads";
async function data<T>(
  path: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  const r = await apiRequest<{ data: T }>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return r.data;
}
export const listThreads = (archived = false, page = 1) =>
  data<ThreadRow[]>(`${prefix}?archived=${archived}&page=${page}`);
export const createThread = (library_id: number) =>
  data<Thread>(prefix, "POST", { library_id });
export const getThread = (id: string) => data<Thread>(`${prefix}/${id}`);
export const changeThread = (id: string, body: unknown) =>
  data<Thread>(`${prefix}/${id}`, "PATCH", body);
export const startRun = (
  t: Thread,
  message: string,
  plan?: Plan,
  requestId = crypto.randomUUID()
) =>
  data<Thread>(`${prefix}/${t.thread_id}/runs`, "POST", {
    client_request_id: requestId,
    base_revision: t.revision,
    message,
    plan,
  });
export const resumeRun = (t: Thread, answer?: unknown) =>
  data<Thread>(`${prefix}/${t.thread_id}/resume`, "POST", {
    base_revision: t.revision,
    interrupt_id: t.interrupt_id,
    answer,
  });
export const cancelRun = (t: Thread) =>
  data<Thread>(`${prefix}/${t.thread_id}/cancel`, "POST", {});
export const countPlan = (t: Thread) =>
  data<Thread>(`${prefix}/${t.thread_id}/count`, "POST", {
    base_revision: t.revision,
    plan_hash: t.plan?.hash,
  });
export const previewPlan = (t: Thread) =>
  data<Record<string, unknown>>(`${prefix}/${t.thread_id}/preview`, "POST", {
    base_revision: t.revision,
    plan_hash: t.plan?.hash,
  });
export const createGroup = (t: Thread, name: string) =>
  data<{ group_id: number }>(`${prefix}/${t.thread_id}/create-group`, "POST", {
    base_revision: t.revision,
    plan_hash: t.plan?.hash,
    name,
  });
export const groupStatus = (t: Thread) =>
  data<{ group_id?: number; status?: string }>(
    `${prefix}/${t.thread_id}/execution`
  );
// 有界 SSE 响应；断线后按持久会话重新订阅，不重发模型请求。
export async function readUpdates(
  id: string,
  signal: AbortSignal
): Promise<Thread> {
  const token = readAdminToken();
  const r = await fetch(`/dev-api${prefix}/${id}/events`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  const text = await r.text();
  if (readAdminToken() !== token) {
    window.dispatchEvent(new Event("tagpilot-agent:session-changed"));
    throw new Error("登录用户已变更");
  }
  if (!r.ok) throw new Error("连接中断，请重试");
  const line = text.split("\n").find((v) => v.startsWith("data: "));
  if (!line) {
    let msg = "无法恢复会话";
    try {
      msg = JSON.parse(text).msg || msg;
    } catch {}
    throw new Error(msg);
  }
  return JSON.parse(line.slice(6)) as Thread;
}
