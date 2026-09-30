import { useEffect, useState } from "react";
import type { Plan, Thread, Tree } from "./agentTypes";
import { busy, clauses, clauseChanged, clauseSentence, pendingItems } from "./agentTypes";
import { SummaryTree } from "./ClauseSummary";
import { PendingCard } from "./PendingCard";
import { PlanMenu } from "./PlanMenu";

function countTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "统计时间未提供" : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function acceptedConfirmations(thread: Thread | null, plan?: Plan): string[] {
  return (thread?.confirmed_clause_ids || []).filter((id) => clauses(plan?.tree).some((c) =>
    c.clause_id === id && c.status === "BOUND" && c.assumption_confirmed === true));
}

export function PlanPanel({ highlightedClauses, thread, pending, onSave, onRefine, onDiscuss, onCancel, onCount, onCreate, onPreview, onOpenGroup }: {
  highlightedClauses?: string[]; thread: Thread | null; pending: boolean; onSave: (p: Plan) => void; onRefine: (message: string) => void;
  onDiscuss: (message: string) => void; onCancel: () => void; onCount: () => void; onCreate: (name: string) => void;
  onPreview: () => void; onOpenGroup: (id: number) => void;
}) {
  const active = thread?.live_plan || thread?.plan;
  const [draft, setDraft] = useState<Plan>();
  const [dirty, setDirty] = useState(false);
  const [version, setVersion] = useState<number>();
  const [editing, setEditing] = useState<string>();
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [confirmedIds, setConfirmedIds] = useState<string[]>([]);
  useEffect(() => {
    setDraft(active); setDirty(false); setConfirm(false); setVersion(undefined); setEditing(undefined);
    setConfirmedIds(acceptedConfirmations(thread, active));
  }, [thread?.thread_id, thread?.revision, active]);
  useEffect(() => { setName(thread?.source_group_name || ""); }, [thread?.thread_id, thread?.source_group_name]);
  useEffect(() => { setConfirm(false); }, [thread?.execution?.group_id]);
  const historical = version !== undefined;
  const shown = historical ? thread?.versions.find((p) => p.revision === version) : draft;
  const running = busy(thread);
  const disabled = !!(pending || running || historical || thread?.archived);
  const items = clauses(shown?.tree);
  const pendingQueue = pendingItems(thread, shown).filter((p) => p.kind !== "assumption" || !confirmedIds.includes(p.clause_id!));
  const updating = !!thread?.source_group_id;
  const savePermission = updating ? thread?.capabilities.update : thread?.capabilities.create;
  const count = !dirty && !historical && !running && shown?.valid && thread?.count && thread.count.revision === thread.revision ? thread.count : undefined;
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
  const status = running ? "整理中" : dirty ? "未保存" : historical ? "历史版本" : queue.length ? "待处理" : execution ? updating ? "已更新" : "已创建" : shown?.valid ? "已核验" : "待核验";
  function changeTree(tree: Tree) {
    if (!shown || disabled) return;
    setConfirmedIds((ids) => ids.filter((id) => {
      const before = items.find((c) => c.clause_id === id);
      const after = clauses(tree).find((c) => c.clause_id === id);
      return before && after && !clauseChanged(before, after);
    }));
    setDraft({ ...shown, tree, valid: false }); setDirty(true); setConfirm(false);
  }
  function discard() {
    setDraft(active); setDirty(false); setEditing(undefined); setConfirm(false); setConfirmedIds(acceptedConfirmations(thread, active));
  }
  function confirmAssumption(id: string) {
    if (!shown || disabled) return;
    const ids = [...new Set([...confirmedIds, id])];
    if (!items.some((c) => c.status === "ASSUMED" && !ids.includes(c.clause_id))) {
      // 最后一项保留至服务端核验成功，提交失败时仍可直接重试。
      onSave({ ...shown, confirmed_clause_ids: ids });
    } else setConfirmedIds(ids);
  }
  return <aside id="agent-plan-editor" tabIndex={-1} className="plan-panel" aria-label="圈选方案">
    <div className="panel-heading plan-heading"><h2>圈选方案</h2>
      {shown || running ? <span className="plan-status" role="status">{shown?.revision ? `v${shown.revision} · ` : ""}{status}</span> : null}
      <PlanMenu thread={thread} plan={shown} historical={historical} dirty={dirty} onVersion={(revision) => { setVersion(revision); setEditing(undefined); setConfirm(false); }} />
    </div>
    <div className="plan-scroll">
      {thread?.archived ? <p className="plan-history-notice">会话已归档，恢复后可继续圈选。</p> : null}
      {updating ? <p className="plan-history-notice">正在编辑《{thread?.source_group_name}》。{thread?.source_requires_validation ? "已载入保存条件，须按最新发布版本重新核验。" : shown?.valid ? "已按最新发布版本重新核验。" : "条件尚待核验。"}{thread?.source_thread_reused === false ? "已建立新的编辑会话。" : ""}</p> : null}
      {historical ? <p className="plan-history-notice">你正在查看 v{version}<button className="text-button" onClick={() => setVersion(undefined)}>返回当前</button></p> : null}
      {running || thread?.status === "WAITING" ? <div className="plan-progress" role="status"><p>{running ? "正在整理条件…" : "等待业务选择"}</p><button className="text-button" disabled={pending} onClick={onCancel}>停止</button></div> : null}
      {!historical && !running && !dirty ? <PendingCard items={queue} disabled={disabled} canRemove={items.length > 1 || (shown?.intent_plan?.requirements.length || 0) > 1}
        onConfirm={confirmAssumption} onEdit={setEditing} onDiscuss={onDiscuss}
        onRemove={(item) => onRefine(`请移除这项要求：${item.title}，保留其余条件，并重新核验。`)} /> : null}
      {execution ? <div className="plan-created" role="status"><strong>{updating ? "已更新客群" : "已创建客群"}{name ? `《${name}》` : ""}</strong><span>按 v{thread?.revision} 的圈选条件{updating ? "更新" : "创建"}</span></div> : null}
      {shown && !running && !historical && !execution && (!queue.length || dirty) ? <section className="plan-count" aria-label="圈选客户数">
        <div className="plan-count-heading"><span>圈选客户数</span>{count ? <button className="text-button" disabled={!canExecute || !thread?.capabilities.count} onClick={onCount}>重新统计</button> : null}</div>
        <strong>{count ? count.value.toLocaleString() : "—"}{count ? <small> 人</small> : null}</strong>
        <p>{count ? `${countTime(count.executed_at)} · 数据截至 ${count.data_as_of || "未提供"}` : dirty ? "修改后须重新核验和统计" : confirmNew ? "确认新增条件后可统计人数" : "条件已核验，统计后显示人数"}</p>
        {count?.warning ? <details className="evidence"><summary>统计说明</summary><p>{count.warning}</p></details> : null}
      </section> : null}
      {shown?.tree ? <>
        {!("children" in shown.tree) ? <p className="single-condition-heading">圈选条件</p> : null}
        <SummaryTree highlightedClauses={highlightedClauses} tree={shown.tree} items={items} changes={changes} editing={editing} disabled={disabled} onEdit={(id) => setEditing(editing === id ? undefined : id)}
          onChange={changeTree} onDone={() => setEditing(undefined)} onDiscuss={onDiscuss} />
        {removed.map((c) => <p className="removed-clause" key={c.clause_id}><del>{clauseSentence(c)}</del><span>已删除</span></p>)}
        <button className="text-button add-condition" disabled={disabled} onClick={() => onDiscuss("在当前方案中补充一项条件，保留其余要求：")}>＋ 补充条件（在对话里说）</button>
      </> : !running ? <div className="plan-empty"><p>先描述你想寻找的客户</p><span>例如：近 3 个月消费至少 1 万元的金卡客户。</span></div> : null}
    </div>
    {shown && !running ? <div className="plan-actions">
      {dirty ? <><p className="muted">已修改 · 原人数失效</p><button className="primary" disabled={disabled} onClick={() => draft && onSave({ ...draft, confirmed_clause_ids: confirmedIds })}>保存并核验</button>
        <button className="text-button" disabled={disabled} onClick={discard}>放弃修改</button></> : historical ? <><button className="primary" disabled={pending || running || thread?.status === "WAITING" || !!thread?.archived} onClick={() => onSave(shown)}>以此版本继续</button>
          <button className="text-button" onClick={() => setVersion(undefined)}>返回当前方案</button></> : thread?.source_requires_validation ? <button className="primary" disabled={disabled || thread?.status === "WAITING"} onClick={() => onSave(shown)}>按最新发布版本核验</button> : confirmNew ? <button className="primary" disabled={disabled} onClick={() => onSave({ ...shown, confirmed_clause_ids: confirmedIds })}>确认新增条件</button> : queue.length ? <p className="muted">处理上方待确认事项后，可继续统计和{updating ? "更新" : "创建"}。</p> : execution ?
            <button className="primary" disabled={disabled} onClick={() => onOpenGroup(execution.group_id)}>打开客群</button> : confirm ? <div className="create-form">
              <label className="field-label">客群名称<input autoFocus disabled={disabled} value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="输入便于识别的名称" /></label>
              <p>将按当前 v{thread?.revision} 的 {items.length} 项条件{updating ? "更新原客群" : "创建客群"}。</p>
              <div className="action-row"><button disabled={disabled} onClick={() => setConfirm(false)}>取消</button><button className="primary" disabled={!name.trim() || !canExecute || !savePermission} onClick={() => onCreate(name.trim())}>{updating ? "确认更新" : "确认创建"}</button></div>
            </div> : <>
              {count ? <button className="primary" disabled={!canExecute || !savePermission} onClick={() => setConfirm(true)}>{updating ? "更新客群" : "创建客群"}</button> :
                <button className="primary" disabled={!canExecute || !thread?.capabilities.count} onClick={onCount}>统计人数</button>}
              <button className="text-button" disabled={!canExecute || !thread?.capabilities.preview} onClick={onPreview}>查看样例客户</button>
              {count && !savePermission ? <p className="muted">当前账号暂无{updating ? "更新" : "创建"}客群权限。</p> : !count && !thread?.capabilities.count ? <p className="muted">当前账号暂无统计权限。</p> : null}
            </>}
    </div> : null}
  </aside>;
}
