import { test, expect } from "@playwright/test";
import fs from "node:fs";

test("合成报告桌面：SVG、PNG 和抑制格的导出与数据表一致", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let apiCalls = 0;
  page.on("request", (request) => { if (request.url().includes("/dev-api/")) apiCalls++; });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/agent-ui/?insightPreview=1");
  await expect(page.getByRole("heading", { name: "大额入金转化 · 合成客群" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("实际取数结果");
  const asset = page.getByRole("region", { name: "资产结构 · 金额加权占比", exact: true });
  await expect(asset.locator("svg")).toBeVisible();
  const svgDownload = page.waitForEvent("download");
  await asset.getByRole("button", { name: "导出 SVG", exact: true }).click();
  const svg = await svgDownload;
  expect(svg.suggestedFilename()).toBe("asset_mix-synthetic.svg");
  const svgBody = fs.readFileSync((await svg.path())!, "utf-8");
  expect(svgBody).toContain("<svg"); expect(svgBody).toContain("合成数据"); expect(svgBody).toContain("2026-09-28");
  const metadata = await page.evaluate((body) => {
    const xml = new DOMParser().parseFromString(body, "image/svg+xml");
    return JSON.parse(xml.querySelector("metadata")!.textContent!);
  }, svgBody);
  expect(metadata.spec.series.map((s: { points: { value: number }[] }) => s.points.map((p) => p.value))).toEqual([[60, 39], [20, 31], [20, 30]]);
  expect(metadata.facts.find((f: { id: string }) => f.id === "liquid_share").value).toBe(60);
  const pngDownload = page.waitForEvent("download");
  await asset.getByRole("button", { name: "导出 PNG", exact: true }).click();
  const png = await pngDownload;
  expect(fs.readFileSync((await png.path())!).subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  const kpi = page.getByRole("region", { name: "客户数", exact: true });
  const kpiDownload = page.waitForEvent("download");
  await kpi.getByRole("button", { name: "导出 SVG", exact: true }).click();
  expect(fs.readFileSync((await (await kpiDownload).path())!, "utf-8")).toContain("240人");
  await page.getByRole("button", { name: "产品缺口", exact: true }).click();
  const heatmap = page.getByRole("region", { name: "品类与 AUM 层级缺口 · 稀疏格隐藏", exact: true });
  await expect(heatmap.locator("svg")).toBeVisible();
  await expect(heatmap.getByText("正值表示低于基准，负值表示高于基准；空白格已抑制或缺少数据。")).toBeVisible();
  const heatmapDownload = page.waitForEvent("download");
  await heatmap.getByRole("button", { name: "导出 SVG", exact: true }).click();
  const heatmapSvg = fs.readFileSync((await (await heatmapDownload).path())!, "utf-8");
  if (process.env.CAPTURE_DIR) fs.writeFileSync(`${process.env.CAPTURE_DIR}/insight-heatmap-export.svg`, heatmapSvg);
  const exportedLabels = await page.evaluate((body) => [...new DOMParser().parseFromString(body, "image/svg+xml").querySelectorAll("text")].map((el) => el.textContent).join(" "), heatmapSvg);
  expect(exportedLabels).toContain("pp");
  expect(exportedLabels).toContain("正值表示低于基准");
  await heatmap.getByText("查看图表数据与抑制状态").click();
  await expect(heatmap.getByRole("cell", { name: "已抑制", exact: true })).toBeVisible();
  const table = page.getByRole("region", { name: "品类缺口汇总", exact: true });
  const tableDownload = page.waitForEvent("download");
  await table.getByRole("button", { name: "导出 SVG", exact: true }).click();
  expect(fs.readFileSync((await (await tableDownload).path())!, "utf-8")).toContain("50pp");
  await page.getByRole("button", { name: "机会排序", exact: true }).click();
  await expect(page.getByText("假设：价值与产品缺口共同构成优先级信号。")).toBeVisible();
  await expect(page.getByText(/未经响应数据校准/)).toBeVisible();
  expect(apiCalls).toBe(0); expect(errors).toEqual([]);
  if (process.env.CAPTURE_DIR) {
    fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
    await page.getByRole("button", { name: "资产结构", exact: true }).click();
    await page.locator(".insight-preview").evaluate((el) => { el.scrollTop = 0; });
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/insight-desktop.png`, fullPage: true });
    await asset.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/insight-desktop-chart.png` });
  }
});

test("合成报告手机：分段、过期提示与导出权限", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/agent-ui/?insightPreview=1");
  await expect(page.getByRole("heading", { name: "大额入金转化 · 合成客群" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (process.env.CAPTURE_DIR) {
    fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/insight-mobile-asset.png`, fullPage: true });
  }
  await page.getByRole("button", { name: "产品缺口", exact: true }).click();
  await expect(page.getByRole("heading", { name: "理财持仓缺口", exact: true })).toBeVisible();
  if (process.env.CAPTURE_DIR) {
    fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/insight-mobile.png`, fullPage: true });
    const heatmap = page.getByRole("region", { name: "品类与 AUM 层级缺口 · 稀疏格隐藏", exact: true });
    await heatmap.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/insight-mobile-chart.png` });
  }
  await page.getByRole("button", { name: "模拟方案变更", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "已过期" })).toBeVisible();
  for (const button of await page.getByRole("button", { name: /导出 SVG|导出 PNG|复制本段摘要/ }).all()) await expect(button).toBeDisabled();
  await page.getByRole("button", { name: "恢复原方案版本", exact: true }).click();
  await expect(page.getByRole("button", { name: "复制本段摘要" })).toBeEnabled();
});
