import { describe, expect, it } from "vitest";
import data from "./synthetic-preview.json";
import type { ChartSpec, InsightReport } from "./types";
import { formatFact, isReportStale, statementText } from "./types";
import { validateChartSpec } from "./chartGuard";
import { toEChartsOption } from "./echartsAdapter";

const report = data as InsightReport;
const asset = report.results[0], gap = report.results[1], priority = report.results[2];
describe("洞察共享协议与展示 Guard", () => {
  it("三个合成 Skill 的每个图表通过再次校验", () => {
    for (const skill of report.results) for (const spec of skill.charts) expect(() => validateChartSpec(spec, skill.facts)).not.toThrow();
  });
  it("叙述引用事实，保留单位", () => {
    expect(statementText(asset.cards[0].facts, asset.facts)).toBe("客群 240人，总 AUM 120,000,000元。");
    expect(formatFact(gap.facts.find((f) => f.id === "sparse_cell")!)).toBe("已抑制");
  });
  it("revision 或 plan hash 变化使报告过期", () => {
    expect(isReportStale(report, 1, "a".repeat(64))).toBe(false);
    expect(isReportStale(report, 2, "a".repeat(64))).toBe(true);
    expect(isReportStale(report, 1, "b".repeat(64))).toBe(true);
  });
  it.each([
    (s: ChartSpec) => { s.series[0].points[0].value = 999; },
    (s: ChartSpec) => { (s as unknown as Record<string, unknown>).formatter = "function(){}"; },
    (s: ChartSpec) => { (s as unknown as Record<string, unknown>).kind = "radar"; },
    (s: ChartSpec) => { s.series[0].fact_ids = ["not_existing"]; },
    (s: ChartSpec) => { s.title = "<img onerror=alert(1)>"; },
  ])("拒绝篡改数字、额外 option、图型和证据", (modify) => {
    const spec = structuredClone(asset.charts[0]); modify(spec);
    expect(() => validateChartSpec(spec, asset.facts)).toThrow();
  });
  it("抑制格不可携带数值或精确样本量", () => {
    const facts = structuredClone(gap.facts), spec = gap.charts.find((s) => s.kind === "heatmap")!;
    facts.find((f) => f.id === "sparse_cell")!.sample_size = 12;
    expect(() => validateChartSpec(spec, facts)).toThrow("抑制格泄露数值");
  });
  it("百分比缺少分母时拒绝渲染", () => {
    const facts = structuredClone(asset.facts), spec = asset.charts.find((s) => s.kind === "stacked_bar")!;
    facts.find((f) => f.id === "liquid_share")!.denominator_id = null;
    expect(() => validateChartSpec(spec, facts)).toThrow("百分比缺少分母");
  });
  it("占比对账和漏斗顺序不能放宽", () => {
    const stack = structuredClone(asset.charts.find((s) => s.kind === "stacked_bar")!);
    stack.reconcile = [];
    expect(() => validateChartSpec(stack, asset.facts)).toThrow("分组对账");
    const funnel = structuredClone(gap.charts.find((s) => s.kind === "funnel")!);
    funnel.reconcile[0].fact_ids.reverse();
    expect(() => validateChartSpec(funnel, gap.facts)).toThrow("漏斗未逐步减少");
  });
});
describe("ECharts 适配器稳定输出", () => {
  for (const skill of report.results) for (const spec of skill.charts.filter((s) => s.kind !== "table" && s.kind !== "kpi")) {
    it(`${skill.skill_id}/${spec.id} snapshot`, () => {
      const option = toEChartsOption(spec, skill.facts, true);
      expect(option).toMatchSnapshot();
      expect(option.animation).toBe(false);
    });
  }
  it("热力图只下发可用格，缺失值不填零", () => {
    const spec = gap.charts.find((s) => s.kind === "heatmap")!;
    const option = toEChartsOption(spec, gap.facts, true);
    const rows = (option.series as { data: unknown[] }[])[0].data;
    expect(rows).toEqual([[0, 0, 50], [0, 1, 12.5], [0, 2, -2.5]]);
    expect(rows).toHaveLength(3);
  });
  it("负分贡献不被零下限裁切，轴仍包含零基线", () => {
    const option = toEChartsOption(priority.charts.find((s) => s.id === "contributions")!, priority.facts, true);
    expect((option.xAxis as { min: number }).min).toBe(-10);
  });
});
