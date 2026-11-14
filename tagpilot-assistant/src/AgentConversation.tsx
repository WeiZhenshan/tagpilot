import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  AssistantRuntimeProvider,
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
import { analysisLimitation, artifactFor } from "./insight/analysisTypes";
import { AnalysisMessageParts } from "./insight/AnalysisMessageParts";
import type { ArtifactReference } from "./insight/analysisTypes";
import { InlinePlanCard } from "./InlinePlanCard";
import type { PlanDraft } from "./usePlanDraft";
import { ActionIcon } from "./ActionIcon";
import { Presence } from "./Presence";
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
type ComposerDraft = { text: string; quote?: string };
const emptyDraft: ComposerDraft = { text: "" };
const planReadyReply = "圈选方案已生成，可以核对条件并统计人数。";
const suggestions = [
  { label: "圈选客户", examples: ["近期资金流入客户", "高消费客户", "高价值客户"] },
  { label: "分析客户", examples: ["分析客户资产结构"] },
];

function SpeakerIcon({ user }: { user: boolean }) {
  return <span className={`speaker-icon ${user ? "speaker-icon--user" : "speaker-icon--assistant"}`} role="img" aria-label={user ? "你" : "TagPilot"}>
    {user ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>
      : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="7" width="16" height="13" rx="4" /><path d="M12 7V4m-2 0h4M2 12h2m16 0h2M8.5 12h.01m7 0h.01M9 16h6" strokeWidth="2" /></svg>}
  </span>;
}

export function AgentConversation({
  thread,
  disabled,
  pending,
  contextControl,
  draftKey,
  planDraft, savingPlan, planError, onSavePlan,
  resultOperation,
  skills = [], skillsLoading = false, skillsError = "", onRefreshSkills, selectedSkill, onSelectSkill, onManageSkills, skillContext,
  skillChips,
  skillRunDisabled = false,
  insightSummary,
  insightRunId,
  composerRequest,
  composerPulse,
  contextTags = [],
  onRemoveContextTag,
  onSend,
  onCancel,
  onAnswer,
  onRetry,
  onRestart,
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
  draftKey: string;
  planDraft: PlanDraft;
  savingPlan: boolean;
  planError?: string;
  onSavePlan: () => void;
  resultOperation?: "count" | "save";
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
  composerRequest?: { text: string; id: number; focusOnly?: boolean; openSkills?: boolean };
  composerPulse?: number;
  contextTags?: ContextTag[];
  onRemoveContextTag?: (id: number) => void;
  onSend: (text: string) => Promise<boolean>;
  onCancel: () => void;
  onAnswer: (text: string) => void;
  onRetry: () => void;
  onRestart: (text: string) => void;
  onEdit: () => void;
  onReveal: (ids: string[]) => void;
  analysisTarget?: ArtifactReference | null;
  onRemoveAnalysisTarget?: () => void;
  onContinueAnalysis?: (target: ArtifactReference, text?: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, ComposerDraft>>({});
  const draft = drafts[draftKey] ?? emptyDraft;
  const setDraft = (value: ComposerDraft) => setDrafts((previous) => ({ ...previous, [draftKey]: value }));
  const [skillPicker, setSkillPicker] = useState(false);
  const [slash, setSlash] = useState<ReturnType<typeof slashQuery>>(null);
  const [activeSkill, setActiveSkill] = useState(0);
  const [citeSelected, setCiteSelected] = useState(false);
  const [sending, setSending] = useState<{ text: string; id: number } | null>(null);
  const [copyResult, setCopyResult] = useState<{ id: string; ok: boolean } | null>(null);
  const citeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!copyResult) return;
    const timer = window.setTimeout(() => setCopyResult(null), 1800);
    return () => window.clearTimeout(timer);
  }, [copyResult]);
  const copyMessage = async (id: string, text: string) => {
    try { await navigator.clipboard.writeText(text); setCopyResult({ id, ok: true }); } catch { setCopyResult({ id, ok: false }); }
  };
  const skillMenuOpen = skillPicker || !!slash;
  const filteredSkills = skills.filter((s) => !slash?.query || `${s.name} ${s.display_name} ${s.description}`.toLowerCase().includes(slash.query));
  useEffect(() => {
    if (skillMenuOpen && filteredSkills.length) document.getElementById(`composer-skill-${Math.min(activeSkill, filteredSkills.length - 1)}`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeSkill, skillMenuOpen, slash?.query, filteredSkills.length]);
  const degraded = degradedOf(thread);
  const runs = conversationRuns(thread);
  const editableReply = thread?.plan?.valid ? thread.messages.slice().reverse().find((message) =>
    message.role === "assistant" && message.revision === thread.revision && message.text?.trim() === planReadyReply)?.id : undefined;
  const summaryMessage = reportMessageId(thread, insightRunId);
  const stoppedRun = thread?.status === "CANCELLED" ? runs.find((run) => run.current) : undefined;
  const stoppedQuestions = stoppedRun ? thread?.stopped_questions
    ?? (stoppedRun.events.some((event) => event.type === "run.waiting") ? thread?.clarification_state?.pending_questions : undefined) ?? [] : [];
  const stoppedRequest = stoppedRun?.requestText;
  const stoppedFollowUp = stoppedRequest ? <div className="stopped-run" role="status">
    <strong>本轮已停止</strong>
    {stoppedQuestions.length ? <><p>停止前待确认</p><ul>{stoppedQuestions.map((question, index) => <li key={index}>{question.prompt}</li>)}</ul></> : null}
    <button type="button" disabled={disabled || pending} onClick={() => onRestart(stoppedRequest)}>重新发起本轮</button>
  </div> : null;
  const renderRun = (run: ReturnType<typeof conversationRuns>[number]) => {
    const validated = [...run.events].reverse().find((event) => event.type === "plan.validated");
    const isPlan = run.profile === "audience" || !!validated || run.events.some((event) => event.type === "plan.observed" || (event.type === "intent.ready" && !!event.plan));
    const report = thread?.skill_report?.run_id === run.run_id ? thread.skill_report : undefined;
    const limited = analysisLimitation(run.responseParts) || report?.results.some((result) => result.status !== "COMPLETE");
    const reply = thread?.messages.find((message) => message.id === run.responseMessageId);
    const currentResult = isPlan && !planDraft.dirty && !run.continued && !!thread?.plan?.valid &&
      (reply?.revision === thread.revision || (reply?.revision === undefined && run.current && !!validated));
    const count = currentResult && thread.count?.revision === thread.revision
      && (!thread.count.plan_hash || thread.count.plan_hash === thread.plan?.hash) ? thread.count.value : undefined;
    const resultReport = thread?.skill_report ?? thread?.insight_report;
    const hasCurrentReport = currentResult && resultReport?.cohort.revision === thread.revision && resultReport.cohort.plan_hash === thread.plan?.hash;
    const resultParts = currentResult ? thread.messages.slice().reverse().find((message) =>
      message.role === "assistant" && message.parts?.length && (
        message.revision === thread.revision || message.parts.some((part) => {
          if (part.type !== "chart" && part.type !== "table") return false;
          const artifact = artifactFor(thread.analysis_artifacts, part.artifact_id, part.artifact_version);
          return artifact?.base_revision === thread.revision && (!artifact.base_plan_hash || artifact.base_plan_hash === thread.plan?.hash);
        })
      ))?.parts : undefined;
    const analysisLimited = !!analysisLimitation(resultParts) || !!(hasCurrentReport && resultReport.results.every((result) => result.status !== "COMPLETE"));
    const completionLabel = limited ? "分析受限"
      : run.responseParts.some((part) => part.type === "clarification") ? "已提出补充问题"
      : validated?.plan?.valid || (currentResult && reply?.text?.trim() === planReadyReply) ? "已生成圈选方案"
      : isPlan ? "已整理圈选条件"
      : run.profile === "conversation" ? run.responseParts.length ? "分析结果已生成" : "已回复"
      : undefined;
    return <RunTimeline key={run.id} runId={run.id} skillMode={run.profile === "skill" || (run.profile === "conversation" && !isPlan)}
      completionLabel={completionLabel}
      results={currentResult ? { count, counting: resultOperation === "count", saving: resultOperation === "save",
        saved: thread.execution?.revision === thread.revision,
        insights: !analysisLimited && (hasCurrentReport || !!resultParts?.some((part) => part.type === "chart" || part.type === "table")),
        limited: analysisLimited } : undefined}
      events={run.events} running={run.current && busy(thread)} continued={run.continued} label={run.label}
      plan={run.current ? thread?.live_plan || thread?.plan : undefined}
      status={run.current ? thread?.status : undefined} questions={run.current ? thread?.questions : undefined} onReveal={onReveal}
      followUp={run === stoppedRun && !stoppedRun.responseMessageId ? stoppedFollowUp : null}>
      {run.current && thread ? <Presence open={thread.status === "WAITING"}>
        <Ask key={thread.interrupt_id} thread={thread} pending={pending} onAnswer={onAnswer} onCancel={onCancel} />
      </Presence> : null}
    </RunTimeline>;
  };
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
  const submit = async (text: string) => {
    const ghost = text.trim()
      ? text
      : selectedSkill
      ? `运行${selectedSkill.display_name}`
      : contextTags.length
      ? `已选择 ${contextTags.length} 个标签作为圈选上下文`
      : "发送中…";
    setSending({ text: ghost, id: Date.now() });
    try {
      return await onSend(text);
    } finally {
      setSending(null);
    }
  };
  const runtime = useExternalStoreRuntime<AgentMessage>({
    messages: thread?.messages || [],
    convertMessage,
    isRunning: busy(thread),
    isDisabled: disabled || pending || thread?.status === "WAITING",
    onNew: async (message) => {
      await submit(message.content.flatMap((part) => part.type === "text" ? [part.text] : []).join("\n"));
    },
  });
  const composerDisabled = disabled || pending || busy(thread) || thread?.status === "WAITING";
  const canSend = !composerDisabled && !skillMenuOpen && !planDraft.dirty
    && !!draft.text.trim() && (!selectedSkill || !skillRunDisabled);
  const sendDraft = async () => {
    if (!canSend || sending) return;
    const text = draft.quote ? `${draft.text.trim()}

引用消息：
${draft.quote}` : draft.text;
    const sent = await submit(text);
    if (sent) setDraft(emptyDraft);
  };
  const closeSkills = () => { setSlash(null); setSkillPicker(false); };
  const openSkills = () => {
    setSlash(null); setSkillPicker(true); setActiveSkill(0);
    onRefreshSkills?.();
    composerInput.current?.focus();
  };
  function fillComposer(text: string) {
    if (text && text !== draft.text) setDraft({ ...draft, text: draft.text ? `${draft.text}
${text}` : text });
    composerInput.current?.focus();
  }
  useEffect(() => {
    if (!composerRequest) return;
    if (thread?.status === "WAITING") {
      document.querySelector<HTMLElement>(".ask-card button:not(:disabled), .ask-card input:not(:disabled)")?.focus();
      return;
    }
    fillComposer(composerRequest.focusOnly ? "" : composerRequest.text);
    if (composerRequest.openSkills) openSkills();
    // 只响应一次预填请求，避免轮询刷新改写用户输入。
  }, [composerRequest]);
  function pickSkill(skill: AgentSkill) {
    if (!onSelectSkill) return;
    if (slash) setDraft({ ...draft, text: draft.text.slice(0, slash.start) + draft.text.slice(slash.end) });
    onSelectSkill(skill); closeSkills();
    composerInput.current?.focus();
  }
  useLayoutEffect(() => { closeSkills(); setActiveSkill(0); }, [draftKey]);
  useEffect(() => { setCiteSelected(false); }, [analysisTarget?.target_artifact_id, analysisTarget?.target_artifact_version]);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => { if (!(event.target as Element).closest(".composer-wrap")) closeSkills(); };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  function removeAnalysisCite() {
    onRemoveAnalysisTarget?.();
    setCiteSelected(false);
    requestAnimationFrame(() => composerInput.current?.focus());
  }
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="thread">
        <div className="thread-stage">
          <ThreadPrimitive.Viewport ref={viewport} className="thread-viewport" autoScroll={false} scrollToBottomOnInitialize={false} scrollToBottomOnThreadSwitch={false} scrollToBottomOnRunStart={false}>
            <ThreadPrimitive.Empty>
              <div className="welcome">
                <h2>找到客户，也看懂客户</h2>
                <p>描述圈选条件，或直接提出分析问题。图表和发现会出现在对话中。</p>
                <div className="suggestions">
                  {suggestions.map(({ label, examples }) => <section key={label} aria-label={label}>
                    <h2>{label}</h2>
                    {examples.map((example) => <button type="button" key={example} disabled={disabled || pending}
                      onClick={() => fillComposer(example)}>{example}<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" /></svg></button>)}
                  </section>)}
                </div>
              </div>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages>
              {({ message }) => {
                const source = thread?.messages.find((m) => m.id === message.id);
                // assistant-ui 会在运行中合成一条尚无内容的助手消息；处理记录负责展示进度。
                if (!source) return null;
                const sourceIndex = thread!.messages.findIndex((item) => item.id === source.id);
                const hasLaterUser = thread!.messages.slice(sourceIndex + 1).some((item) => item.role === "user");
                if (source.role === "assistant" && busy(thread) && !hasLaterUser &&
                  (!source.run_id || source.run_id === thread?.run_id)) return null;
                const precedingUser = thread!.messages.slice(0, sourceIndex).reverse().find((item) => item.role === "user");
                const followsRun = source.role === "assistant" && !!precedingUser && runs.some((run) => run.afterMessageId === precedingUser.id);
                const text = source?.text?.trim();
                const planReply = source?.role === "assistant" && text === planReadyReply;
                const savedPlan = planReply && source.revision !== undefined
                  ? (source.revision === thread?.revision ? thread.plan : thread?.versions.find((plan) => plan.revision === source.revision))
                  : undefined;
                const observedPlan = planReply && !savedPlan
                  ? runs.find((run) => run.responseMessageId === source.id)?.events.slice().reverse().find((event) => event.type === "plan.validated" && event.plan?.valid)?.plan
                  : undefined;
                return (
                <div className="conversation-turn" data-message-id={message.id}>
                <MessagePrimitive.Root
                  className={`message ${
                    message.role === "user" ? "user-message" : "assistant-message"
                  }`}
                >
                  <span className="speaker">
                    {!followsRun ? <SpeakerIcon user={message.role === "user"} /> : null}
                    {text ? <span className="message-actions">
                      <button type="button" aria-label="复制" title="复制消息" onClick={() => void copyMessage(message.id, text)}>
                        <ActionIcon kind="copy" />
                      </button>
                      <button type="button" disabled={composerDisabled} onClick={() => { setDraft({ ...draft, quote: text }); composerInput.current?.focus(); }} aria-label="引用" title="引用到输入框"><ActionIcon kind="quote" /></button>
                    </span> : null}
                  </span>
                  {copyResult?.id === message.id ? <span className="message-copy-result" role="status">{copyResult.ok ? "已复制消息" : "复制失败，请重试"}</span> : null}
                  {source?.context_tags?.length ? <TagChips tags={source.context_tags} /> : null}
                  {planReply ? <InlinePlanCard plan={savedPlan ?? observedPlan} editor={source.id === editableReply ? {
                    draft: planDraft,
                    disabled: composerDisabled || savingPlan,
                    saving: savingPlan,
                    error: planError,
                    onSave: onSavePlan,
                    onOpenResults: () => onReveal([]),
                  } : undefined} /> : <div className="message-text"><MessagePrimitive.Parts /></div>}
                  {source?.parts?.length ? <AnalysisMessageParts
                    parts={source.parts} artifacts={thread!.analysis_artifacts} revision={thread!.revision}
                    disabled={disabled || pending || busy(thread) || planDraft.dirty} onContinue={(target, text) => onContinueAnalysis?.(target, text)} onAdjust={() => composerInput.current?.focus()} onAnswer={(text) => { void submit(text); }} /> : null}
                </MessagePrimitive.Root>
                {runs.filter((run) => run.afterMessageId === message.id).map((run) => <div className="bot-run" key={run.id}>
                  <span className="speaker"><SpeakerIcon user={false} /></span>
                  {renderRun(run)}
                </div>)}
                {summaryMessage === message.id && !source?.parts?.length ? insightSummary : null}
                {stoppedRun?.responseMessageId === message.id ? stoppedFollowUp : null}
                </div>
                );
              }}
            </ThreadPrimitive.Messages>
            {runs.filter((run) => !run.afterMessageId).map((run) => <div className="bot-run" key={run.id}><span className="speaker"><SpeakerIcon user={false} /></span>{renderRun(run)}</div>)}
            {!summaryMessage ? insightSummary : null}
            {sending ? (
              <div className="conversation-turn" data-ghost="true" aria-busy="true">
                <div className="message user-message is-pending">
                  <span className="speaker"><SpeakerIcon user /><span>发送中</span></span>
                  <div className="message-text">{sending.text}</div>
                </div>
              </div>
            ) : null}
            {thread && runNotice(thread) === "partial" && degraded ? (
              <div className="run-degraded" role="status">
                <strong>{degraded.kept_clauses.length ? `已保留 ${degraded.kept_clauses.length}/${clauses(thread.plan?.tree).length} 项条件` : "尚未形成可用条件"}</strong>
                <p>{degradedMessage(degraded)}</p>
                {degraded.level === "L3" && clauses(thread.plan?.tree).some((c) => c.candidates?.length) ? <p>已找到可能相关的标签，请在方案中选择并核验。</p> : null}
                <div className="degraded-actions">
                  {degraded.resumable ? <button disabled={disabled || pending} onClick={() => void submit("请继续补全尚未确定的条件")}>补全剩余条件</button> : null}
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
          {skillMenuOpen ? <div className="skill-menu" aria-label="选择技能">
            <div className="skill-menu-heading"><strong>调用技能</strong><button type="button" className="text-button" onClick={onManageSkills}>管理技能</button></div>
            <p className="skill-menu-context">{skillContext}{thread && !thread.plan?.valid ? <button type="button" className="text-button" onClick={() => { closeSkills(); onEdit(); }}>去核验</button> : null}</p>
            {skillsLoading ? <p role="status" className="skill-menu-empty">正在加载技能…</p> : skillsError ? <div className="skill-menu-empty" role="alert">{skillsError}<button type="button" onClick={onRefreshSkills}>重新加载</button></div> : filteredSkills.length ? <div id="composer-skills" role="listbox" aria-label="已发布技能" className="skill-menu-list">
              {filteredSkills.map((skill, index) => <button id={`composer-skill-${index}`} type="button" role="option" aria-selected={activeSkill === index} className="skill-menu-option" key={skill.name} onPointerMove={() => setActiveSkill(index)} onClick={() => pickSkill(skill)}>
                <span><strong>{skill.display_name}</strong><small>/{skill.name}</small></span>{skill.description ? <p>{skill.description.split(/[。；]/, 1)[0]}</p> : null}
              </button>)}
            </div> : <p className="skill-menu-empty">{skills.length ? "没有匹配的技能，请调整搜索词。" : thread?.capabilities.insight ? "暂无已发布的可调用技能，请先到洞察技能页面登记并发布。" : "请先进入客群会话，并确认技能运行权限。"}</p>}
            <p className="skill-menu-hint">↑ ↓ 选择 · Enter 添加 · Esc 关闭</p>
          </div> : null}
          <div className="composer">
            {skillChips}
            {contextTags.length ? <div className="composer-tags" key={composerPulse || 0}><TagChips tags={contextTags} onRemove={onRemoveContextTag} /></div> : null}
            <div className="composer-editor">
              {draft.quote ? <div className="composer-quote"><span>引用消息</span><p>{draft.quote}</p>
                <button type="button" className="text-button" aria-label="移除消息引用" onClick={() => setDraft({ text: draft.text })}>移除</button>
              </div> : null}
              {analysisTarget ? (
                <button
                  ref={citeRef}
                  type="button"
                  className={`analysis-cite${citeSelected ? " is-selected" : ""}`}
                  aria-label={`引用图表：继续分析 ${analysisTarget.title || "已选图表"}，按删除键整块移除`}
                  aria-pressed={citeSelected}
                  onClick={() => { setCiteSelected(true); citeRef.current?.focus(); }}
                  onFocus={() => setCiteSelected(true)}
                  onBlur={() => setCiteSelected(false)}
                  onKeyDown={(event) => {
                    if (event.nativeEvent.isComposing) return;
                    if (event.key === "Backspace" || event.key === "Delete") {
                      event.preventDefault();
                      removeAnalysisCite();
                    } else if (event.key === "ArrowRight" || event.key === "ArrowDown" || event.key === "Enter") {
                      event.preventDefault();
                      setCiteSelected(false);
                      composerInput.current?.focus();
                    } else if (event.key === "Escape") {
                      event.preventDefault();
                      setCiteSelected(false);
                      composerInput.current?.focus();
                    }
                  }}
                >
                  继续分析：{analysisTarget.title || "已选图表"}
                </button>
              ) : null}
              <textarea
                value={draft.text}
                disabled={composerDisabled}
                ref={composerInput}
                className="composer-input"
                rows={2}
                aria-label="圈选需求或技能调用"
                aria-haspopup="listbox"
                aria-expanded={skillMenuOpen}
                aria-controls={skillMenuOpen && filteredSkills.length ? "composer-skills" : undefined}
                aria-activedescendant={skillMenuOpen && filteredSkills.length ? `composer-skill-${Math.min(activeSkill, filteredSkills.length - 1)}` : undefined}
                onChange={(event) => {
                  setDraft({ ...draft, text: event.currentTarget.value });
                  const next = slashQuery(event.currentTarget.value, event.currentTarget.selectionStart);
                  if (next && !skillMenuOpen) onRefreshSkills?.();
                  setSlash(next);setActiveSkill(0);
                }}
                onKeyDownCapture={(event) => {
                  if (event.nativeEvent.isComposing) return;
                  const input = event.currentTarget;
                  if (analysisTarget && event.key === "Backspace" && input.selectionStart === 0 && input.selectionEnd === 0) {
                    event.preventDefault();
                    event.stopPropagation();
                    removeAnalysisCite();
                    return;
                  }
                  if (analysisTarget && event.key === "ArrowLeft" && input.selectionStart === 0 && input.selectionEnd === 0) {
                    event.preventDefault();
                    event.stopPropagation();
                    setCiteSelected(true);
                    citeRef.current?.focus();
                    return;
                  }
                  if (!skillMenuOpen) {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void sendDraft();
                    }
                    return;
                  }
                  if (event.key === "Escape") { event.preventDefault();event.stopPropagation();closeSkills(); }
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
                    : selectedSkill ? `填写${selectedSkill.display_name}的分析目标…` : "描述客户条件，或直接提问、分析与改图…"
                }
              />
            </div>
            {planDraft.dirty || sending ? <div className="composer-scope">{planDraft.dirty ? <span>请先保存或放弃条件修改，再发送新需求</span> : null}{sending ? <span className="composer-hint" role="status">正在发送…</span> : null}</div> : null}
            <div className="composer-footer">
              {contextControl ? <div className="composer-context">{contextControl}</div> : null}
              {!selectedSkill ? <button type="button" className="composer-skill-button" disabled={composerDisabled}
                aria-label="选择技能" title="选择技能（/）" aria-expanded={skillMenuOpen} onClick={() => skillMenuOpen ? closeSkills() : openSkills()}>
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m12 3 1.6 4.7L18.3 9l-4.7 1.6L12 15.3l-1.6-4.7L5.7 9l4.7-1.3L12 3Z" /><path d="m19 14 .8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14ZM5 14l.7 2L7.7 17l-2 .7L5 20l-.7-2.3L2.3 17l2-.7L5 14Z" /></svg>
              </button> : null}
              {busy(thread) || thread?.status === "WAITING" ? (
                <button type="button" className="send-button" disabled={pending} title="取消本轮智能体任务" onClick={onCancel}><ActionIcon kind="stop" />停止处理</button>
              ) : (
                <button type="button" className="send-button" aria-label="发送需求" disabled={!canSend} onClick={() => void sendDraft()}>
                  <ActionIcon kind="send" />{sending ? "发送中…" : "发送"}
                </button>
              )}
            </div>
          </div>
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
