import { useEffect, useRef, useState } from "react";
import type { Plan, Thread, Tree } from "./agentTypes";
import { busy, clauses, clauseChanged, clauseSentence, pendingItems, runPhaseText } from "./agentTypes";
import { SummaryTree } from "./ClauseSummary";
import { PendingCard } from "./PendingCard";
import { ActionIcon } from "./ActionIcon";
import { PlanMenu } from "./PlanMenu";
import type { PlanDraft } from "./usePlanDraft";

function countTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "统计时间未提供" : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
export function PlanPanel({ highlightedClauses, thread, pending, planDraft, onSave, onRefine, onDiscuss, onCancel, onCount, onCreate, onPreview, onOpenGroup, onViewInsights, hidden, error, onDismissError, onRetryError }: {
  highlightedClauses?: string[]; thread: Thread | null; pending: boolean; planDraft: PlanDraft; onSave: (p: Plan) => void; onRefine: (message: string) => void;
  onDiscuss: (message: string) => void; onCancel: () => void; onCount: () => void; onCreate: (name: string) => void;
  onPreview: () => void; onOpenGroup: (id: number) => void; onViewInsights?: () => void; hidden?: boolean; error?: string; onDismissError?: () => void; onRetryError?: () => void;
}) {
  const active = busy(thread) ? thread?.live_plan || thread?.plan : thread?.plan;
  const { draft, dirty, confirmedIds, undoRemoval } = planDraft;
  const [version, setVersion] = useState<number>();
  const [editing, setEditing] = useState<string>();
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busyAction, setBusyAction] = useState<"count" | "save" | "create" | "preview" | null>(null);
  useEffect(() => { if (!pending) setBusyAction(null); }, [pending]);
  function run<T extends "count" | "save" | "create" | "preview">(action: T, fn: () => void) {
    setBusyAction(action);
    fn();
  }
  const busyLabel = busyAction === "count" ? "统计中…" : busyAction === "save" ? "保存中…" : busyAction === "create" ? "创建中…" : busyAction === "preview" ? "加载中…" : null;
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!confirm) return;
    // 等折叠展开动画结束再聚焦，避免输入区在动画中被滚动到视口。
    const timer = window.setTimeout(() => nameInput.current?.focus(), 180);
    return () => window.clearTimeout(timer);
  }, [confirm]);
  useEffect(() => {
    setConfirm(false); setVersion(undefined); setEditing(undefined);
  }, [thread?.thread_id, thread?.revision, active?.hash]);
  useEffect(() => { if (dirty) setConfirm(false); }, [dirty]);
  useEffect(() => { setName(thread?.source_group_name || ""); }, [thread?.thread_id, thread?.source_group_name]);
  useEffect(() => { setConfirm(false); }, [thread?.execution?.group_id]);
  const historical = version !== undefined;
  const shown = historical ? thread?.versions.find((p) => p.revision === version) : busy(thread) ? active : draft;
  const running = busy(thread);
  const disabled = !!(pending || running || historical || thread?.archived);
  const items = clauses(shown?.tree);
  const pendingQueue = pendingItems(thread, shown).filter((p) => p.kind !== "assumption" || !confirmedIds.includes(p.clause_id!));
  const updating = !!thread?.source_group_id;
  const savePermission = updating ? thread?.capabilities.update : thread?.capabilities.create;
  const count = !dirty && !historical && !running && shown?.valid && thread?.count && thread.count.revision === thread.revision && (!thread.count.plan_hash || thread.count.plan_hash === shown.hash) ? thread.count : undefined;
  const execution = !dirty && !historical && !running && thread?.execution && thread.execution.revision === thread.revision ? thread.execution : undefined;
  const previous = thread?.versions.find((p) => p.revision === (shown?.revision || 1) - 1);
  const comparison = dirty ? active : previous;
  const old = new Map(clauses(comparison?.tree).map((c) => [c.clause_id, c]));
  const changes = new Map<string, "新" | "改">();
  if (comparison) for (const c of items) {
    const before = old.get(c.clause_id);
    if (!before) changes.set(c.clause_id, "新");
    else if (clauseChanged(before, c)) changes.set(c.clause_id, "改");
  }
  const removed = comparison ? clauses(comparison.tree).filter((c) => !items.some((item) => item.clause_id === c.clause_id)) : [];
  const provenanceOnly = !!shown?.diagnostics?.length && shown.diagnostics.every((d) => d.code === "LITERAL_DRIFT" && d.message.includes("来源必须逐字引用用户原话"));
  const confirmNew = updating && !dirty && !historical && !thread?.source_requires_validation && thread?.status !== "WAITING"
    && !execution && [...changes.values()].includes("新") && items.every((c) => c.status === "BOUND")
    && (!pendingQueue.length || provenanceOnly);
  // 用户在右侧确认可见的新条件后走既有手工编辑核验；来源格式不再逐项追问。
  const queue = confirmNew && provenanceOnly ? [] : pendingQueue;
  const canExecute = !!thread?.plan?.valid && !!shown?.valid && !thread?.source_requires_validation && !dirty && !historical && !disabled && thread?.status !== "WAITING" && !queue.length && !confirmNew;
  const status = running ? runPhaseText(thread) : dirty ? "未保存" : historical ? "历史版本" : queue.length ? "待处理" : execution ? updating ? "已更新" : "已创建" : shown?.valid ? "已核验" : "待核验";
  function changeTree(tree: Tree) {
    if (disabled) return;
    planDraft.changeTree(tree);
    setConfirm(false);
  }
  function discard() {
    planDraft.discard();
    setEditing(undefined);
    setConfirm(false);
  }
  function confirmAssumption(id: string) {
    if (!shown || disabled) return;
    const ids = [...new Set([...confirmedIds, id])];
    if (!items.some((c) => c.status === "ASSUMED" && !ids.includes(c.clause_id))) {
      // 最后一项保留至服务端核验成功，提交失败时仍可直接重试。
      onSave({ ...shown, confirmed_clause_ids: ids });
    } else planDraft.confirmAssumption(ids);
  }
  const originalRequest = shown?.intent_plan?.original_request || thread?.messages.find((message) => message.role === "user")?.text;
  const regenerate = originalRequest && !dirty && !disabled && thread?.status !== "WAITING"
    ? () => onDiscuss(originalRequest) : undefined;
  return <aside id="agent-plan-editor" tabIndex={-1} className="plan-panel" aria-label="圈选方案" hidden={hidden} inert={hidden || undefined}>
    <div className="plan-scroll">
      {error ? <p className="plan-inline-error" role="alert"><span>{error}</span><span className="plan-inline-error-actions">{onRetryError ? <button type="button" className="text-button" onClick={onRetryError}>重试</button> : null}{onDismissError ? <button type="button" className="text-button" onClick={onDismissError}>关闭</button> : null}</span></p> : null}
      {thread?.archived ? <p className="plan-history-notice">会话已归档，恢复后可继续圈选。</p> : null}
      {updating ? <p className="plan-history-notice">正在编辑《{thread?.source_group_name}》。{thread?.source_requires_validation ? "已载入保存条件，须按最新发布版本重新核验。" : shown?.valid ? "已按最新发布版本重新核验。" : "条件尚待核验。"}{thread?.source_thread_reused === false ? "已建立新的编辑会话。" : ""}</p> : null}
      {historical ? <p className="plan-history-notice">你正在查看 v{version}<button className="text-button" onClick={() => setVersion(undefined)}>返回当前</button></p> : null}
      {running || thread?.status === "WAITING" ? <div className="plan-progress" role="status"><p>{running ? "正在整理条件…" : "等待业务选择"}</p><button className="text-button" disabled={pending} onClick={onCancel}>停止</button></div> : null}
      {!historical && !running && !dirty ? <PendingCard items={queue} disabled={disabled} canRemove={items.length > 1 || (shown?.intent_plan?.requirements.length || 0) > 1}
        onConfirm={confirmAssumption} onEdit={setEditing} onDiscuss={onDiscuss}
        onRemove={(item) => onRefine(`请移除这项要求：${item.title}，保留其余条件，并重新核验。`)} /> : null}
      {execution ? <div className="plan-created" role="status"><strong>{updating ? "已更新客群" : "已创建客群"}{name ? `《${name}》` : ""}</strong><span>按 v{thread?.revision} 的圈选条件{updating ? "更新" : "创建"}</span></div> : null}
      {shown && !running && !historical && (!execution || !!count) && (!queue.length || dirty) ? <section className="result-card plan-count" aria-label="圈选客户数">
        <div className="plan-count-heading"><span>命中人数</span>{count && !execution ? <button className="text-button" disabled={!canExecute || !thread?.capabilities.count} data-busy={busyAction === "count" ? "true" : undefined} aria-busy={busyAction === "count" || undefined} onClick={() => run("count", onCount)}>{busyAction === "count" ? "统计中…" : "重新统计"}</button> : null}</div>
        <strong>{count ? count.value.toLocaleString() : "—"}{count ? <small> 人</small> : null}</strong>
        {count ? <div className="count-provenance"><p>业务数据日期 · {count.data_as_of || "未知"}</p><p>查询时间 · {countTime(count.executed_at)}</p></div>
          : <p>{dirty ? "修改后须重新核验和统计" : confirmNew ? "确认新增条件后可统计人数" : "条件已核验，统计后显示人数"}</p>}
        {count?.warning ? <details className="evidence"><summary>统计说明</summary><p>{count.warning}</p></details> : null}
      </section> : null}
      {shown?.tree ? <section className="result-card result-conditions" aria-labelledby="result-conditions-title">
        <header className="plan-heading">
          <h3 id="result-conditions-title">筛选条件</h3>
          <span className="plan-status" role="status">{shown.revision ? `v${shown.revision} · ` : ""}{busyLabel || status}</span>
          <PlanMenu thread={thread} plan={shown} historical={historical} dirty={dirty} onRegenerate={regenerate} onVersion={(revision) => { setVersion(revision); setEditing(undefined); setConfirm(false); }} />
        </header>
        <SummaryTree highlightedClauses={highlightedClauses} tree={shown.tree} items={items} changes={changes} editing={editing} disabled={disabled} onEdit={(id) => setEditing(editing === id ? undefined : id)}
          onChange={changeTree} onDone={() => setEditing(undefined)} onDiscuss={onDiscuss} />
        {removed.map((c) => <p className="removed-clause" key={c.clause_id}><del>{clauseSentence(c)}</del><span>已删除</span></p>)}
        {undoRemoval ? <button type="button" className="text-button undo-removal" disabled={disabled} onClick={undoRemoval}>撤销删除</button> : null}
        <button className="text-button add-condition" disabled={disabled} onClick={() => onDiscuss("在当前方案中补充一项条件，保留其余要求：")}>＋ 补充条件（在对话里说）</button>
      </section> : !running ? <div className="plan-empty"><p>生成方案后，可在这里核对条件和统计人数。</p></div> : null}
      {shown && !running ? <section className="result-card plan-actions" aria-labelledby="result-actions-title">
      <h3 id="result-actions-title">下一步操作</h3>
      {!dirty && !historical && !execution && shown.valid ? <p className="muted">方案已核验；{updating ? "尚未更新客群" : "尚未创建客群"}。</p> : null}
      {dirty ?<><p className="muted" role="status">条件修改尚未保存并核验，原人数失效；客群不会自动更新。</p>
        {planDraft.incomplete ? <p className="field-error">请填完整条件值，区间需要填写上下限。</p> : null}
        <button className="primary" disabled={disabled || planDraft.incomplete} data-busy={busyAction === "save" ? "true" : undefined} aria-busy={busyAction === "save" || undefined} onClick={() => run("save", () => draft && onSave({ ...draft, confirmed_clause_ids: confirmedIds }))}><ActionIcon kind="save" />{busyAction === "save" ? "核验中…" : "保存并核验"}</button>
        <button className="text-button" disabled={disabled} onClick={discard}>放弃修改</button></> : historical ? <><button className="primary" disabled={pending || running || thread?.status === "WAITING" || !!thread?.archived} data-busy={busyAction === "save" ? "true" : undefined} aria-busy={busyAction === "save" || undefined} onClick={() => run("save", () => onSave(shown))}>{busyAction === "save" ? "核验中…" : "以此版本继续"}</button>
          <button className="text-button" onClick={() => setVersion(undefined)}>返回当前方案</button></> : thread?.source_requires_validation ? <button className="primary" disabled={disabled || thread?.status === "WAITING"} data-busy={busyAction === "save" ? "true" : undefined} aria-busy={busyAction === "save" || undefined} onClick={() => run("save", () => onSave(shown))}>{busyAction === "save" ? "核验中…" : "按最新发布版本核验"}</button> : confirmNew ? <button className="primary" disabled={disabled} data-busy={busyAction === "save" ? "true" : undefined} aria-busy={busyAction === "save" || undefined} onClick={() => run("save", () => onSave({ ...shown, confirmed_clause_ids: confirmedIds }))}>{busyAction === "save" ? "核验中…" : "确认新增条件"}</button> : queue.length ? <p className="muted">处理上方待确认事项后，可继续统计和{updating ? "更新" : "创建"}。</p> : execution ?
            <button className="primary" disabled={disabled} onClick={() => onOpenGroup(execution.group_id)}>打开客群</button> : confirm ? <div className="create-form collapse-in">
              <div>
              <label className="field-label">客群名称<input ref={nameInput} disabled={disabled} value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="输入便于识别的名称" /></label>
              <dl className="create-review">
                <dt>使用方案</dt><dd>v{thread?.revision} · {items.length} 项条件</dd>
                <dt>已统计人数</dt><dd>{count?.value.toLocaleString("zh-CN")} 人</dd>
                <dt>业务数据日期</dt><dd>{count?.data_as_of || "未知"}</dd>
                {updating ? <><dt>更新客群</dt><dd>{thread?.source_group_name}</dd></> : null}
              </dl>
              <div className="action-row"><button disabled={disabled} onClick={() => setConfirm(false)}>取消</button><button className="primary" disabled={!name.trim() || !canExecute || !savePermission} data-busy={busyAction === "create" ? "true" : undefined} aria-busy={busyAction === "create" || undefined} onClick={() => run("create", () => onCreate(name.trim()))}>{busyAction === "create" ? (updating ? "更新中…" : "创建中…") : updating ? "确认更新" : "确认创建"}</button></div>
              </div>
            </div> : <>
              {count ? <button className="primary" disabled={!canExecute || !savePermission} onClick={() => setConfirm(true)}><ActionIcon kind="save" />{updating ? "更新客群" : "创建客群"}</button> :
                <button className="primary" disabled={!canExecute || !thread?.capabilities.count} data-busy={busyAction === "count" ? "true" : undefined} aria-busy={busyAction === "count" || undefined} onClick={() => run("count", onCount)}><ActionIcon kind="run" />{busyAction === "count" ? "统计中…" : "统计人数"}</button>}
              <button className="text-button" disabled={!canExecute || !thread?.capabilities.preview} data-busy={busyAction === "preview" ? "true" : undefined} aria-busy={busyAction === "preview" || undefined} onClick={() => run("preview", onPreview)}>{busyAction === "preview" ? "加载中…" : "查看样例客户"}</button>
              {onViewInsights ? <button type="button" className="text-button" onClick={onViewInsights}>查看客群洞察</button> : null}
              {count && !savePermission ? <p className="muted">当前账号暂无{updating ? "更新" : "创建"}客群权限。</p> : !count && !thread?.capabilities.count ? <p className="muted">当前账号暂无统计权限。</p> : null}
            </>}
      </section> : null}
    </div>
  </aside>;
}
