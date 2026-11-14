import { useState } from "react";
import { ActionIcon } from "./ActionIcon";
import { ClauseDetails, ClauseValueFields } from "./ClauseSummary";
import { clauseSentence, clauses, treeSentence, type Plan, type Tree } from "./agentTypes";
import type { PlanDraft } from "./usePlanDraft";

type Editor = {
  draft: PlanDraft;
  disabled: boolean;
  saving: boolean;
  error?: string;
  onSave: () => void;
  onOpenResults: () => void;
};

function ConditionFields({ tree, disabled, onChange, onRemove }: {
  tree: Tree;
  disabled: boolean;
  onChange: (tree: Tree) => void;
  onRemove?: () => void;
}) {
  if ("children" in tree) return <fieldset className="plan-form-group">
    <legend>{tree.logic === "AND" ? "满足以下全部条件" : "满足以下任一条件"}</legend>
    {tree.children.map((child, index) => <ConditionFields
      key={"clause_id" in child ? child.clause_id : `group:${index}`}
      tree={child} disabled={disabled}
      onChange={(next) => onChange({ ...tree, children: tree.children.map((item, i) => i === index ? next : item) })}
      onRemove={tree.children.length > 1
        ? () => onChange({ ...tree, children: tree.children.filter((_, i) => i !== index) })
        : onRemove}
    />)}
  </fieldset>;

  const name = tree.name || tree.source_span || "筛选条件";
  const exclusion = tree.operator === "not_in" || tree.operator === "!=";
  const editable = tree.kind !== "SCOPE_ALL" && !tree.compare_expression && (!tree.status || tree.status === "BOUND");
  return <div className="plan-form-row">
    <div className="plan-form-label">
      {exclusion && onRemove ? <label className="plan-form-exclusion">
        <input type="checkbox" checked disabled={disabled} onChange={onRemove} aria-label={`保留排除条件：${name}`} />
        <strong>{name}</strong>
      </label> : <strong>{name}</strong>}
      {tree.time_constraint ? <span className="plan-form-period">{tree.time_constraint}</span> : null}
      {tree.definition || tree.code_options?.length || tree.expression ? <details className="plan-form-caliber">
        <summary>查看口径</summary><ClauseDetails clause={tree} />
      </details> : null}
    </div>
    {editable ? <ClauseValueFields clause={tree} disabled={disabled} labelPrefix="方案卡："
      onChange={(patch) => onChange({ ...tree, ...patch })} />
      : <p className="plan-form-readonly">{clauseSentence(tree)}</p>}
  </div>;
}

export function InlinePlanCard({ plan, editor }: { plan?: Plan; editor?: Editor }) {
  const [copyNotice, setCopyNotice] = useState("");
  const shown = editor?.draft.draft ?? plan;
  const items = clauses(shown?.tree);
  const dirty = editor?.draft.dirty ?? false;
  const inputIncomplete = editor?.draft.incomplete ?? false;

  async function copyConditions() {
    if (!shown) return;
    try {
      await navigator.clipboard.writeText(treeSentence(shown.tree));
      setCopyNotice("已复制条件");
    } catch {
      setCopyNotice("复制失败，请重试");
    }
  }

  return <section className="plan-reply" aria-label="已生成筛选方案">
    <header className="plan-form-heading">
      <h2>智能圈选方案</h2>
      {shown?.revision !== undefined ? <span className="plan-status">v{shown.revision} · {dirty ? "未保存" : editor ? "已核验" : "历史方案"}</span> : null}
    </header>
    {editor && shown ? <form onSubmit={(event) => {
      event.preventDefault();
      if (dirty && !editor.disabled && !inputIncomplete) editor.onSave();
    }}>
      <p className="plan-form-status" role="status">{dirty ? "已修改条件，保存并核验后可重新统计。" : `已核验 ${items.length} 项筛选条件`}</p>
      <div className="plan-form-fields">
        <ConditionFields tree={shown.tree} disabled={editor.disabled} onChange={editor.draft.changeTree} />
      </div>
      {editor.draft.undoRemoval ? <button type="button" className="text-button" disabled={editor.disabled}
        onClick={editor.draft.undoRemoval}>撤销移除条件</button> : null}
      {inputIncomplete ? <p className="field-error">请填完整条件值，区间需要填写上下限。</p> : null}
      {editor.error ? <p className="field-error" role="alert">{editor.error}</p> : null}
      <div className="plan-form-actions">
        <button type="button" onClick={() => void copyConditions()}><ActionIcon kind="copy" />复制条件</button>
        {dirty ? <>
          <button type="button" className="text-button" disabled={editor.disabled} onClick={editor.draft.discard}>放弃修改</button>
          <button type="submit" className="primary" disabled={editor.disabled || inputIncomplete}
            aria-busy={editor.saving || undefined}>{editor.saving ? "核验中…" : "保存并核验条件"}</button>
        </> : <button type="button" className="primary" onClick={editor.onOpenResults}>查看圈选结果</button>}
      </div>
    </form> : <>
      <p className="message-text">可以核对条件并统计人数。</p>
      {items.length ? <ul className="plan-reply-conditions">
        {items.slice(0, 3).map((condition) => <li key={condition.clause_id} title={clauseSentence(condition)}>{clauseSentence(condition)}</li>)}
        {items.length > 3 ? <li>另有 {items.length - 3} 项条件</li> : null}
      </ul> : null}
    </>}
    {copyNotice ? <p className="plan-form-status" role="status">{copyNotice}</p> : null}
  </section>;
}
