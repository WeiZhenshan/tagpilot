import { useState } from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import type { Thread, AgentMessage, RunEvent } from "./agentTypes";
import { busy, clauses, stateText, toolText } from "./agentTypes";
const convertMessage = (m: AgentMessage): ThreadMessageLike => ({
  id: m.id,
  role: m.role,
  content: [{ type: "text", text: m.text }],
  createdAt: new Date(m.created_at),
});
function Process({
  events,
  running,
  label = "处理记录",
}: {
  events: RunEvent[];
  running: boolean;
  label?: string;
}) {
  const tools = events.filter(
    (e) => e.type === "tool.started" || e.type === "tool.completed"
  );
  const understood = events.some((e) => e.type === "intent.ready");
  const lastPlan = [...events].reverse().find((e) => e.plan)?.plan;
  const bound =
    clauses(lastPlan?.tree).length > 0 &&
    clauses(lastPlan?.tree).every((c) => c.status === "BOUND");
  const validated = events.some(
    (e) => e.type === "plan.validated" && e.plan?.valid
  );
  return (
    <details className="process" open={running}>
      <summary>
        {running
          ? (events.at(-1)?.type === "run.queued" ? events.at(-1)?.message : "正在处理圈选需求")
          : `${label} · ${
              tools.filter((e) => e.type === "tool.completed").length
            } 次处理操作`}
      </summary>
      <ol className="todo-plan">
        {[
          ["理解圈选需求", understood],
          ["匹配标签与口径", bound],
          ["校验圈选方案", validated],
        ].map(([label, done]) => (
          <li key={String(label)} data-done={!!done}>
            <span className="step-marker" />
            {label}
            <small>{done ? "已完成" : running ? "待完成" : "未完成"}</small>
          </li>
        ))}
      </ol>
      <ol className="event-list">
        {events
          .filter((e) => e.message || (e.tool && toolText[e.tool]))
          .map((e) => (
            <li key={e.seq}>
              <span>{e.message || (e.tool && toolText[e.tool])}</span>
              {e.occurred_at ? (
                <time>
                  {new Date(e.occurred_at * 1000).toLocaleTimeString("zh-CN")}
                </time>
              ) : null}
              {e.candidates?.length ? (
                <small>
                  候选：{e.candidates.map((c) => c.name).join("、")}
                </small>
              ) : null}
            </li>
          ))}
      </ol>
    </details>
  );
}
function Ask({
  thread,
  pending,
  onAnswer,
}: {
  thread: Thread;
  pending: boolean;
  onAnswer: (answer: string) => void;
}) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const qs = thread.questions || [];
  return (
    <form
      className="ask-card"
      onSubmit={(e) => {
        e.preventDefault();
        onAnswer(
          qs
            .map(
              (q, i) => `${q.clause_id || ""} ${q.prompt}：${answers[i] || ""}`
            )
            .join("\n")
        );
      }}
    >
      <h3>确认业务选择后继续</h3>
      {qs.map((q, i) => (
        <fieldset key={i}>
          <legend>{q.prompt}</legend>
          {q.options?.length ? (
            <div className="ask-options">
              {q.options.map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={answers[i] === v}
                  onClick={() => setAnswers({ ...answers, [i]: v })}
                >
                  {v}
                </button>
              ))}
            </div>
          ) : null}
          <input
            aria-label={q.prompt}
            value={answers[i] || ""}
            placeholder="选择上方选项，或输入你的回答"
            onChange={(e) => setAnswers({ ...answers, [i]: e.target.value })}
          />
        </fieldset>
      ))}
      <button
        className="primary"
        disabled={pending || qs.some((_, i) => !answers[i]?.trim())}
      >
        提交并继续
      </button>
      <p>也可以直接修改右侧条件，再保存核验。</p>
    </form>
  );
}
export function AgentConversation({
  thread,
  disabled,
  pending,
  onSend,
  onCancel,
  onAnswer,
  onRetry,
}: {
  thread: Thread | null;
  disabled: boolean;
  pending: boolean;
  onSend: (text: string) => Promise<void>;
  onCancel: () => void;
  onAnswer: (text: string) => void;
  onRetry: () => void;
}) {
  const runtime = useExternalStoreRuntime<AgentMessage>({
    messages: thread?.messages || [],
    convertMessage,
    isRunning: busy(thread),
    isDisabled:
      disabled || pending || thread?.archived || thread?.status === "WAITING",
    onNew: async (message) => {
      const text = message.content
        .filter((p) => p.type === "text")
        .map((p) => ("text" in p ? p.text : ""))
        .join("\n");
      await onSend(text);
    },
    onCancel: async () => onCancel(),
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="thread">
        <div className="thread-stage">
          <ThreadPrimitive.Viewport className="thread-viewport">
            <ThreadPrimitive.Empty>
              <div className="welcome">
                <h1>找到你要经营的客户</h1>
                <p>描述客户特征，逐步核对标签与口径，形成可执行的圈选方案。</p>
                <div className="suggestions">
                  {[
                    "近30天有异名跨行转入的客户",
                    "上月借记卡消费金额超过5000元的客户",
                    "帮我梳理高价值客户的圈选口径",
                  ].map((s) => (
                    <button
                      key={s}
                      disabled={disabled || pending}
                      onClick={() => void onSend(s)}
                    >
                      {s}
                      <span aria-hidden="true">→</span>
                    </button>
                  ))}
                </div>
              </div>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages>
              {({ message }) => (
                <MessagePrimitive.Root
                  className={`message ${
                    message.role === "user" ? "user-message" : "assistant-message"
                  }`}
                >
                  <span className="speaker">
                    {message.role === "user" ? "你" : "圈选助手"}
                  </span>
                  <div className="message-text">
                    <MessagePrimitive.Parts />
                  </div>
                </MessagePrimitive.Root>
              )}
            </ThreadPrimitive.Messages>
            {thread?.run_history?.map((r, i) => (
              <Process
                key={r.run_id}
                events={r.events}
                running={false}
                label={`第 ${i + 1} 轮处理记录`}
              />
            ))}
            {thread?.events?.length ? (
              <Process events={thread.events} running={busy(thread)} />
            ) : busy(thread) ? (
              <p className="progress-text" role="status">
                正在理解你的需求…
              </p>
            ) : null}
            {thread?.status === "WAITING" ? (
              <Ask
                key={thread.interrupt_id}
                thread={thread}
                pending={pending}
                onAnswer={onAnswer}
              />
            ) : null}
            {thread && ["FAILED", "INTERRUPTED"].includes(thread.status) ? (
              <div className="run-error" role="alert">
                <strong>{stateText[thread.status]}</strong>
                <p>{thread.error || "处理位置已保存，可以继续。"}</p>
                <button disabled={pending} onClick={onRetry}>
                  从保存位置继续
                </button>
              </div>
            ) : null}
          </ThreadPrimitive.Viewport>
          <ThreadPrimitive.ScrollToBottom
            className="scroll-bottom"
            behavior="smooth"
          >
            <DownIcon />
            <span>回到最新消息</span>
          </ThreadPrimitive.ScrollToBottom>
        </div>
        <div className="composer-wrap">
          <ComposerPrimitive.Root className="composer">
            <ComposerPrimitive.Input
              className="composer-input"
              rows={2}
              placeholder={
                disabled
                  ? "请先选择标签库"
                  : thread?.status === "WAITING"
                  ? "请先回答待补充的问题"
                  : "描述客户条件，或继续修改当前方案…"
              }
            />
            <div className="composer-footer">
              <span>
                {thread
                  ? "会话自动保存"
                  : disabled
                  ? "选择标签库后开始圈选"
                  : "发送后自动保存会话"}
              </span>
              {busy(thread) ? (
                <ComposerPrimitive.Cancel className="send-button">
                  停止处理
                </ComposerPrimitive.Cancel>
              ) : (
                <ComposerPrimitive.Send
                  className="send-button"
                  aria-label="发送需求"
                >
                  发送
                </ComposerPrimitive.Send>
              )}
            </div>
          </ComposerPrimitive.Root>
          <p className="composer-note">
            条件可随时核对和修改；创建客群前会请你确认。
          </p>
        </div>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

function DownIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
