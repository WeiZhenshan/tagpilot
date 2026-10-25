import { expect, test } from "@playwright/test";
import type { Thread } from "../src/agentTypes";
import type { AnalysisArtifact } from "../src/insight/analysisTypes";

for (const width of [1440, 390]) test(`对话分析 ${width}：消息内图表、引用改图、来源与历史恢复`, async ({ page }) => {
  await page.setViewportSize({ width, height: 960 });
  const artifact: AnalysisArtifact = {
    id: "synthetic-chart", version: 1, base_revision: 2, snapshot_id: "synthetic-batch", created_at: "2026-10-21T01:00:00Z", context: "合成测试客群 · 按机构统计",
    bundle: { queried_at: "2026-10-21T01:00:00Z", data_as_of: null, quality: { note: "数据日期未知；查询时间不代表业务数据日期" } },
    facts: [
      { id: "f-nanjing", label: "南京客户资产均值", metric: "aum", value: 500000, unit: "元", sample_size: 120, status: "AVAILABLE", query_id: "analysis.a.1", evidence: ["合成测试聚合"], denominator_id: null, derived_from: [], role: "OBSERVED", exclusions_applied: [] },
      { id: "f-suzhou", label: "苏州客户资产均值", metric: "aum", value: 800000, unit: "元", sample_size: 120, status: "AVAILABLE", query_id: "analysis.a.2", evidence: ["合成测试聚合"], denominator_id: null, derived_from: [], role: "OBSERVED", exclusions_applied: [] },
    ],
    spec: { schema_version: 1, id: "synthetic-spec", title: "机构资产均值", kind: "bar", intent: "compare_categories", unit: "元", metric_label: "资产均值", orientation: "vertical", zero_baseline: true, annotations: [], reconcile: [],
      series: [{ name: "当前客群", fact_ids: ["f-nanjing", "f-suzhou"], points: [{ category: "南京", column: null, fact_id: "f-nanjing", value: 500000 }, { category: "苏州", column: null, fact_id: "f-suzhou", value: 800000 }] }] },
  };
  let thread: Thread = {
    thread_id: "analysis-fixture", library_id: 107, title: "合成对话分析", status: "COMPLETED", revision: 2, archived: false, pinned: false,
    plan: { valid: true, hash: "h", tree: { kind: "SCOPE_ALL", clause_id: "all", name: "合成测试范围" } }, messages: [], versions: [], events: [], capabilities: { insight: true, count: true, create: false, preview: false },
  };
  const requests: Record<string, unknown>[] = [];
  await page.route("**/dev-api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/getInfo")) return route.fulfill({ json: { code: 200, user: { userId: 2, userName: "fixture", nickName: "合成测试" } } });
    if (path.endsWith("/library/list")) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: "合成测试库" }] } });
    if (path.endsWith("/skills/available") || path.endsWith("/tags/tree") || path.endsWith("/threads")) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith("/runs") && route.request().method() === "POST") {
      const request = route.request().postDataJSON(); requests.push(request);
      const version = requests.length;
      const currentArtifact = structuredClone(artifact); currentArtifact.version = version;
      if (version > 1) currentArtifact.spec.orientation = "horizontal";
      thread = { ...thread, run_id: `analysis-${version}`, run_profile: "conversation", analysis_artifacts: { ...thread.analysis_artifacts, [`${artifact.id}@${version}`]: currentArtifact }, messages: [
        ...thread.messages, { id: `u-${version}`, role: "user", text: request.message, run_id: `analysis-${version}`, created_at: new Date().toISOString() },
        { id: `a-${version}`, role: "assistant", text: "", run_id: `analysis-${version}`, created_at: new Date().toISOString(), parts: [
          { id: `text-${version}`, type: "text", text: version === 1 ? "苏州客户的资产均值高于南京，可继续比较机构结构。" : "已保留原数据，调整为横向条形图。", version: 1, status: "COMPLETE" },
          { id: `chart-${version}`, type: "chart", artifact_id: artifact.id, artifact_version: version, version: 1, status: "COMPLETE" },
        ] },
      ] };
    }
    return route.fulfill({ json: { code: 200, data: thread } });
  });
  await page.goto("/agent-ui/?libraryId=107&threadId=analysis-fixture");
  const composer = page.getByRole("textbox", { name: "圈选需求或技能调用" });
  await composer.fill("分析这批客户的资产结构，按机构比较");
  await page.getByRole("button", { name: "发送需求" }).click();
  await expect(page.getByText("苏州客户的资产均值高于南京，可继续比较机构结构。")).toBeVisible();
  const original = page.locator('[data-artifact-id="synthetic-chart"][data-artifact-version="1"]');
  await expect(original.locator("svg")).toBeVisible();
  expect(requests[0].intent).toBe("auto"); expect(requests[0].skill_name).toBeUndefined(); expect(requests[0].context_tag_ids).toEqual([]);
  await original.getByRole("button", { name: "查看来源" }).click();
  const detail = page.getByRole("dialog");
  await expect(detail.getByText("数据日期未知；查询时间不代表业务数据日期")).toBeVisible();
  await page.keyboard.press("Escape"); await expect(detail).not.toBeVisible();
  await original.getByRole("button", { name: "放大查看" }).click(); await expect(page.getByRole("dialog").locator("svg")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "关闭", exact: true }).click();
  await original.getByRole("button", { name: "继续分析此图" }).click();
  const cite = page.locator(".composer .analysis-cite");
  await expect(cite).toContainText("机构资产均值");
  await expect(cite).toBeVisible();
  await expect(composer).toBeFocused();
  // 引用落在输入框内：下划线文字令牌，而非输入框外的整行引用条。
  await expect(page.locator(".composer-wrap > .analysis-reference, .analysis-reference")).toHaveCount(0);
  await expect(cite).toHaveCSS("text-decoration-line", "underline");
  await expect(cite).toBeVisible();
  await cite.click();
  await expect(cite).toHaveClass(/is-selected/);
  await page.keyboard.press("Backspace");
  await expect(page.locator(".composer .analysis-cite")).toHaveCount(0);
  await original.getByRole("button", { name: "继续分析此图" }).click();
  await expect(page.locator(".composer .analysis-cite")).toContainText("机构资产均值");
  await composer.fill("改成横向条形图，按金额排序"); await page.getByRole("button", { name: "发送需求" }).click();
  await expect(page.getByText("已保留原数据，调整为横向条形图。")).toBeVisible();
  expect(requests[1].target_artifact_id).toBe("synthetic-chart"); expect(requests[1].target_artifact_version).toBe(1);
  await expect(page.locator(".analysis-chart-block")).toHaveCount(2);
  await page.reload(); await expect(page.locator(".analysis-chart-block")).toHaveCount(2);
  await expect(page.locator(".analysis-chart-block .insight-chart-canvas svg")).toHaveCount(2);
  expect(thread.analysis_artifacts!["synthetic-chart@1"].spec.orientation).toBe("vertical");
  expect(thread.analysis_artifacts!["synthetic-chart@2"].spec.orientation).toBe("horizontal");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (process.env.CAPTURE_DIR) await page.screenshot({ path: `${process.env.CAPTURE_DIR}/tagpilot-conversation-${width}.png`, fullPage: true });
});
