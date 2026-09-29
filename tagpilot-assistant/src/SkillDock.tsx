import { useEffect, useRef, useState } from "react";
import type { Thread } from "./agentTypes";
import { ChartFigure } from "./SkillChart";
import {
  BENCHMARK_OPTIONS,
  layerText,
  listSkills,
  priorityText,
  runSkill,
  type InsightCard,
  type SkillRunResult,
  type SkillSummary,
} from "./skillApi";

type RunState = {
  key: string;
  skillId: string;
  name: string;
  status: "running" | "succeeded" | "failed";
  error?: string;
  result?: SkillRunResult;
};

const diagnosisText: Record<string, string> = {
  rule_based_inference: "规则推断",
  model_explanation: "模型解释",
  descriptive: "描述统计",
};

function InsightCardView({ card }: { card: InsightCard }) {
  return (
    <article className="insight-card">
      <h4>{card.title}</h4>
      <dl>
        <div>
          <dt>事实</dt>
          <dd>{card.fact.text}</dd>
        </div>
        {card.benchmark?.text ? (
          <div>
            <dt>对比</dt>
            <dd>
              {card.benchmark.benchmark_name ? (
                <em className="insight-benchmark">
                  基准：{card.benchmark.benchmark_name}
                </em>
              ) : null}
              {card.benchmark.text}
            </dd>
          </div>
        ) : null}
        <div>
          <dt>诊断</dt>
          <dd>
            <span className="insight-tag">
              {diagnosisText[card.diagnosis.type || ""] || card.diagnosis.type}
            </span>
            {card.diagnosis.text}
          </dd>
        </div>
        {card.action?.recommendation ? (
          <div>
            <dt>行动</dt>
            <dd>
              {card.action.priority ? (
                <span className={`insight-priority ${card.action.priority}`}>
                  优先级：{priorityText[card.action.priority] || card.action.priority}
                </span>
              ) : null}
              {card.action.recommendation}
              {card.action.eligible_customer_count ? (
                <small>
                  可触达 {card.action.eligible_customer_count.toLocaleString()} 人
                </small>
              ) : null}
            </dd>
          </div>
        ) : null}
        <div>
          <dt>边界</dt>
          <dd>
            {card.boundary.text}
            {card.boundary.sample_size ? (
              <small>样本 {card.boundary.sample_size} 人</small>
            ) : null}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function ResultView({ run }: { run: RunState }) {
  const result = run.result;
  if (run.status === "failed")
    return (
      <div className="skill-result failed" role="alert">
        <div className="skill-result-head">
          <strong>{run.name}</strong>
          <span className="skill-badge failed">未产出结果</span>
        </div>
        <p>{run.error}</p>
      </div>
    );
  if (!result)
    return (
      <div className="skill-result running">
        <div className="skill-result-head">
          <strong>{run.name}</strong>
          <span className="skill-badge running">正在运行…</span>
        </div>
        <p className="muted">正在解析客群成员并执行确定性计算。</p>
      </div>
    );
  const audience = result.audience;
  return (
    <div className="skill-result">
      <div className="skill-result-head">
        <strong>{run.name}</strong>
        <span className="skill-badge ok">
          {result.skill_version ? `v${result.skill_version} · ` : ""}
          {result.duration_ms ? `${(result.duration_ms / 1000).toFixed(1)}s` : "已完成"}
        </span>
      </div>
      <p className="skill-meta">
        客群 {audience?.customer_count?.toLocaleString() ?? "—"} 人
        {audience?.benchmark_name
          ? ` · 基准 ${audience.benchmark_name}${
              audience.benchmark_customer_count
                ? `（${audience.benchmark_customer_count.toLocaleString()} 人）`
                : ""
            }`
          : ""}
        {result.data_as_of ? ` · 数据时点 ${result.data_as_of}` : ""}
      </p>
      {result.insight_cards?.length ? (
        <div className="insight-list">
          {result.insight_cards.map((card) => (
            <InsightCardView key={card.card_id} card={card} />
          ))}
        </div>
      ) : null}
      {result.charts?.length ? (
        <div className="chart-list">
          {result.charts.map((chart) => (
            <ChartFigure key={chart.chart_id} spec={chart} />
          ))}
        </div>
      ) : null}
      <div className="skill-fold">
        <details>
          <summary>运行校验（{result.validations?.length || 0} 项）</summary>
          <ul className="validation-list">
            {(result.validations || []).map((item, i) => (
              <li key={i} data-passed={item.passed}>
                <span>{item.passed ? "通过" : "未通过"}</span>
                <strong>{item.name}</strong>
                <em>{item.detail}</em>
              </li>
            ))}
          </ul>
        </details>
        <details>
          <summary>证据（{result.evidence?.length || 0} 条）</summary>
          <ul className="evidence-list">
            {(result.evidence || []).map((item) => (
              <li key={item.evidence_id}>
                <code>{item.evidence_id}</code>
                {item.text}
                {item.value !== null && item.value !== undefined ? (
                  <small>
                    {String(item.value)}
                    {item.unit || ""}
                  </small>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </div>
  );
}

export function SkillDock({
  thread,
  disabled,
  pending,
  onError,
}: {
  thread: Thread | null;
  disabled: boolean;
  pending: boolean;
  onError: (message: string) => void;
}) {
  const [catalog, setCatalog] = useState<SkillSummary[] | null>(null);
  const [open, setOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [selected, setSelected] = useState<SkillSummary[]>([]);
  const [runs, setRuns] = useState<RunState[]>([]);
  const [running, setRunning] = useState(false);
  const [benchmark, setBenchmark] = useState("AUTO");
  const loaded = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  // 切换圈选会话即切换目标客群，已添加的技能与运行结果不跨会话沿用
  useEffect(() => {
    setRuns([]);
    setSelected([]);
    setOpen(false);
  }, [thread?.thread_id]);

  const revisionMatched =
    !!thread?.execution && thread.execution.revision === thread?.revision;
  const groupId = revisionMatched ? thread?.execution?.group_id : undefined;
  const busy = running || pending;

  async function ensureCatalog() {
    if (loaded.current && catalog) return;
    try {
      const items = await listSkills();
      if (!alive.current) return;
      setCatalog(items);
      loaded.current = true;
    } catch (e) {
      onError(e instanceof Error ? e.message : "洞察技能列表加载失败");
    }
  }

  async function togglePicker() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    await ensureCatalog();
  }

  const selectedIds = new Set(selected.map((item) => item.skill_id));
  const visible = (catalog || []).filter((item) => {
    if (!keyword.trim()) return true;
    const needle = keyword.trim().toLowerCase();
    return `${item.name}${item.skill_id}${item.description}`
      .toLowerCase()
      .includes(needle);
  });

  function toggle(item: SkillSummary) {
    setSelected((list) =>
      selectedIds.has(item.skill_id)
        ? list.filter((v) => v.skill_id !== item.skill_id)
        : [...list, item]
    );
  }

  async function runAll() {
    if (!groupId || !selected.length || busy) return;
    const stamp = Date.now();
    const queue: RunState[] = selected.map((item, i) => ({
      key: `${item.skill_id}-${stamp}-${i}`,
      skillId: item.skill_id,
      name: item.name,
      status: "running",
    }));
    setRuns(queue);
    setRunning(true);
    for (const task of queue) {
      try {
        const result = await runSkill(task.skillId, {
          groupId,
          benchmarkType: benchmark === "AUTO" ? undefined : benchmark,
        });
        if (!alive.current) return;
        setRuns((list) =>
          list.map((item) =>
            item.key === task.key ? { ...item, status: "succeeded", result } : item
          )
        );
      } catch (e) {
        if (!alive.current) return;
        const message = e instanceof Error ? e.message : "技能运行失败";
        setRuns((list) =>
          list.map((item) =>
            item.key === task.key ? { ...item, status: "failed", error: message } : item
          )
        );
        onError(`${task.name}：${message}`);
      }
    }
    if (alive.current) setRunning(false);
  }

  const hint = !thread?.plan
    ? "先描述并完成圈选方案，再选择要对客群执行的洞察 Skill"
    : !groupId
    ? "创建客群后即可对客群运行已添加的 Skill"
    : `将对客群 #${groupId} 运行 ${selected.length} 个 Skill`;

  return (
    <section className="skill-dock" aria-label="洞察技能">
      <div className="skill-dock-bar">
        <button
          className="skill-add"
          aria-expanded={open}
          disabled={disabled || busy}
          onClick={() => void togglePicker()}
        >
          <span aria-hidden="true">＋</span> 添加 Skill
        </button>
        <div className="skill-chips">
          {selected.length ? (
            selected.map((item) => (
              <span className="skill-chip" key={item.skill_id}>
                <em>{layerText[item.layer] || item.layer}</em>
                {item.name}
                <button
                  type="button"
                  aria-label={`移除${item.name}`}
                  disabled={busy}
                  onClick={() => toggle(item)}
                >
                  ×
                </button>
              </span>
            ))
          ) : (
            <span className="skill-hint">{hint}</span>
          )}
        </div>
        <label className="skill-benchmark">
          <span>基准</span>
          <select
            aria-label="对比基准"
            value={benchmark}
            disabled={disabled || busy || !selected.length}
            onChange={(e) => setBenchmark(e.target.value)}
          >
            <option value="AUTO">按技能默认</option>
            {BENCHMARK_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary skill-run"
          disabled={disabled || busy || !selected.length || !groupId}
          onClick={() => void runAll()}
        >
          {running ? "正在运行…" : `对客群运行${selected.length ? `（${selected.length}）` : ""}`}
        </button>
      </div>
      {selected.length ? <p className="skill-hint-line">{hint}</p> : null}
      {open ? (
        <div className="skill-picker">
          <div className="skill-picker-head">
            <input
              aria-label="搜索技能"
              placeholder="搜索已发布的洞察技能"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
            <button onClick={() => setOpen(false)}>收起</button>
          </div>
          {catalog === null ? (
            <p className="muted">正在加载技能…</p>
          ) : !visible.length ? (
            <p className="muted">没有匹配的已发布技能。</p>
          ) : (
            <ul className="skill-options">
              {visible.map((item) => (
                <li key={item.skill_id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(item.skill_id)}
                      onChange={() => toggle(item)}
                    />
                    <span>
                      <strong>
                        {item.name}
                        <em className="skill-layer">
                          {layerText[item.layer] || item.layer}
                        </em>
                        {item.human_review_required ? (
                          <em className="skill-review">需人工确认</em>
                        ) : null}
                      </strong>
                      <small>{item.description}</small>
                      <small className="muted">
                        v{item.version} · {item.owner}
                        {item.default_benchmark
                          ? ` · 默认基准 ${
                              BENCHMARK_OPTIONS.find(
                                (option) => option.value === item.default_benchmark
                              )?.label || item.default_benchmark
                            }`
                          : ""}
                      </small>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
      {runs.length ? (
        <div className="skill-results">
          {runs.map((run) => (
            <ResultView key={run.key} run={run} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
