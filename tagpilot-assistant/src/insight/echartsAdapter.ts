import type { EChartsCoreOption } from "echarts/core";
import type { ChartSpec, Fact } from "./types";
import { statementText } from "./types";
import { validateChartSpec } from "./chartGuard";

export function chartExplanation(spec: ChartSpec): string {
  return spec.kind === "heatmap" && spec.unit === "pp"
    ? "正值表示低于基准，负值表示高于基准；空白格已抑制或缺少数据。"
    : "";
}

export function toEChartsOption(spec: ChartSpec, facts: Fact[], reducedMotion = false): EChartsCoreOption {
  validateChartSpec(spec, facts);
  if (spec.kind === "kpi" || spec.kind === "table") throw new Error("KPI 和表格使用语义 HTML 渲染");
  const labels = [...new Set(spec.series.flatMap((s) => s.points.map((p) => p.category)))];
  const numericValues = spec.series.flatMap((s) => s.points.flatMap((p) => p.value === null ? [] : [p.value]));
  const base: EChartsCoreOption = {
    animation: !reducedMotion,
    animationDuration: 180,
    color: ["#365e85", "#738ca6", "#a3b6c9", "#677861", "#b4bdb0", "#7c7185"],
    // ECharts 5.4 的 SVG style 序列化不会转义字族内的引号，使用等价的无引号 CSS 字族。
    textStyle: { fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, sans-serif", fontSize: 12, color: "#24272c" },
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: spec.kind === "heatmap" || spec.kind === "funnel" ? "item" : "axis", renderMode: "richText", confine: true },
    legend: { bottom: 0, type: "scroll" },
  };
  const footnotes = spec.annotations.map((a) => statementText(a, facts)).join("；");
  if (footnotes) base.title = { subtext: footnotes, left: 8, top: 0, subtextStyle: { color: "#68717d" } };
  if (spec.kind === "funnel") return {
    ...base, color: ["#365e85", "#44617c", "#526979", "#596577", "#606a73", "#626d62"], legend: { show: false },
    series: [{ type: "funnel", left: "12%", width: "72%", top: 15, bottom: 24, sort: "none", min: 0,
      max: Math.max(0, ...numericValues), label: { position: "inside", color: "#fff", formatter: "{b}: {c}人" },
      data: spec.series[0].points.map((p) => ({ name: p.category, value: p.value })) }],
  };
  if (spec.kind === "heatmap") {
    const columns = [...new Set(spec.series[0].points.map((p) => p.column!))];
    // 已抑制格完全不进入 ECharts 数据集、tooltip 或导出。
    const visible = spec.series[0].points.filter((p) => p.value !== null);
    const min = Math.min(0, ...numericValues), max = Math.max(1, ...numericValues);
    return { ...base, title: { text: `${spec.metric_label}（${spec.unit}）`, left: 8, top: 0, textStyle: { fontSize: 12, fontWeight: "normal" } },
      legend: { show: false }, grid: { top: 45, left: 12, right: 24, bottom: 65, containLabel: true },
      xAxis: { type: "category", data: columns, axisLabel: { interval: 0, width: 100, overflow: "break" } },
      yAxis: { type: "category", data: labels },
      visualMap: { min, max, text: [`${max}${spec.unit}`, `${min}${spec.unit}`], orient: "horizontal", bottom: 0, left: "center", calculable: false, inRange: { color: ["#edf0f4", "#9fb3c7", "#365e85"] } },
      series: [{ name: `${spec.metric_label}（${spec.unit}）`, type: "heatmap", label: { show: true, formatter: `{@[2]}${spec.unit}` },
        data: visible.map((p) => [columns.indexOf(p.column!), labels.indexOf(p.category), p.value]), emphasis: { itemStyle: { borderColor: "#24272c", borderWidth: 1 } } }],
    };
  }
  const horizontal = spec.orientation === "horizontal";
  const categoryAxis = { type: "category", data: labels, axisLabel: { interval: 0, width: horizontal ? 90 : 110, overflow: "break" }, axisTick: { show: false } };
  const valueAxis = { type: "value", min: Math.min(0, ...numericValues), ...(spec.unit === "%" ? { max: 100 } : {}), name: `${spec.metric_label}（${spec.unit}）`, nameLocation: "middle", nameGap: 28, splitLine: { lineStyle: { color: "#e7e9ed" } } };
  return { ...base, grid: { left: 12, right: 28, top: footnotes ? 55 : 24, bottom: 66, containLabel: true },
    xAxis: horizontal ? valueAxis : categoryAxis, yAxis: horizontal ? { ...categoryAxis, inverse: true } : valueAxis,
    series: spec.series.map((s) => ({ name: s.name, type: "bar", ...(spec.kind === "stacked_bar" ? { stack: "composition" } : {}),
      barMaxWidth: 32, data: labels.map((category) => s.points.find((p) => p.category === category)?.value ?? null),
      emphasis: { focus: "series" } })),
  };
}
