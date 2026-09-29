import { useId, useRef, useState } from "react";
import type { Clause, Tree } from "./agentTypes";
import { clauseSentence, clauseUnit, operatorNames } from "./agentTypes";
import { ListboxSelect } from "./ListboxSelect";

export function PlanIcon({ kind }: { kind: "edit" | "info" | "more" | "close" }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === "edit" ? <><path d="m15 4 5 5M4 20l5-1L20 8a2.1 2.1 0 0 0-4-4L5 15l-1 5Z" /></> :
      kind === "info" ? <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></> :
      kind === "close" ? <path d="m6 6 12 12M18 6 6 18" /> : <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>}
  </svg>;
}

export function ClauseEditor({ clause: c, disabled, onChange, onDone, onRemove, onDiscuss }: {
  clause: Clause; disabled: boolean; onChange: (c: Clause) => void; onDone: () => void; onRemove?: () => void; onDiscuss: (text: string) => void;
}) {
  const patch = (p: Partial<Clause>) => onChange({ ...c, ...p, unresolved: null, gap_reason: undefined });
  const candidates = [...new Map((c.candidates || []).map((x) => [x.tag_id, x])).values()];
  const selectTag = (tagId: string) => {
    const id = Number(tagId);
    // 新标签的单位、码值、口径与依据由核验重新加载，不能沿用原标签的发布元数据。
    patch({ tag_id: id, name: candidates.find((x) => x.tag_id === id)?.name, values: [], code_options: [],
      allowed_operators: undefined, unit: undefined, value_unit: undefined, value_scale: undefined,
      definition: undefined, caliber_struct: undefined, evidence_id: undefined, status: "UNRESOLVED" });
  };
  return <div className="clause-editor" aria-label={`编辑${c.name || c.clause_id}`}>
    {c.kind !== "SCOPE_ALL" ? <>
      {candidates.length > 1 ? <label className="field-label field-label--tag">换一个标签
        <ListboxSelect ariaLabel="换一个标签" disabled={disabled} value={c.tag_id ? String(c.tag_id) : ""} placeholder="请选择标签"
          triggerClassName="library-select-trigger--field" onChange={selectTag}
          options={candidates.map((x) => ({ value: String(x.tag_id), label: x.name }))} />
      </label> : candidates.length === 1 && (c.status !== "BOUND" || c.gap_reason || c.unresolved) ? <button disabled={disabled} onClick={() => selectTag(String(candidates[0].tag_id))}>采用标签：{candidates[0].name}</button> : null}
      <div className="condition-inputs">
        <label className="field-label field-label--operator">比较方式
          <ListboxSelect ariaLabel={`${c.name || c.clause_id}比较方式`} disabled={disabled} value={c.operator || "="}
            triggerClassName="library-select-trigger--field" onChange={(operator) => patch({ operator, values: ["is_null", "is_not_null"].includes(operator) ? [] : c.values })}
            options={[...new Set([...(c.allowed_operators || ["=", "!=", ">", ">=", "<", "<=", "between", "in", "not_in"]), c.operator || "="])].map((op) => ({ value: op, label: operatorNames[op] || op }))} />
        </label>
        {!["is_null", "is_not_null"].includes(c.operator || "") && !c.compare_expression ? <label className="field-label field-label--value">
          条件值{clauseUnit(c) ? `（${clauseUnit(c)}）` : ""}
          {c.code_options?.length && ["in", "not_in"].includes(c.operator || "") ?
            <ListboxSelect multiple ariaLabel={`${c.name || c.clause_id}条件值`} disabled={disabled} placeholder="请选择"
              triggerClassName="library-select-trigger--field" value={c.values || []} onChange={(values) => patch({ values })}
              options={c.code_options.map((o) => ({ value: o.code, label: o.label || o.code }))} /> :
            c.code_options?.length && c.operator !== "between" ?
              <ListboxSelect ariaLabel={`${c.name || c.clause_id}条件值`} disabled={disabled} placeholder="请选择"
                triggerClassName="library-select-trigger--field" value={c.values?.[0] || ""} onChange={(value) => patch({ values: value ? [value] : [] })}
                options={c.code_options.map((o) => ({ value: o.code, label: o.label || o.code }))} /> :
              <input aria-label={`${c.name || c.clause_id}条件值`} disabled={disabled} value={(c.values || []).join(", ")}
                placeholder={c.operator === "between" ? "下限, 上限" : "填写条件值"}
                onChange={(e) => patch({ values: e.target.value.split(/[,，]/).map((v) => v.trim()) })} />}
        </label> : null}
      </div>
      {c.values?.some((v) => c.code_options?.length && !c.code_options.some((o) => o.code === v)) ? <p className="field-error">条件中有未发布的码值，请重新选择。</p> : null}
      <button className="text-button clause-discuss" disabled={disabled} onClick={() => onDiscuss(`我想调整“${c.name || c.source_span || "这项条件"}”的时间或业务口径：`)}>修改时间或口径，在对话里说</button>
    </> : <p className="muted">采用当前标签库的授权客户范围。</p>}
    <div className="clause-editor-actions">
      <button disabled={disabled} onClick={onDone}>完成</button>
      {onRemove ? <button className="text-button remove-condition" disabled={disabled} onClick={onRemove}>删除此条件</button> : null}
    </div>
  </div>;
}

export function ClauseSummary({ highlighted, clause: c, number, change, open, disabled, onEdit, onChange, onDone, onRemove, onDiscuss }: {
  highlighted?: boolean; clause: Clause; number: number; change?: "新" | "改"; open: boolean; disabled: boolean;
  onEdit: () => void; onChange: (c: Clause) => void; onDone: () => void; onRemove?: () => void; onDiscuss: (text: string) => void;
}) {
  const [info, setInfo] = useState(false);
  const [infoPosition, setInfoPosition] = useState({ left: 0, top: 0, width: 300 });
  const row = useRef<HTMLElement>(null);
  const infoId = useId();
  const editorId = useId();
  const sentence = clauseSentence(c);
  const exception = c.status === "ASSUMED" ? "待确认" : (c.status && c.status !== "BOUND") || c.unresolved || c.gap_reason ? "待补充" : undefined;
  return <section className="condition clause-row" data-highlighted={highlighted || undefined} ref={row}>
    <div className="clause-summary">
      <span className="clause-number">{number}</span>
      <div className="clause-copy">
        <p title={c.source_span && c.source_span !== sentence && c.source_span !== c.name ? c.source_span : undefined}>{sentence}</p>
        {exception || change ? <div className="clause-markers">{exception ? <span className="clause-exception">{exception}</span> : null}{change ? <span className="clause-change">{change}</span> : null}</div> : null}
      </div>
      <div className="clause-tools">
        <button className="plan-icon-button" aria-label={`${c.name || c.clause_id}口径说明`} aria-expanded={info} popoverTarget={infoId} onClick={() => {
          const rect = row.current?.getBoundingClientRect();
          if (rect) {
            const width = Math.min(rect.width, 340, window.innerWidth - 24);
            setInfoPosition({ width, left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), top: Math.max(12, Math.min(rect.bottom + 4, window.innerHeight - 200)) });
          }
        }}><PlanIcon kind="info" /></button>
        <button className="plan-icon-button" aria-label={`编辑条件：${c.name || c.clause_id}`} aria-expanded={open} aria-controls={editorId} disabled={disabled} onClick={onEdit}><PlanIcon kind="edit" /></button>
      </div>
    </div>
    <div id={infoId} popover="auto" className="clause-info" role="note" style={infoPosition} onToggle={(event) => setInfo(event.newState === "open")}>
      <p>{c.definition || (c.kind === "SCOPE_ALL" ? "采用当前标签库的授权客户范围。" : "核验后可查看发布口径。")}{c.time_constraint ? ` 时间范围：${c.time_constraint}。` : ""}</p>
      {["not_in", "!="].includes(c.operator || "") ? <p>排除空值；{c.unknown_policy === "INCLUDE" ? "包含" : "排除"}未知码值。</p> : null}
    </div>
    {open ? <div id={editorId}><ClauseEditor clause={c} disabled={disabled} onChange={onChange} onDone={onDone} onRemove={onRemove} onDiscuss={onDiscuss} /></div> : null}
  </section>;
}

export function SummaryTree({ highlightedClauses, tree, items, changes, editing, disabled, onEdit, onChange, onDone, onDiscuss, onRemove }: {
  highlightedClauses?: string[]; tree: Tree; items: Clause[]; changes: Map<string, "新" | "改">; editing?: string; disabled: boolean; onEdit: (id: string) => void;
  onChange: (tree: Tree) => void; onDone: () => void; onDiscuss: (text: string) => void; onRemove?: () => void;
}) {
  const [changingLogic, setChangingLogic] = useState(false);
  if ("children" in tree) return <div className="condition-group">
    <div className="group-heading">
      {changingLogic ? <><ListboxSelect ariaLabel="条件组合" disabled={disabled} value={tree.logic}
        triggerClassName="library-select-trigger--compact" onChange={(logic) => { onChange({ ...tree, logic: logic as "AND" | "OR" }); setChangingLogic(false); }}
        options={[{ value: "AND", label: "满足以下全部条件" }, { value: "OR", label: "满足以下任一条件" }]} />
        <button className="text-button" onClick={() => setChangingLogic(false)}>取消</button></> :
        <button className="logic-summary text-button" aria-label={`条件组合：满足以下${tree.logic === "AND" ? "全部" : "任一"}条件`} disabled={disabled} onClick={() => setChangingLogic(true)}>
          满足以下{tree.logic === "AND" ? "全部" : "任一"}条件
        </button>}
    </div>
    <div className="condition-children">{tree.children.map((child, i) => <SummaryTree key={"clause_id" in child ? child.clause_id : `group:${i}`}
      highlightedClauses={highlightedClauses} tree={child} items={items} changes={changes} editing={editing} disabled={disabled} onEdit={onEdit} onDone={onDone} onDiscuss={onDiscuss}
      onChange={(next) => onChange({ ...tree, children: tree.children.map((c, j) => i === j ? next : c) })}
      onRemove={tree.children.length > 1 ? () => onChange({ ...tree, children: tree.children.filter((_, j) => i !== j) }) : onRemove} />)}</div>
  </div>;
  return <ClauseSummary highlighted={highlightedClauses?.includes(tree.clause_id)} clause={tree} number={items.findIndex((c) => c.clause_id === tree.clause_id) + 1} change={changes.get(tree.clause_id)}
    open={editing === tree.clause_id} disabled={disabled} onEdit={() => onEdit(tree.clause_id)} onChange={onChange} onDone={onDone} onRemove={onRemove} onDiscuss={onDiscuss} />;
}
