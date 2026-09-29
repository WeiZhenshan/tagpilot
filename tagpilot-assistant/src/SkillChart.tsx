import type { ReactElement } from "react";
import type { ChartField, ChartSpec } from "./skillApi";

/**
 * 图表渲染：直接消费引擎下发的 InsightChartSpec（rows 已聚合、已校验）。
 * 这里只做呈现，不做任何二次计算或推断；未知 mark 一律降级为数据表，保证可读。
 */
const PALETTE = [
  "#409eff",
  "#67c23a",
  "#e6a23c",
  "#f56c6c",
  "#8b5cf6",
  "#0ea5e9",
  "#94a3b8",
  "#d97706",
];

const WIDTH = 640;
const ROW_H = 26;
const LABEL_W = 118;
const VALUE_W = 76;

function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumber(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  if (Number.isFinite(numeric)) {
    const abs = Math.abs(numeric);
    if (abs >= 100000000) return (numeric / 100000000).toFixed(2) + " 亿";
    if (abs >= 10000) return (numeric / 10000).toFixed(2) + " 万";
    return Number.isInteger(numeric)
      ? numeric.toLocaleString("zh-CN")
      : numeric.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function unitSuffix(unit?: string): string {
  if (!unit) return "";
  if (unit === "percent" || unit === "%") return "%";
  return unit;
}

function formatValue(value: unknown, unit?: string): string {
  return `${formatNumber(value)}${unitSuffix(unit)}`;
}

function unitOf(spec: ChartSpec, field?: string): string {
  return spec.fields.find((f) => f.field === field)?.unit || "";
}

function roles(spec: ChartSpec) {
  const dimension = spec.fields.find((f) => f.role === "dimension");
  const measure = spec.fields.find((f) => f.role === "measure");
  const group = spec.fields.find((f) => f.role === "group");
  return {
    dimension: dimension?.field,
    measure: measure?.field,
    group: group?.field,
    dimensionUnit: dimension?.unit,
    measureUnit: measure?.unit,
  };
}

function clip(text: unknown, max = 14): string {
  const value = String(text ?? "—");
  return value.length > max ? value.slice(0, max - 1) + "…" : value;
}

function unique(values: unknown[]): string[] {
  const seen: string[] = [];
  for (const value of values) {
    const key = String(value);
    if (!seen.includes(key)) seen.push(key);
  }
  return seen;
}

function KpiChart({ spec }: { spec: ChartSpec }) {
  return (
    <div className="chart-kpi">
      {spec.rows.map((row, i) => (
        <div className="chart-kpi-item" key={i}>
          <span>{String(row.label ?? "—")}</span>
          <strong>
            {formatValue(row.value)}
            <small>{unitSuffix(String(row.unit || ""))}</small>
          </strong>
          {row.delta_text ? <em>{String(row.delta_text)}</em> : null}
        </div>
      ))}
    </div>
  );
}

function TableChart({ spec }: { spec: ChartSpec }) {
  const columns: ChartField[] = spec.fields.length
    ? spec.fields
    : Object.keys(spec.rows[0] || {}).map((field) => ({
        field,
        semantic_type: "measure",
        role: "measure",
      }));
  return (
    <div className="chart-table-wrap">
      <table className="chart-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.field}>{column.field}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.rows.slice(0, 50).map((row, i) => (
            <tr key={i}>
              {columns.map((column) => (
                <td key={column.field}>
                  {formatValue(row[column.field], column.unit || unitOf(spec, column.field))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {spec.rows.length > 50 ? (
        <p className="muted">仅展示前 50 行，共 {spec.rows.length} 行。</p>
      ) : null}
    </div>
  );
}

function HorizontalBar({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure, measureUnit } = roles(spec);
  const cat = enc.y || dimension;
  const val = enc.x || measure;
  if (!cat || !val) return <TableChart spec={spec} />;
  const rows = spec.rows.slice(0, 20);
  const max = Math.max(...rows.map((row) => Math.abs(toNumber(row[val]))), 1);
  const height = Math.max(rows.length * ROW_H + 12, 60);
  const barArea = WIDTH - LABEL_W - VALUE_W;
  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
      aria-label={spec.accessibility?.summary || spec.title}>
      {rows.map((row, i) => {
        const width = (Math.abs(toNumber(row[val])) / max) * barArea;
        return (
          <g key={i}>
            <text x={LABEL_W - 8} y={i * ROW_H + 20} textAnchor="end" className="chart-label">
              {clip(row[cat])}
            </text>
            <rect x={LABEL_W} y={i * ROW_H + 7} width={Math.max(width, 1)} height={15}
              fill={PALETTE[i % PALETTE.length]} rx={2} />
            <text x={LABEL_W + Math.max(width, 1) + 6} y={i * ROW_H + 20} className="chart-value">
              {formatValue(row[val], unitOf(spec, val) || measureUnit)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function VerticalBar({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure, measureUnit } = roles(spec);
  const cat = enc.x || dimension;
  const val = enc.y || measure;
  if (!cat || !val) return <TableChart spec={spec} />;
  const rows = spec.rows.slice(0, 20);
  const height = 260;
  const base = height - 34;
  const top = 12;
  const max = Math.max(...rows.map((row) => Math.abs(toNumber(row[val]))), 1);
  const slot = (WIDTH - 24) / Math.max(rows.length, 1);
  const barW = Math.min(slot * 0.62, 46);
  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
      aria-label={spec.accessibility?.summary || spec.title}>
      <line x1={16} y1={base} x2={WIDTH - 8} y2={base} stroke="#e7e9ed" />
      {rows.map((row, i) => {
        const value = Math.abs(toNumber(row[val]));
        const barH = ((value / max) * (base - top)) || 0;
        const x = 16 + slot * i + (slot - barW) / 2;
        return (
          <g key={i}>
            <rect x={x} y={base - barH} width={barW} height={Math.max(barH, 1)}
              fill={PALETTE[i % PALETTE.length]} rx={2} />
            <text x={x + barW / 2} y={base - barH - 5} textAnchor="middle" className="chart-value">
              {formatValue(row[val], unitOf(spec, val) || measureUnit)}
            </text>
            <text x={x + barW / 2} y={base + 16} textAnchor="middle" className="chart-label">
              {clip(row[cat], 10)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function StackedBar({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure, group } = roles(spec);
  const cat = enc.x || dimension;
  const val = enc.y || measure;
  const series = enc.color || group;
  if (!cat || !val || !series) return <TableChart spec={spec} />;
  const categories = unique(spec.rows.map((row) => row[cat]));
  const legends = unique(spec.rows.map((row) => row[series]));
  const height = 270;
  const base = height - 40;
  const top = 14;
  const slot = (WIDTH - 24) / Math.max(categories.length, 1);
  const barW = Math.min(slot * 0.6, 52);
  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
        aria-label={spec.accessibility?.summary || spec.title}>
        <line x1={16} y1={base} x2={WIDTH - 8} y2={base} stroke="#e7e9ed" />
        {categories.map((category, i) => {
          const parts = spec.rows.filter((row) => String(row[cat]) === category);
          const total = parts.reduce((sum, row) => sum + toNumber(row[val]), 0) || 1;
          let cursor = base;
          const x = 16 + slot * i + (slot - barW) / 2;
          return (
            <g key={category}>
              {parts.map((row, j) => {
                const h = (toNumber(row[val]) / total) * (base - top);
                cursor -= h;
                return (
                  <rect key={j} x={x} y={cursor} width={barW} height={Math.max(h, 0)}
                    fill={PALETTE[legends.indexOf(String(row[series])) % PALETTE.length]} />
                );
              })}
              <text x={x + barW / 2} y={base + 16} textAnchor="middle" className="chart-label">
                {clip(category, 10)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="chart-legend">
        {legends.map((legend, i) => (
          <span key={legend}>
            <i style={{ background: PALETTE[i % PALETTE.length] }} />
            {legend}
          </span>
        ))}
      </div>
    </div>
  );
}

function PieChart({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure } = roles(spec);
  const cat = enc.category || enc.y || dimension;
  const val = enc.value || enc.x || measure;
  if (!cat || !val) return <TableChart spec={spec} />;
  const rows = spec.rows.slice(0, 12);
  const total = rows.reduce((sum, row) => sum + toNumber(row[val]), 0) || 1;
  const size = 240;
  const radius = 96;
  const cx = 150;
  const cy = 130;
  let angle = -Math.PI / 2;
  return (
    <div className="chart-pie-wrap">
      <svg viewBox={`0 0 ${size + 130} ${size + 20}`} className="chart-svg chart-pie" role="img"
        aria-label={spec.accessibility?.summary || spec.title}>
        {rows.map((row, i) => {
          const share = toNumber(row[val]) / total;
          const end = angle + share * Math.PI * 2;
          const large = end - angle > Math.PI ? 1 : 0;
          const x1 = cx + radius * Math.cos(angle);
          const y1 = cy + radius * Math.sin(angle);
          const x2 = cx + radius * Math.cos(end);
          const y2 = cy + radius * Math.sin(end);
          angle = end;
          if (share <= 0) return null;
          return (
            <path
              key={i}
              d={`M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2} Z`}
              fill={PALETTE[i % PALETTE.length]}
              stroke="#fff"
              strokeWidth={1}
            />
          );
        })}
      </svg>
      <ul className="chart-legend chart-legend-list">
        {rows.map((row, i) => (
          <li key={i}>
            <i style={{ background: PALETTE[i % PALETTE.length] }} />
            {clip(row[cat], 12)}
            <span>
              {((toNumber(row[val]) / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LineChart({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure, group } = roles(spec);
  const cat = enc.x || dimension;
  const val = enc.y || measure;
  const series = enc.color || group;
  if (!cat || !val) return <TableChart spec={spec} />;
  const filled = spec.view.mark === "area";
  const categories = unique(spec.rows.map((row) => row[cat]));
  const seriesList = series ? unique(spec.rows.map((row) => row[series])) : [""];
  const height = 250;
  const base = height - 34;
  const top = 14;
  const max = Math.max(...spec.rows.map((row) => toNumber(row[val])), 1);
  const step = categories.length > 1 ? (WIDTH - 60) / (categories.length - 1) : 0;
  const xOf = (index: number) => 40 + step * index;
  const yOf = (value: number) => base - (value / max) * (base - top);
  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
        aria-label={spec.accessibility?.summary || spec.title}>
        <line x1={30} y1={base} x2={WIDTH - 20} y2={base} stroke="#e7e9ed" />
        {seriesList.map((name, s) => {
          const points = categories.map((category, i) => {
            const row = spec.rows.find(
              (item) =>
                String(item[cat]) === category &&
                (!series || String(item[series]) === name)
            );
            return { x: xOf(i), y: yOf(row ? toNumber(row[val]) : 0) };
          });
          const path = points.map((p) => `${p.x},${p.y}`).join(" ");
          const areaPath =
            `M ${points[0]?.x ?? 40},${base} ` +
            points.map((p) => `L ${p.x},${p.y}`).join(" ") +
            ` L ${points[points.length - 1]?.x ?? 40},${base} Z`;
          return (
            <g key={name || s}>
              {filled ? (
                <path d={areaPath} fill={PALETTE[s % PALETTE.length]} opacity={0.16} />
              ) : null}
              <polyline points={path} fill="none" stroke={PALETTE[s % PALETTE.length]} strokeWidth={2} />
              {points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={2.6} fill={PALETTE[s % PALETTE.length]} />
              ))}
            </g>
          );
        })}
        {categories.map((category, i) => (
          <text key={category} x={xOf(i)} y={base + 16} textAnchor="middle" className="chart-label">
            {clip(category, 10)}
          </text>
        ))}
      </svg>
      {seriesList.length > 1 ? (
        <div className="chart-legend">
          {seriesList.map((name, i) => (
            <span key={name}>
              <i style={{ background: PALETTE[i % PALETTE.length] }} />
              {name}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function FunnelChart({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const { dimension, measure } = roles(spec);
  const cat = enc.category || dimension;
  const val = enc.value || measure;
  if (!cat || !val) return <TableChart spec={spec} />;
  const rows = spec.rows.slice(0, 12);
  const height = Math.max(rows.length * 42 + 12, 90);
  const max = Math.max(...rows.map((row) => toNumber(row[val])), 1);
  const usable = WIDTH - 190;
  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
      aria-label={spec.accessibility?.summary || spec.title}>
      {rows.map((row, i) => {
        const value = toNumber(row[val]);
        const width = Math.max((value / max) * usable, 42);
        const x = (WIDTH - width) / 2;
        const y = i * 42 + 8;
        return (
          <g key={i}>
            <rect x={x} y={y} width={width} height={30} rx={3}
              fill={PALETTE[i % PALETTE.length]} opacity={0.9} />
            <text x={WIDTH / 2} y={y + 20} textAnchor="middle" className="chart-funnel-text">
              {clip(row[cat], 16)} · {formatValue(row[val], unitOf(spec, val))}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function ScatterChart({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const xField = enc.x;
  const yField = enc.y;
  if (!xField || !yField) return <TableChart spec={spec} />;
  const points = spec.rows.slice(0, 200);
  const xs = points.map((row) => toNumber(row[xField]));
  const ys = points.map((row) => toNumber(row[yField]));
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 1);
  const height = 250;
  const base = height - 34;
  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
        aria-label={spec.accessibility?.summary || spec.title}>
        <line x1={46} y1={base} x2={WIDTH - 16} y2={base} stroke="#e7e9ed" />
        <line x1={46} y1={12} x2={46} y2={base} stroke="#e7e9ed" />
        {points.map((row, i) => {
          const px = 46 + ((toNumber(row[xField]) - minX) / (maxX - minX || 1)) * (WIDTH - 70);
          const py = base - ((toNumber(row[yField]) - minY) / (maxY - minY || 1)) * (base - 18);
          return <circle key={i} cx={px} cy={py} r={4} fill={PALETTE[0]} opacity={0.72} />;
        })}
        <text x={WIDTH / 2} y={height - 6} textAnchor="middle" className="chart-label">
          {xField}
        </text>
        <text x={10} y={22} className="chart-label">{yField}</text>
      </svg>
      <p className="muted">散点仅展示相关关系，不代表因果。</p>
    </div>
  );
}

function HeatmapChart({ spec }: { spec: ChartSpec }) {
  const enc = spec.view.encoding || {};
  const xField = enc.x;
  const yField = enc.y;
  const valueField = enc.color;
  if (!xField || !yField || !valueField) return <TableChart spec={spec} />;
  const xs = unique(spec.rows.map((row) => row[xField]));
  const ys = unique(spec.rows.map((row) => row[yField]));
  const max = Math.max(...spec.rows.map((row) => toNumber(row[valueField])), 1);
  const cellW = Math.min(110, (WIDTH - 120) / Math.max(xs.length, 1));
  const cellH = 30;
  const height = ys.length * cellH + 46;
  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} className="chart-svg" role="img"
      aria-label={spec.accessibility?.summary || spec.title}>
      {xs.map((x, i) => (
        <text key={x} x={116 + cellW * i + cellW / 2} y={26} textAnchor="middle" className="chart-label">
          {clip(x, 10)}
        </text>
      ))}
      {ys.map((y, r) => (
        <g key={y}>
          <text x={110} y={44 + cellH * r + cellH / 2 + 4} textAnchor="end" className="chart-label">
            {clip(y, 12)}
          </text>
          {xs.map((x, c) => {
            const row = spec.rows.find(
              (item) => String(item[xField]) === x && String(item[yField]) === y
            );
            const value = row ? toNumber(row[valueField]) : 0;
            const alpha = 0.12 + (value / max) * 0.72;
            return (
              <g key={`${x}-${y}`}>
                <rect x={116 + cellW * c} y={34 + cellH * r} width={cellW - 3} height={cellH - 3}
                  fill={`rgba(64, 158, 255, ${alpha.toFixed(3)})`} rx={2} />
                <text x={116 + cellW * c + (cellW - 3) / 2} y={34 + cellH * r + cellH / 2 + 3}
                  textAnchor="middle" className="chart-cell-text">
                  {value ? value.toFixed(0) + "%" : "—"}
                </text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

export function ChartFigure({ spec }: { spec: ChartSpec }) {
  const mark = spec.view.mark;
  const orientation = spec.view.orientation || "vertical";
  let body: ReactElement;
  switch (mark) {
    case "kpi":
      body = <KpiChart spec={spec} />;
      break;
    case "table":
      body = <TableChart spec={spec} />;
      break;
    case "bar":
    case "histogram":
      body = orientation === "horizontal" ? <HorizontalBar spec={spec} /> : <VerticalBar spec={spec} />;
      break;
    case "stacked_bar":
      body = <StackedBar spec={spec} />;
      break;
    case "pie":
      body = <PieChart spec={spec} />;
      break;
    case "line":
    case "area":
      body = <LineChart spec={spec} />;
      break;
    case "funnel":
      body = <FunnelChart spec={spec} />;
      break;
    case "scatter":
      body = <ScatterChart spec={spec} />;
      break;
    case "heatmap":
      body = <HeatmapChart spec={spec} />;
      break;
    default:
      body = <TableChart spec={spec} />;
  }
  return (
    <figure className="chart-figure">
      <figcaption>
        <strong>{spec.title}</strong>
        {spec.subtitle ? <span>{spec.subtitle}</span> : null}
      </figcaption>
      {body}
      {spec.annotations?.length ? (
        <ul className="chart-notes">
          {spec.annotations
            .filter((note) => note.text)
            .map((note, i) => (
              <li key={i}>{note.text}</li>
            ))}
        </ul>
      ) : null}
    </figure>
  );
}
