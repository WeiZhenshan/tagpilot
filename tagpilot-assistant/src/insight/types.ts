// 与 tagpilot-insight 导出的 InsightReport.schema.json 对应；不接受原始 ECharts option。
export type Fact = {
  id: string;
  metric: string;
  label: string;
  value: number | null;
  unit: "人" | "元" | "%" | "pp" | "分";
  sample_size: number | null;
  status: "AVAILABLE" | "SUPPRESSED" | "MISSING";
  query_id: string;
  evidence: string[];
  denominator_id: string | null;
  derived_from: string[];
  role: "OBSERVED" | "BENCHMARK" | "POST_EXCLUSION" | "DERIVED";
  exclusions_applied: string[];
  calculation?: "DIRECT" | "RATIO" | "WEIGHTED";
  weights?: Record<string, number>;
};
export type ChartKind = "kpi" | "table" | "bar" | "stacked_bar" | "heatmap" | "funnel";
export type ChartIntent = "single_value" | "compare_categories" | "show_composition" | "show_distribution" | "show_matrix" | "show_conversion";
export type ChartPoint = { category: string; column: string | null; fact_id: string; value: number | null };
export type ChartSeries = { name: string; fact_ids: string[]; points: ChartPoint[] };
export type ChartSpec = {
  schema_version: 1;
  id: string;
  title: string;
  kind: ChartKind;
  intent: ChartIntent;
  unit: Fact["unit"];
  metric_label: string;
  series: ChartSeries[];
  annotations: { text: string; fact_ids: string[] }[];
  reconcile: { kind: "sum" | "percentage" | "funnel"; fact_ids: string[]; total_fact_id: string | null; tolerance: number }[];
  zero_baseline: true;
  orientation: "horizontal" | "vertical";
};
export type Statement = { text: string; fact_ids: string[] };
export type InsightCard = {
  id: string;
  title: string;
  facts: Statement;
  comparison: Statement & { benchmark_fact_ids: string[]; difference_fact_ids: string[] };
  diagnosis: Statement & { basis: "RULE" | "STAT" | "HYPOTHESIS"; statistical_evidence?: { method: string; cohort_rate_id:string; benchmark_rate_id:string; cohort_interval:number[]; benchmark_interval:number[]; threshold_pp:number } | null };
  action: Statement & { population_fact_id: string | null; priority: "HIGH" | "MEDIUM" | "LOW" | "NONE" };
  boundary: { text: string; data_as_of: string; skill_version: string; sample_fact_id: string; metric_definitions: string[] };
};
export type SkillResult = {
  registry_version?: string | null;
  definition_hash?: string | null;
  skill_id: string;
  skill_version: string;
  pack_hash: string;
  status: "COMPLETE" | "PARTIAL" | "BLOCKED";
  level: "L2" | "L3" | "L4" | null;
  reasons: string[];
  facts: Fact[];
  cards: InsightCard[];
  charts: ChartSpec[];
};
export type InsightReport = {
  level?: "L2" | "L3" | "L4" | null;
  schema_version: 1;
  run_id: string;
  cohort: {
    audience_id: string;
    audience_name: string;
    library_id: number;
    revision: number;
    plan_hash: string;
    snapshot_id: string;
    count: number;
    data_as_of: string;
    reference_date: string;
    binding_version: string;
    declared_context: string;
    synthetic: boolean;
  };
  results: SkillResult[];
};

export function isReportStale(report: InsightReport, revision: number, planHash: string): boolean {
  return report.cohort.revision !== revision || report.cohort.plan_hash !== planHash;
}

export function formatFact(fact: Fact): string {
  if (fact.status !== "AVAILABLE" || fact.value === null) return fact.status === "SUPPRESSED" ? "已抑制" : "待补充";
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(fact.value)}${fact.unit}`;
}

export function statementText(statement: Statement, facts: Fact[]): string {
  const index = new Map(facts.map((fact) => [fact.id, fact]));
  return statement.text.replace(/\{fact:([a-z][a-z0-9_.-]{0,79})\}/g, (_, id: string) => {
    const fact = index.get(id);
    if (!fact || !statement.fact_ids.includes(id) || fact.status !== "AVAILABLE") throw new Error("叙述引用无效事实");
    return formatFact(fact);
  });
}
