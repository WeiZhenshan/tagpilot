import { describe, expect, it } from "vitest";
import fixtureData from "../../../ruoyi-taglibrary/src/test/resources/agent/diagnostic-baseline-run.json";
import type { ChartSpec, Fact } from "./types";
import { statementText } from "./types";
import { validateChartSpec } from "./chartGuard";
import { toEChartsOption } from "./echartsAdapter";

// 真实模型输出回归：带对照客群的诊断报告（服务端校验后的事实/卡片/图表）必须能通过前端 Guard 渲染。
const fixture = fixtureData as { skill_result: { facts: Fact[]; charts: ChartSpec[]; cards: unknown[] } };
const facts = fixture.skill_result.facts;
const charts = fixture.skill_result.charts;
const cards = fixture.skill_result.cards as { facts: Statement; comparison: Statement; diagnosis: Statement; action: Statement }[];
type Statement = { text: string; fact_ids: string[] };

// 服务端（TsAgentWorkbenchService.skillStatement）会把陈述里引用到、但模型漏登记进 fact_ids 的可用事实按引用补齐；前端拿到的是补齐后的报告。
const ref = /\{fact:([a-z][a-z0-9_.-]{0,79})\}/g;
const available = new Set(facts.filter((fact) => fact.status === "AVAILABLE").map((fact) => fact.id));
function likeServer(card: (typeof cards)[number]) {
  return [card.facts, card.comparison, card.diagnosis, card.action].map((segment) => ({
    ...segment,
    fact_ids: [...new Set([...(segment.fact_ids || []), ...[...segment.text.matchAll(ref)].map((match) => match[1])].filter((id) => available.has(id)))],
  }));
}

describe("真实诊断报告的前端渲染回归", () => {
  it("每张图表通过再次校验并生成 ECharts option", () => {
    expect(charts).toHaveLength(4);
    for (const spec of charts) {
      expect(() => validateChartSpec(spec, facts)).not.toThrow();
      if (spec.kind === "kpi" || spec.kind === "table") continue;
      const option = toEChartsOption(spec, facts) as { series?: unknown[] };
      expect(option.series?.length).toBeGreaterThan(0);
    }
  });
  it("每段陈述都能把事实占位符替换为带单位数值", () => {
    for (const card of cards)
      for (const segment of likeServer(card)) expect(statementText(segment, facts)).not.toContain("{fact:");
  });
});
