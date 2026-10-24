import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import type { Thread, AgentMessage, ContextTag } from "./agentTypes";
import { TagChips } from "./TagTree";
import { busy, clauses, stateText, degradedOf, degradedMessage, degradedText, runNotice } from "./agentTypes";
import { slashQuery, type AgentSkill } from "./skillApi";
import { RunTimeline } from "./RunTimeline.tsx";
import { stagedQuestions } from "./clarification";
import { conversationRuns, reportMessageId } from "./conversationRuns";
import { AnalysisMessageParts } from "./insight/AnalysisMessageParts";
import type { ArtifactReference } from "./insight/analysisTypes";
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
  onCancel,
}: {
  thread: Thread;
  pending: boolean;
  onAnswer: (answer: string) => void;
  onCancel: () => void;
}) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const qs = stagedQuestions(thread.questions || []);
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
      {qs.length < (thread.questions || []).length ? <p>先确认采用的指标，再选择该指标对应的档位或阈值。</p> : null}
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
      <div className="ask-actions">
        <button
          className="primary"
          disabled={pending || qs.some((_, i) => !answers[i]?.trim())}
        >
          提交并继续
        </button>
        <button type="button" className="text-button" disabled={pending} onClick={onCancel}>
          停止处理
        </button>
      </div>
      <p>也可以直接修改右侧条件，再保存核验。</p>
    </form>
  );
}
export function AgentConversation({
  thread,
  disabled,
  pending,
  contextControl,
  skills = [], skillsLoading = false, skillsError = "", onRefreshSkills, selectedSkill, onSelectSkill, onManageSkills, skillContext,
  skillChips,
  skillRunDisabled = false,
  insightSummary,
  insightRunId,
  composerRequest,
  contextTags = [],
  onRemoveContextTag,
  onSend,
  onCancel,
  onAnswer,
  onRetry,
  onEdit,
  onReveal,
  analysisTarget,
  onRemoveAnalysisTarget,
  onContinueAnalysis,
}: {
  thread: Thread | null;
  disabled: boolean;
  pending: boolean;
  contextControl?: ReactNode;
  skills?: AgentSkill[];
  skillsLoading?: boolean;
  skillsError?: string;
  onRefreshSkills?: () => void;
  selectedSkill?: AgentSkill | null;
  onSelectSkill?: (skill: AgentSkill | null) => void;
  onManageSkills?: () => void;
  skillContext?: string;
  skillChips?: ReactNode;
  skillRunDisabled?: boolean;
  insightSummary?: ReactNode;
  insightRunId?: string;
  composerRequest?: { text: string; id: number; focusOnly?: boolean };
  contextTags?: ContextTag[];
  onRemoveContextTag?: (id: number) => void;
  onSend: (text: string) => Promise<boolean>;
  onCancel: () => void;
  onAnswer: (text: string) => void;
  onRetry: () => void;
  onEdit: () => void;
  onReveal: (ids: string[]) => void;
  analysisTarget?: ArtifactReference | null;
  onRemoveAnalysisTarget?: () => void;
  onContinueAnalysis?: (target: ArtifactReference, text?: string) => void;
}) {
  const [slash, setSlash] = useState<ReturnType<typeof slashQuery>>(null);
  const [activeSkill, setActiveSkill] = useState(0);
  const filteredSkills = skills.filter((s) => !slash?.query || `${s.name} ${s.display_name} ${s.description}`.toLowerCase().includes(slash.query));
  useEffect(() => {
    if (slash && filteredSkills.length) document.getElementById(`composer-skill-${Math.min(activeSkill, filteredSkills.length - 1)}`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeSkill, slash?.query, filteredSkills.length]);
  const degraded = degradedOf(thread);
  const runs = conversationRuns(thread);
  const summaryMessage = reportMessageId(thread, insightRunId);
  const renderRun = (run: ReturnType<typeof conversationRuns>[number]) => (
    <RunTimeline key={run.id} runId={run.id} skillMode={run.profile === "skill" || run.profile === "conversation"}
      events={run.events} running={run.current && busy(thread)} continued={run.continued} label={run.label}
      plan={run.current ? thread?.live_plan || thread?.plan : undefined}
      status={run.current ? thread?.status : undefined} questions={run.current ? thread?.questions : undefined} onReveal={onReveal}>
      {run.current && thread?.status === "WAITING" ? <Ask key={thread.interrupt_id} thread={thread} pending={pending} onAnswer={onAnswer} onCancel={onCancel} /> : null}
    </RunTimeline>
  );
  const composerInput = useRef<HTMLTextAreaElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const scrollThread = useRef<string | undefined>(undefined);
  const [atBottom, setAtBottom] = useState(true);
  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element) return;
    if (scrollThread.current !== thread?.thread_id) {
      scrollThread.current = thread?.thread_id; followLatest.current = true;
    }
    const nearBottom = () => element.scrollHeight - element.clientHeight - element.scrollTop < 8;
    // 用户上翻后立即取消跟随；新图表载入和内容扩高只能在仍跟随时调整滚动。
    const onScroll = () => { followLatest.current = nearBottom(); setAtBottom(nearBottom()); };
    const onResize = () => {
      if (followLatest.current) element.scrollTop = element.scrollHeight;
      setAtBottom(nearBottom());
    };
    element.addEventListener("scroll", onScroll, { passive: true });
    const observer = new ResizeObserver(onResize); observer.observe(element);
    for (const child of element.children) observer.observe(child);
    onResize();
    return () => { element.removeEventListener("scroll", onScroll); observer.disconnect(); };
  }, [thread?.thread_id, thread?.messages]);
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
      setSlash(null);
      const sent = await onSend(text);
      if (!sent) runtime.thread.composer.setText(text);
    },
    onCancel: async () => onCancel(),
  });
  useEffect(() => {
    if (!composerRequest) return;
    if (thread?.status === "WAITING") {
      document.querySelector<HTMLElement>(".ask-card button:not(:disabled), .ask-card input:not(:disabled)")?.focus();
      return;
    }
    if (!composerRequest.focusOnly) {
      runtime.thread.composer.setText(composerRequest.text);
      const query = slashQuery(composerRequest.text, composerRequest.text.length);
      setSlash(query);setActiveSkill(0);if(query) onRefreshSkills?.();
    }
    composerInput.current?.focus();
    // 只响应右栏发起的一次预填请求，避免轮询刷新覆盖用户后续输入。
  }, [composerRequest]);
  function pickSkill(skill: AgentSkill) {
    if (!slash || !onSelectSkill) return;
    const text = runtime.thread.composer.getState().text;
    runtime.thread.composer.setText(text.slice(0, slash.start) + text.slice(slash.end));
    onSelectSkill(skill);setSlash(null);
    composerInput.current?.focus();
  }
  useEffect(() => { setSlash(null);setActiveSkill(0); }, [thread?.thread_id]);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => { if (!(event.target as Element).closest(".composer-wrap")) setSlash(null); };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="thread">
        <div className="thread-stage">
          <ThreadPrimitive.Viewport ref={viewport} className="thread-viewport" autoScroll={false} scrollToBottomOnInitialize={false} scrollToBottomOnThreadSwitch={false} scrollToBottomOnRunStart={false}>
            <ThreadPrimitive.Empty>
              <div className="welcome">
                <h1>找到客户，也看懂客户</h1>
                <p>描述圈选条件，或直接提出分析问题。图表和发现会出现在对话中。</p>
                <div className="suggestions">
                  {[
                    "近30天有异名跨行转入的客户",
                    "上月借记卡消费金额超过5000元的客户",
                    "帮我梳理高价值客户的圈选口径",
                    "分析当前授权范围内客户的资产结构",
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
                <div className="conversation-turn" data-message-id={message.id}>
                <MessagePrimitive.Root
                  className={`message ${
                    message.role === "user" ? "user-message" : "assistant-message"
                  }`}
                >
                  <span className="speaker">
                    {message.role === "user" ? "你" : "TagPilot"}
                  </span>
                  {thread?.messages.find((m) => m.id === message.id)?.context_tags?.length ? <TagChips tags={thread.messages.find((m) => m.id === message.id)!.context_tags!} /> : null}
                  <div className="message-text">
                    <MessagePrimitive.Parts />
                  </div>
                  {thread?.messages.find((m) => m.id === message.id)?.parts?.length ? <AnalysisMessageParts
                    parts={thread.messages.find((m) => m.id === message.id)!.parts!} artifacts={thread.analysis_artifacts} revision={thread.revision}
                    disabled={disabled || pending || busy(thread)} onContinue={(target, text) => onContinueAnalysis?.(target, text)} onAnswer={(text) => { void onSend(text); }} /> : null}
                </MessagePrimitive.Root>
                {runs.filter((run) => run.afterMessageId === message.id).map(renderRun)}
                {summaryMessage === message.id && !thread?.messages.find((m) => m.id === message.id)?.parts?.length ? insightSummary : null}
                </div>
              )}
            </ThreadPrimitive.Messages>
            {runs.filter((run) => !run.afterMessageId).map(renderRun)}
            {!summaryMessage ? insightSummary : null}
            {thread && runNotice(thread) === "partial" && degraded ? (
              <div className="run-degraded" role="status">
                <strong>{degraded.kept_clauses.length ? `已保留 ${degraded.kept_clauses.length}/${clauses(thread.plan?.tree).length} 项条件` : "尚未形成可用条件"}</strong>
                <p>{degradedMessage(degraded)}</p>
                {degraded.level === "L3" && clauses(thread.plan?.tree).some((c) => c.candidates?.length) ? <p>已找到可能相关的标签，请在方案中选择并核验。</p> : null}
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
                  {thread.run_profile === "skill" ? "重新选择技能" : degraded ? "稍后重试" : "从保存位置继续"}
                </button> : null}
              </div>
            ) : null}
          </ThreadPrimitive.Viewport>
          <button type="button" aria-label="回到最新消息" disabled={atBottom} onClick={() => {
            followLatest.current = true;
            viewport.current?.scrollTo({ top: viewport.current.scrollHeight, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
          }}
            className="scroll-bottom"
          >
            <DownIcon />
            <span>回到最新消息</span>
          </button>
        </div>
        <div className="composer-wrap">
          {analysisTarget && <div className="analysis-reference"><span>继续分析：{analysisTarget.title || "已选图表"}</span><button type="button" onClick={onRemoveAnalysisTarget}>移除引用</button></div>}
          {slash ? <div className="skill-menu" aria-label="选择技能">
            <div className="skill-menu-heading"><strong>调用技能</strong><button type="button" className="text-button" onClick={onManageSkills}>管理技能</button></div>
            <p className="skill-menu-context">{skillContext}</p>
            {skillsLoading ? <p role="status" className="skill-menu-empty">正在加载技能…</p> : skillsError ? <div className="skill-menu-empty" role="alert">{skillsError}<button type="button" onClick={onRefreshSkills}>重新加载</button></div> : filteredSkills.length ? <div id="composer-skills" role="listbox" aria-label="已发布技能" className="skill-menu-list">
              {filteredSkills.map((skill, index) => <button id={`composer-skill-${index}`} type="button" role="option" aria-selected={activeSkill === index} className="skill-menu-option" key={skill.name} onPointerMove={() => setActiveSkill(index)} onClick={() => pickSkill(skill)}>
                <span><strong>{skill.display_name}</strong><small>/{skill.name}</small></span><p>{skill.description}</p>{skill.argument_hint ? <small>{skill.argument_hint}</small> : null}
              </button>)}
            </div> : <p className="skill-menu-empty">{skills.length ? "没有匹配的技能，请调整搜索词。" : thread?.capabilities.insight ? "暂无已发布的可调用技能，请先到洞察技能页面登记并发布。" : "请先进入客群会话，并确认技能运行权限。"}</p>}
            <p className="skill-menu-hint">↑ ↓ 选择 · Enter 添加 · Esc 关闭</p>
          </div> : null}
          <ComposerPrimitive.Root className="composer" onKeyDownCapture={(event) => {
            if (selectedSkill && !slash && event.target === composerInput.current && event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();event.stopPropagation();
              if (!disabled && !pending && !skillRunDisabled) void onSend(runtime.thread.composer.getState().text).then((sent) => { if(sent) runtime.thread.composer.setText(""); });
            }
          }}>
            {skillChips}
            {contextTags.length ? <div className="composer-tags"><TagChips tags={contextTags} onRemove={onRemoveContextTag} /></div> : null}
            <ComposerPrimitive.Input
              ref={composerInput}
              className="composer-input"
              rows={2}
              aria-label="圈选需求或技能调用"
              aria-haspopup="listbox"
              aria-expanded={!!slash}
              aria-controls={slash && filteredSkills.length ? "composer-skills" : undefined}
              aria-activedescendant={slash && filteredSkills.length ? `composer-skill-${Math.min(activeSkill, filteredSkills.length - 1)}` : undefined}
              onChange={(event) => {
                const next = slashQuery(event.currentTarget.value, event.currentTarget.selectionStart);
                if (next && !slash) onRefreshSkills?.();
                setSlash(next);setActiveSkill(0);
              }}
              onKeyDownCapture={(event) => {
                if (!slash || event.nativeEvent.isComposing) return;
                if (event.key === "Escape") { event.preventDefault();event.stopPropagation();setSlash(null); }
                else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                  event.preventDefault();event.stopPropagation();setActiveSkill((index) => (index + (event.key === "ArrowDown" ? 1 : -1) + Math.max(1,filteredSkills.length)) % Math.max(1,filteredSkills.length));
                } else if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();event.stopPropagation();if (filteredSkills.length) pickSkill(filteredSkills[Math.min(activeSkill,filteredSkills.length-1)]);
                }
              }}
              placeholder={
                thread?.archived ? "会话已归档，请先恢复"
                  : disabled ? "请先选择标签库"
                  : thread?.status === "WAITING"
                  ? "请先回答待补充的问题"
                  : selectedSkill ? `补充${selectedSkill.display_name}的分析目标，或直接发送运行…` : "描述客户条件，或直接提问、分析与改图…"
              }
            />
            <div className="composer-footer">
              {contextControl ? (
                <div className="composer-context">{contextControl}</div>
              ) : null}
              {thread || !disabled ? (
                <span className="composer-hint">
                  {selectedSkill ? "携带当前客群上下文" : "直接对话分析 · / 选择技能"}
                </span>
              ) : null}
              {busy(thread) ? (
                <ComposerPrimitive.Cancel className="send-button">
                  停止处理
                </ComposerPrimitive.Cancel>
              ) : thread?.status === "WAITING" ? (
                <button type="button" className="send-button" disabled={pending} onClick={onCancel}>
                  停止处理
                </button>
              ) : contextTags.length || skillChips ? (
                <button className="send-button" type="button" aria-label="发送需求" disabled={disabled || pending || (!!skillChips && skillRunDisabled)} onClick={() => {
                  const text = runtime.thread.composer.getState().text;
                  void onSend(text).then((sent) => { if (sent) runtime.thread.composer.setText(""); });
                }}>发送</button>
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
            条件可随时核对和修改；技能分析使用当前客群，创建前会请你确认。
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
