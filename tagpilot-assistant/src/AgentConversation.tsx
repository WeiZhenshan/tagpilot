import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import type { Thread, AgentMessage } from "./agentTypes";
import { busy, clauses, stateText, degradedOf, degradedText, runNotice } from "./agentTypes";
import { RunTimeline } from "./RunTimeline.tsx";
const convertMessage = (m: AgentMessage): ThreadMessageLike => ({
  id: m.id,
  role: m.role,
  content: [{ type: "text", text: m.text }],
  createdAt: new Date(m.created_at),
});
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
  contextControl,
  composerRequest,
  onSend,
  onCancel,
  onAnswer,
  onRetry,
  onEdit,
  onReveal,
}: {
  thread: Thread | null;
  disabled: boolean;
  pending: boolean;
  contextControl?: ReactNode;
  composerRequest?: { text: string; id: number };
  onSend: (text: string) => Promise<void>;
  onCancel: () => void;
  onAnswer: (text: string) => void;
  onRetry: () => void;
  onEdit: () => void;
  onReveal: (ids: string[]) => void;
}) {
  const degraded = degradedOf(thread);
  const composerInput = useRef<HTMLTextAreaElement>(null);
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
  useEffect(() => {
    if (!composerRequest) return;
    if (thread?.status === "WAITING") {
      document.querySelector<HTMLElement>(".ask-card button:not(:disabled), .ask-card input:not(:disabled)")?.focus();
      return;
    }
    runtime.thread.composer.setText(composerRequest.text);
    composerInput.current?.focus();
    // 只响应右栏发起的一次预填请求，避免轮询刷新覆盖用户后续输入。
  }, [composerRequest]);
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
              <RunTimeline key={r.run_id} runId={r.run_id} events={r.events} running={false} label={`第 ${i + 1} 轮处理记录`} onReveal={onReveal} />
            ))}
            {thread && (thread.events.length || busy(thread) || thread.status === "WAITING") ? (
              <RunTimeline key={`${thread.thread_id}:${thread.run_id || "current"}`} runId={thread.run_id || thread.thread_id}
                events={thread.events} running={busy(thread)} plan={thread.live_plan || thread.plan}
                status={thread.status} questions={thread.questions} onReveal={onReveal}>
                {thread.status === "WAITING" ? <Ask key={thread.interrupt_id} thread={thread} pending={pending} onAnswer={onAnswer} /> : null}
              </RunTimeline>
            ) : null}
            {thread && runNotice(thread) === "partial" && degraded ? (
              <div className="run-degraded" role="status">
                <strong>已保留 {degraded.kept_clauses.length}/{clauses(thread.plan?.tree).length} 项条件</strong>
                <p>{degraded.user_message || degradedText[degraded.reason]}</p>
                {degraded.level === "L3" ? <p>已找到可能相关的标签，请在方案中选择并核验。</p> : null}
                <div className="degraded-actions">
                  {degraded.resumable ? <button disabled={disabled || pending} onClick={() => void onSend("请继续补全尚未确定的条件")}>补全剩余条件</button> : null}
                  <button disabled={disabled || pending} onClick={onEdit}>手工编辑方案</button>
                </div>
              </div>
            ) : null}
            {thread && runNotice(thread) === "failure" ? (
              <div className="run-error" role="alert">
                <strong>{stateText[thread.status]}</strong>
                <p>{degraded?.user_message || thread.error || (degraded ? degradedText[degraded.reason] : "处理位置已保存，可以继续。")}</p>
                {!degraded || degraded.resumable ? <button disabled={disabled || pending} onClick={onRetry}>
                  {degraded ? "稍后重试" : "从保存位置继续"}
                </button> : null}
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
              ref={composerInput}
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
              {contextControl ? (
                <div className="composer-context">{contextControl}</div>
              ) : null}
              {thread || !disabled ? (
                <span className="composer-hint">
                  {thread ? "会话自动保存" : "发送后自动保存会话"}
                </span>
              ) : null}
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
