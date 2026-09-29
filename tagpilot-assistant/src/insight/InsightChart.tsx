import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, FunnelChart } from "echarts/charts";
import { AriaComponent, DatasetComponent, GridComponent, LegendComponent, TitleComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer, SVGRenderer } from "echarts/renderers";
import type { ChartSpec, Fact } from "./types";
import { formatFact } from "./types";
import { validateChartSpec } from "./chartGuard";
import { chartExplanation, toEChartsOption } from "./echartsAdapter";

echarts.use([BarChart, HeatmapChart, FunnelChart, AriaComponent, DatasetComponent, GridComponent, LegendComponent, TitleComponent, TooltipComponent, VisualMapComponent, SVGRenderer, CanvasRenderer]);

type Props = { spec: ChartSpec; facts: Fact[]; context: string; stale?: boolean };
const escapeXml = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]!);

function nativeSvg(spec: ChartSpec, facts: Fact[], context: string): string {
  const index = new Map(facts.map((f) => [f.id, f]));
  const rows = spec.series.flatMap((s) => s.points.map((p) => [p.category, s.name, p.column || "", formatFact(index.get(p.fact_id)!)]));
  const header = [spec.title, context];
  const height = 120 + rows.length * 30;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="${height}" viewBox="0 0 720 ${height}" role="img"><title>${escapeXml(spec.title)}</title><desc>${escapeXml(context)}</desc><rect width="720" height="${height}" fill="white"/><g fill="#24272c" font-family="sans-serif" font-size="14">${header.map((t, i) => `<text x="16" y="${28 + i * 24}">${escapeXml(t)}</text>`).join("")}${rows.map((row, i) => row.map((cell, col) => `<text x="${16 + col * 175}" y="${95 + i * 30}">${escapeXml(cell)}</text>`).join("")).join("")}</g></svg>`;
}

function download(url: string, name: string) {
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove();
}

function evidenceSvg(svg: string, spec: ChartSpec, facts: Fact[], context: string): string {
  const ids = new Set(spec.series.flatMap((s) => s.fact_ids));
  // 导出只包含本图聚合事实；抑制格仍为 null，不携带客户明细。
  const evidence = { context, spec, facts: facts.filter((f) => ids.has(f.id)) };
  const result = svg.replace(/(<svg\b[^>]*>)/, `$1<metadata>${escapeXml(JSON.stringify(evidence))}</metadata>`);
  if (new DOMParser().parseFromString(result, "image/svg+xml").querySelector("parsererror")) throw new Error("SVG 导出格式校验失败，请重试");
  return result;
}

async function svgToPng(svg: string): Promise<string> {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image(); img.src = url; await img.decode();
    const canvas = document.createElement("canvas"); canvas.width = img.width * 2; canvas.height = img.height * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("浏览器无法导出 PNG");
    ctx.scale(2, 2); ctx.drawImage(img, 0, 0);
    return canvas.toDataURL("image/png");
  } finally { URL.revokeObjectURL(url); }
}

export function InsightChart({ spec, facts, context, stale = false }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.EChartsType | null>(null);
  const [renderError, setRenderError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const validationError = useMemo(() => {
    try { validateChartSpec(spec, facts); return ""; }
    catch (e) { return e instanceof Error ? e.message : "图表协议非法"; }
  }, [spec, facts]);
  const index = new Map(facts.map((fact) => [fact.id, fact]));
  const native = spec.kind === "kpi" || spec.kind === "table";
  useEffect(() => {
    setRenderError(""); setExportError("");
    if (validationError) return;
    try {
      validateChartSpec(spec, facts);
      if (native || !host.current) return;
      const media = window.matchMedia("(prefers-reduced-motion: reduce)");
      const chart = echarts.init(host.current, undefined, { renderer: "svg" });
      instance.current = chart;
      const update = () => chart.setOption(toEChartsOption(spec, facts, media.matches), { notMerge: true });
      update();
      const observer = new ResizeObserver(() => chart.resize()); observer.observe(host.current);
      media.addEventListener("change", update);
      return () => { observer.disconnect(); media.removeEventListener("change", update); chart.dispose(); instance.current = null; };
    } catch (e) { setRenderError(e instanceof Error ? e.message : "图表校验失败"); }
  }, [spec, facts, native, validationError]);

  async function exportChart(type: "svg" | "png") {
    if (stale || exporting) return;
    setExportError(""); setExporting(true);
    let detached: HTMLDivElement | null = null;
    let chart: echarts.EChartsType | null = null;
    try {
      validateChartSpec(spec, facts);
      let dataUrl: string;
      if (native) {
        const svg = evidenceSvg(nativeSvg(spec, facts, context), spec, facts, context);
        dataUrl = type === "svg" ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` : await svgToPng(svg);
      } else {
        detached = document.createElement("div");
        detached.style.cssText = "position:fixed;left:-10000px;width:720px;height:420px";
        document.body.append(detached);
        chart = echarts.init(detached, undefined, { renderer: type === "svg" ? "svg" : "canvas", width: 720, height: 420 });
        const option = toEChartsOption(spec, facts, true);
        const explanation = chartExplanation(spec);
        chart.setOption({ ...option, backgroundColor: "#fff", title: { text: `${spec.title}（${spec.unit}）`, subtext: [context, explanation].filter(Boolean).join("\n"), left: 12, top: 8, textStyle: { fontSize: 14 }, subtextStyle: { fontSize: 11 } },
          ...(spec.kind === "funnel" ? { series: (option.series as object[]).map((s) => ({ ...s, top: 78 })) } : { grid: { ...(option.grid as object), top: 82 } }) });
        dataUrl = chart.getDataURL({ type, pixelRatio: 2, backgroundColor: "#fff" });
        if (type === "svg") {
          const encoded = dataUrl.slice(dataUrl.indexOf(",") + 1);
          const svg = dataUrl.slice(0, dataUrl.indexOf(",")).includes("base64")
            ? new TextDecoder().decode(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0)))
            : decodeURIComponent(encoded);
          dataUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(evidenceSvg(svg, spec, facts, context))}`;
        }
      }
      download(dataUrl, `${spec.id}${context.includes("合成") ? "-synthetic" : ""}.${type}`);
    } catch (e) { setExportError(e instanceof Error ? e.message : "导出失败，请重试"); }
    finally { chart?.dispose(); detached?.remove(); setExporting(false); }
  }

  const rows = spec.series.flatMap((series) => series.points.map((point) => ({ series: series.name, ...point })));
  const table = <div className="insight-table-scroll"><table><caption>{spec.title} · 数值与事实登记表一致</caption>
    <thead><tr><th scope="col">类别</th>{spec.kind === "heatmap" && <th scope="col">层级</th>}<th scope="col">系列</th><th scope="col">{spec.metric_label}（{spec.unit}）</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={`${row.series}-${row.category}-${row.column}`}><th scope="row">{row.category}</th>{spec.kind === "heatmap" && <td>{row.column}</td>}<td>{row.series}</td><td>{index.has(row.fact_id) ? formatFact(index.get(row.fact_id)!) : "事实缺失"}</td></tr>)}</tbody>
  </table></div>;
  return <section className={`insight-chart insight-chart--${spec.kind}`} aria-label={spec.title}>
    <header><h3>{spec.title}</h3></header>
    {chartExplanation(spec) && <p className="insight-chart-explanation">{chartExplanation(spec)}</p>}
    {validationError || renderError ? <p role="alert" className="insight-error">图表已阻断：{validationError || renderError}</p> : <>
      {spec.kind === "kpi" ? <p className="insight-kpi">{formatFact(index.get(rows[0].fact_id)!)}</p> : native ? table : <>
        <div ref={host} className="insight-chart-canvas" role="img" aria-label={`${spec.title}，详见下方数据表`} />
        <details><summary>查看图表数据与抑制状态</summary>{table}</details>
      </>}
      <div className="insight-chart-actions"><button type="button" disabled={stale || exporting} onClick={() => void exportChart("svg")}>导出 SVG</button><button type="button" disabled={stale || exporting} onClick={() => void exportChart("png")}>导出 PNG</button></div>
    </>}
    {exportError && <p role="alert" className="insight-error">{exportError}</p>}
  </section>;
}
