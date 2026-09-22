import { useEffect, useState } from "react";
import type { Clause, Plan, Thread, Tree } from "./agentTypes";
import { busy, clauses, planDiff, planStateText, expressionText } from "./agentTypes";
const unitLabels: Record<string, string> = {
  CNY: "元",
  COUNT: "次",
  RATIO: "比例",
  PERSON: "人",
  DAY: "天",
  MONTH: "月",
  POINT: "点",
  SHARE: "份",
};
const caliberLabels: Record<string, string> = {
  unit: "单位",
  scope: "统计范围",
  statistic: "统计方式",
  unit_scale: "单位倍率",
  calendar_mode: "周期类型",
  time_anchor_type: "时间类型",
  time_window_unit: "窗口单位",
  time_window_value: "窗口长度",
  time_anchor_label: "时间口径",
  period_edge: "期间边界",
  time_offset_years: "年偏移",
  time_offset_months: "月偏移",
  numerator: "分子",
  denominator: "分母",
  source_system: "来源系统",
  boundary_semantics: "边界含义",
};
const caliberValues: Record<string, string> = {
  NONE: "无",
  ALL: "全部",
  FLAG: "标志",
  SUM: "合计",
  AVG: "平均",
  MAX: "最大值",
  MIN: "最小值",
  COUNT: "计数",
  ROLLING: "滚动周期",
  CALENDAR: "自然周期",
  WINDOW: "时间窗口",
  WHOLE: "完整期间",
  DAY: "天",
  MONTH: "月",
  YEAR: "年",
  CNY: "元",
};
const operatorNames: Record<string, string> = {
  "=": "等于",
  "!=": "不等于",
  ">": "大于",
  ">=": "至少",
  "<": "小于",
  "<=": "不超过",
  in: "属于",
  not_in: "不属于",
  between: "介于",
  contains: "包含",
  like: "匹配",
  is_null: "为空",
  is_not_null: "不为空",
};
function TreeEditor({
  tree,
  onChange,
  disabled = false,
}: {
  tree: Tree;
  onChange: (v: Tree) => void;
  disabled?: boolean;
}) {
  if ("children" in tree)
    return (
      <div className="condition-group">
        <div className="group-heading">
          <select
            aria-label="条件组合"
            disabled={disabled}
            value={tree.logic}
            onChange={(e) =>
              onChange({ ...tree, logic: e.target.value as "AND" | "OR" })
            }
          >
            <option value="AND">全部满足</option>
            <option value="OR">任一满足</option>
          </select>
          <span>{tree.children.length} 项条件</span>
        </div>
        <div className="condition-children">
          {tree.children.map((child, i) => (
            <div key={"clause_id" in child ? child.clause_id : i}>
              <TreeEditor
                tree={child}
                disabled={disabled}
                onChange={(v) =>
                  onChange({
                    ...tree,
                    children: tree.children.map((c, j) => (j === i ? v : c)),
                  })
                }
              />
              {!disabled && tree.children.length > 1 ? (
                <button
                  className="text-button remove-condition"
                  onClick={() =>
                    onChange({
                      ...tree,
                      children: tree.children.filter((_, j) => j !== i),
                    })
                  }
                >
                  移除此条件
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    );
  const c = tree;
  const patch = (p: Partial<Clause>) =>
    onChange({ ...c, ...p, unresolved: null });
  if (c.kind === "SCOPE_ALL") return <section className="condition">
    <strong>当前授权范围内的全部客户</strong>
    <p className="muted">统计沿用当前标签库的数据范围与权限。</p>
  </section>;
  if (c.kind === "DERIVED_PREDICATE") return <section className="condition">
    <div className="condition-title"><strong>{c.name || c.source_span || "计算条件"}</strong>
      <span className={`status-dot ${c.status === "BOUND" ? "bound" : ""}`}>{c.status === "BOUND" ? "已核验" : "待核验"}</span></div>
    <p>{expressionText(c.expression)}</p>
    <p>{operatorNames[c.operator || "="] || c.operator} {c.compare_expression ? expressionText(c.compare_expression) : (c.values || []).join(" 至 ")}</p>
    <p className="muted">缺失值保留为未知；比例的分母须大于零。可在对话中修改指标或阈值。</p>
    {c.unresolved ? <p className="field-error">{c.unresolved}</p> : null}
  </section>;
  return (
    <section className="condition">
      <div className="condition-title">
        <strong>{c.name || c.source_span || c.query || "待选择标签"}</strong>
        <span className={`status-dot ${c.status === "BOUND" ? "bound" : ""}`}>
          {c.status === "BOUND" ? "已匹配" : "待补充"}
        </span>
      </div>
      {c.source_span && c.source_span !== c.name ? (
        <p className="source-text">{c.source_span}</p>
      ) : null}
      {c.candidates?.length ? (
        <label className="field-label">
          关联标签
          <select
            disabled={disabled}
            value={c.tag_id || ""}
            onChange={(e) =>
              patch({
                tag_id: Number(e.target.value),
                name: c.candidates?.find(
                  (x) => x.tag_id === Number(e.target.value)
                )?.name,
                values: [],
                code_options: [],
                allowed_operators: undefined,
                value_unit: undefined,
                value_scale: undefined,
                status: "UNRESOLVED",
              })
            }
          >
            <option value="">请选择标签</option>
            {[...new Map(c.candidates.map((x) => [x.tag_id, x])).values()].map(
              (x) => (
                <option key={x.tag_id} value={x.tag_id}>
                  {x.name}
                </option>
              )
            )}
          </select>
        </label>
      ) : null}
      <div className="condition-inputs">
        <label className="field-label">
          比较方式
          <select
            aria-label={`${c.name || c.clause_id}比较方式`}
            disabled={disabled}
            value={c.operator || "="}
            onChange={(e) => patch({ operator: e.target.value })}
          >
            {[
              ...new Set([
                ...(c.allowed_operators || [
                  "=",
                  ">",
                  ">=",
                  "<",
                  "<=",
                  "between",
                  "in",
                  "not_in",
                ]),
                c.operator || "=",
              ]),
            ].map((op) => (
              <option key={op} value={op}>
                {operatorNames[op] || op}
              </option>
            ))}
          </select>
        </label>
        {!["is_null", "is_not_null"].includes(c.operator || "") ? (
          <label className="field-label">
            条件值
            {c.unit && c.unit !== "NONE"
              ? `（${
                  Number(c.value_scale || 1) === 10000
                    ? "万"
                    : Number(c.value_scale || 1) !== 1
                    ? `${c.value_scale} × `
                    : ""
                }${unitLabels[c.unit] || c.unit}）`
              : ""}
            {c.code_options?.length ? (
              <select
                disabled={disabled}
                multiple={["in", "not_in"].includes(c.operator || "")}
                value={
                  ["in", "not_in"].includes(c.operator || "")
                    ? c.values || []
                    : c.values?.[0] || ""
                }
                onChange={(e) =>
                  patch({
                    values: Array.from(e.target.selectedOptions).map(
                      (o) => o.value
                    ),
                  })
                }
              >
                <option value="" disabled>
                  请选择
                </option>
                {c.code_options.map((o) => (
                  <option key={o.code} value={o.code}>
                    {o.label || o.code}
                  </option>
                ))}
              </select>
            ) : (
              <input
                disabled={disabled}
                value={(c.values || []).join(", ")}
                aria-label={`${c.name || c.clause_id}条件值`}
                placeholder={
                  c.operator === "between" ? "下限, 上限" : "填写条件值"
                }
                onChange={(e) =>
                  patch({
                    values: e.target.value.split(/[,，]/).map((v) => v.trim()),
                  })
                }
              />
            )}
          </label>
        ) : null}
      </div>
      {c.time_constraint ? (
        <p className="muted">时间口径：{c.time_constraint}</p>
      ) : null}
      {["not_in", "!="].includes(c.operator || "") ? (
        <p className="muted">
          排除空值；{c.unknown_policy === "INCLUDE" ? "包含" : "排除"}未知码值。
        </p>
      ) : null}
      {c.unresolved ? <p className="field-error">{c.unresolved}</p> : null}
      <details className="evidence">
        <summary>查看口径与依据</summary>
        <p>{c.definition || "选择标签后将读取发布口径"}</p>
        {c.caliber_struct ? (
          <dl>
            {Object.entries(c.caliber_struct)
              .filter(([, v]) => v !== null && v !== "")
              .map(([k, v]) => (
                <div key={k}>
                  <dt>{caliberLabels[k] || k}</dt>
                  <dd>{caliberValues[String(v)] || String(v)}</dd>
                </div>
              ))}
          </dl>
        ) : null}
        <p className="muted">依据：{c.evidence_id || "待核验"}</p>
      </details>
    </section>
  );
}
export function PlanPanel({
  thread,
  pending,
  onSave,
  onCount,
  onCreate,
  onPreview,
  onOpenGroup,
}: {
  thread: Thread | null;
  pending: boolean;
  onSave: (p: Plan) => void;
  onCount: () => void;
  onCreate: (name: string) => void;
  onPreview: () => void;
  onOpenGroup: (id: number) => void;
}) {
  const active = thread?.live_plan || thread?.plan;
  const [draft, setDraft] = useState<Plan>();
  const [dirty, setDirty] = useState(false);
  const [version, setVersion] = useState("current");
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    setDraft(active);
    setDirty(false);
    setConfirm(false);
    setVersion("current");
  }, [thread?.thread_id, thread?.revision, active]);
  const historical = version !== "current";
  const shown = historical
    ? thread?.versions.find((p) => String(p.revision) === version)
    : draft;
  const disabled = pending || busy(thread) || historical || thread?.archived;
  const canExecute =
    !!thread?.plan?.valid &&
    !dirty &&
    !historical &&
    !disabled &&
    thread?.status !== "WAITING";
  const items = clauses(shown?.tree);
  const previous = thread?.versions.find(
    (p) => p.revision === (shown?.revision || 1) - 1
  );
  return (
    <aside className="plan-panel" aria-label="圈选方案">
      <div className="panel-heading">
        <div>
          <h2>圈选方案</h2>
          <p>
            {shown
              ? `${items.length} 项条件 · ${
                  dirty ? "有未保存修改" : `版本 ${shown.revision || "草稿"}`
                }`
              : "条件会随对话逐步整理"}
          </p>
        </div>
        {thread?.versions.length ? (
          <select
            aria-label="方案版本"
            value={version}
            onChange={(e) => {
              setVersion(e.target.value);
              setConfirm(false);
            }}
          >
            <option value="current">当前方案</option>
            {thread.versions.map((p) => (
              <option key={p.revision} value={p.revision}>
                v{p.revision}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <div className="plan-scroll">
        {shown?.plan_status ? <p className="plan-state" role="status">{planStateText[shown.plan_status] || "方案待核验"}</p> : null}
        {shown?.intent_plan?.requirements?.length ? <details className="evidence">
          <summary>原始业务要求</summary>
          {shown.intent_plan.requirements.map((r) => <p key={r.requirement_id}>{r.business_meaning}</p>)}
        </details> : null}
        {shown?.tree ? (
          <>
            <TreeEditor
              tree={shown.tree}
              disabled={disabled}
              onChange={(tree) => {
                setDraft({ ...shown, tree, valid: false });
                setDirty(true);
                setConfirm(false);
              }}
            />
            {(shown.diagnostics || shown.validation_errors)?.length ? (
              <div className="inline-warning">
                <strong>{shown.plan_status === "NEEDS_DECISION" ? "需要你决定" : "尚未完成的条件"}</strong>
                {(shown.diagnostics || shown.validation_errors || []).map((e, i) => (
                  <div key={i}><p>{e.message}</p>{e.expected || e.actual ? <details className="evidence"><summary>查看口径差异</summary><p>要求：{JSON.stringify(e.expected)}</p><p>当前证据：{JSON.stringify(e.actual)}</p></details> : null}</div>
                ))}
              </div>
            ) : null}
            {shown.revision ? (
              <details className="version-diff">
                <summary>本版变化</summary>
                {planDiff(previous, shown).map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
              </details>
            ) : null}
            <details className="evidence">
              <summary>版本与技术详情</summary>
              <p>快照：{shown.snapshot_id || "待核验"}</p>
              <p>构建：{shown.build_id || "待核验"}</p>
            </details>
          </>
        ) : (
          <div className="plan-empty">
            <div className="empty-lines" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <p>先描述你想寻找的客户</p>
            <span>
              标签、时间、金额与组合关系
              <br />
              会整理为可编辑的条件。
            </span>
          </div>
        )}
      </div>
      {shown ? (
        <div className="plan-actions">
          {dirty ? (
            <>
              <p className="muted">修改后将重新校验，原人数结果失效。</p>
              <button
                className="primary"
                disabled={disabled}
                onClick={() => draft && onSave(draft)}
              >
                保存并核验修改
              </button>
            </>
          ) : historical ? (
            <button
              disabled={pending || busy(thread) || thread?.status === "WAITING"}
              onClick={() => onSave(shown)}
            >
              以此版本继续圈选
            </button>
          ) : (
            <>
              <div className="count-result">
                {thread?.count && thread.count.revision === thread.revision ? (
                  <>
                    <strong>
                      {thread.count.value.toLocaleString()}
                      <small> 人</small>
                    </strong>
                    <span>
                      统计于{" "}
                      {new Date(thread.count.executed_at).toLocaleString(
                        "zh-CN"
                      )}
                    </span>
                    <span>
                      数据时点：{thread.count.data_as_of || "数据源未提供"}
                    </span>
                    {thread.count.warning ? (
                      <p>{thread.count.warning}</p>
                    ) : null}
                  </>
                ) : (
                  <span>
                    {canExecute
                      ? "条件已校验，尚未统计人数"
                      : "完成条件核验后可统计人数"}
                  </span>
                )}
              </div>
              <div className="action-row">
                <button
                  disabled={!canExecute || !thread?.capabilities.count}
                  onClick={onCount}
                >
                  统计人数
                </button>
                <button
                  disabled={!canExecute || !thread?.capabilities.preview}
                  onClick={onPreview}
                >
                  查看样例
                </button>
              </div>
              {thread?.execution &&
              thread.execution.revision === thread.revision ? (
                <button
                  className="primary"
                  onClick={() => onOpenGroup(thread.execution!.group_id)}
                >
                  打开已创建客群
                </button>
              ) : (
                <button
                  className="primary"
                  disabled={!canExecute || !thread?.capabilities.create}
                  onClick={() => setConfirm(!confirm)}
                >
                  创建客群
                </button>
              )}
              {confirm ? (
                <div className="create-form">
                  <label className="field-label">
                    客群名称
                    <input
                      autoFocus
                      value={name}
                      maxLength={100}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="输入便于识别的名称"
                    />
                  </label>
                  <p>
                    将按当前 v{thread?.revision} 的 {items.length}{" "}
                    项条件创建客群。
                  </p>
                  <div className="action-row">
                    <button onClick={() => setConfirm(false)}>取消</button>
                    <button
                      className="primary"
                      disabled={!name.trim() || pending}
                      onClick={() => onCreate(name.trim())}
                    >
                      确认创建
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </aside>
  );
}
