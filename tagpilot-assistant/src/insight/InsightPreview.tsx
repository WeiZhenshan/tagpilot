import { useState } from "react";
import data from "./synthetic-preview.json";
import type { InsightReport } from "./types";
import { InsightReportPanel } from "./InsightReportPanel";

// 仅开发模式加载；没有业务网络请求，也不向模型发送任何数据。
export default function InsightPreview() {
  const report = data as InsightReport;
  const [changed, setChanged] = useState(false);
  return <main className="insight-preview"><div className="insight-preview-tools"><a href="/agent-ui/">返回圈选工作台</a><button type="button" aria-pressed={changed} onClick={() => setChanged((v) => !v)}>{changed ? "恢复原方案版本" : "模拟方案变更"}</button></div><InsightReportPanel report={report} currentRevision={report.cohort.revision + (changed ? 1 : 0)} currentPlanHash={report.cohort.plan_hash} /></main>;
}
