import { apiRequest } from "./api";

/** 技能摘要（引擎 Manifest.summary，经 Java 治理层按权限收敛后下发） */
export type SkillSummary = {
  skill_id: string;
  name: string;
  category: string;
  layer: string;
  version: string;
  status: string;
  owner: string;
  description: string;
  applicable_objects?: string[];
  default_benchmark?: string;
  required_permissions?: string[];
  human_review_required?: boolean;
  updated_at?: string;
};

export type SkillEvidence = {
  evidence_id: string;
  kind?: string;
  metric_id?: string;
  text: string;
  value?: number | string | null;
  unit?: string;
  rule?: string;
  source?: string;
  data_as_of?: string;
};

export type InsightCard = {
  card_id: string;
  title: string;
  fact: { text: string; metric_ids?: string[]; evidence_ids?: string[] };
  benchmark?: {
    text: string;
    benchmark_id?: string;
    benchmark_name?: string;
    evidence_ids?: string[];
  } | null;
  diagnosis: { text: string; type?: string; confidence?: number };
  action: {
    eligible_customer_count?: number;
    priority?: string;
    recommendation?: string;
    rule_ids?: string[];
  };
  boundary: { text: string; data_as_of?: string; sample_size?: number };
  provenance?: {
    skill_id?: string;
    skill_version?: string;
    data_as_of?: string;
    trace_id?: string;
  };
};

export type ChartField = {
  field: string;
  semantic_type?: string;
  role?: string;
  metric_id?: string;
  unit?: string;
};

export type ChartSpec = {
  chart_id: string;
  intent?: string;
  chart_skill?: string;
  title: string;
  subtitle?: string;
  fields: ChartField[];
  rows: Record<string, unknown>[];
  view: { mark: string; orientation?: string; encoding?: Record<string, string> };
  annotations?: {
    type?: string;
    category?: string;
    text?: string;
    evidence_id?: string;
  }[];
  accessibility?: { summary?: string; data_table?: boolean };
  provenance?: { skill_id?: string; skill_version?: string; data_as_of?: string };
};

export type SkillRunResult = {
  run_id?: string;
  skill_id: string;
  skill_version?: string;
  status: string;
  blocked_reason?: string | null;
  started_at?: string;
  duration_ms?: number;
  audience?: {
    audience_id?: string;
    name?: string;
    customer_count?: number;
    as_of_date?: string;
    benchmark_type?: string;
    benchmark_name?: string;
    benchmark_customer_count?: number;
  };
  metrics?: Record<string, Record<string, unknown>>;
  insight_cards: InsightCard[];
  charts: ChartSpec[];
  evidence: SkillEvidence[];
  validations?: { name: string; passed: boolean; detail: string }[];
  chart_validations?: { name: string; passed: boolean; detail: string }[];
  data_as_of?: string;
  trace_id?: string;
};

type AjaxPayload<T> = { code?: number; msg?: string; data?: T };

/** 可选基准：与引擎 BENCHMARK_LABELS 保持一致 */
export const BENCHMARK_OPTIONS = [
  { value: "ALL_BRANCH", label: "全行客户" },
  { value: "SAME_AUM_BAND", label: "同 AUM 层级客户" },
  { value: "SAME_RISK_LEVEL", label: "同风险等级客户" },
] as const;

export const layerText: Record<string, string> = {
  L1: "L1 事实",
  L2: "L2 诊断",
  L3: "L3 行动",
};

export const statusText: Record<string, string> = {
  published: "已发布",
  draft: "草稿",
  offline: "已下线",
  deprecated: "已废弃",
};

export const priorityText: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

/** 已发布技能列表（Java 治理代理，浏览器不直连 Python 引擎） */
export async function listSkills(keyword?: string): Promise<SkillSummary[]> {
  const query = new URLSearchParams({ status: "published", limit: "100" });
  if (keyword && keyword.trim()) query.set("keyword", keyword.trim());
  const payload = await apiRequest<AjaxPayload<{ items?: SkillSummary[] }>>(
    `/taglibrary/skill/list?${query.toString()}`
  );
  const items = payload.data?.items || [];
  return items.filter((item) => item && item.skill_id);
}

/** 对指定客群运行技能；成员名单由后端解析，前端只传客群与基准 */
export async function runSkill(
  skillId: string,
  body: { groupId: number; benchmarkType?: string; asOfDate?: string }
): Promise<SkillRunResult> {
  const payload = await apiRequest<AjaxPayload<SkillRunResult>>(
    `/taglibrary/skill/${encodeURIComponent(skillId)}/run`,
    {
      method: "POST",
      body: JSON.stringify({
        groupId: body.groupId,
        benchmarkType: body.benchmarkType || undefined,
        asOfDate: body.asOfDate || undefined,
      }),
    }
  );
  const result = payload.data;
  if (!result) throw new Error("技能引擎未返回结果");
  return result;
}
