import { apiRequest } from "../api";
import type { Thread } from "../agentTypes";
import type { InsightReport } from "./types";
export type SkillEntry = { manifest: { id: string; name: string; layer: string; question: string; preconditions: { min_sample: number; max_stale_days: number }; metrics: string[] }; pack_hash: string };
export type SkillVersion = { skill_id: string; version: string; status: string; pack_hash: string; definition_json: string };
export type InsightCatalog = { skills: SkillEntry[]; versions: SkillVersion[] };
async function data<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const result = await apiRequest<{ data: T }>(`/taglibrary/insight${path}`, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  return result.data;
}
export const insightCatalog = (library: number) => data<InsightCatalog>(`/${library}/catalog`);
export const runInsight = (thread: Thread, skillIds: string[], parameters: Record<string, unknown> = {}) => data<InsightReport>(`/threads/${thread.thread_id}/run`, "POST", { base_revision: thread.revision, plan_hash: thread.plan?.hash, skill_ids: skillIds, parameters, narrate: true });
export const insightFeedback = (run: string, rating: number, category: string, comment: string) => data(`/runs/${run}/feedback`, "POST", { rating, category, comment });
export const GOLDEN_SKILLS = ["asset_structure_profile", "product_holding_gap", "opportunity_priority"];
export const skillNames: Record<string,string> = { asset_structure_profile: "资产结构", product_holding_gap: "产品缺口", opportunity_priority: "机会排序" };

export type ChartChange = { change: { classification: "view" | "data" | "definition"; parameters?: Record<string,unknown> }; requires_confirmation: boolean; report: InsightReport | null; message: string };
export const editInsight = (thread: Thread, skill: string, chart: string, utterance: string) => data<ChartChange>(`/threads/${thread.thread_id}/edit`, "POST", { base_revision: thread.revision, plan_hash: thread.plan?.hash, skill_id: skill, chart_id: chart, utterance });
export const routeInsight = (thread: Thread, utterance: string) => data<{skills:string[];parameters:Record<string,unknown>}>(`/threads/${thread.thread_id}/route`, "POST", { base_revision: thread.revision, plan_hash: thread.plan?.hash, utterance });

export function insightParameterSummary(parameters: Record<string,unknown>): string {
  const labels:Record<string,string> = {benchmark_type:"比较基准",min_gap_pp:"最小缺口(pp)",min_deviation_pp:"最小偏离(pp)",categories:"品类",recent_contact_days:"近期触达排除(天)",profile:"评分画像"};
  const values:Record<string,string> = {same_aum:"同AUM层级",same_org:"同机构",all_customers:"全部客户",standardized:"结构标准化",wealth:"理财",fund:"基金",insurance:"保险",default_v1:"默认规则假设"};
  return Object.entries(parameters).flatMap(([skill,params]) => params && typeof params === "object" ? Object.entries(params).map(([k,v]) => `${skillNames[skill]} · ${labels[k] || k}：${Array.isArray(v) ? v.map(x => values[String(x)] || String(x)).join("、") : values[String(v)] || String(v)}`) : []).join("；");
}
