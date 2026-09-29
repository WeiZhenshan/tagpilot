import type { ChartSpec, Fact } from "./types";

const intentKinds = { single_value: "kpi", compare_categories: "bar", show_composition: "stacked_bar", show_distribution: "bar", show_matrix: "heatmap", show_conversion: "funnel" };
const kinds = new Set(["kpi", "table", "bar", "stacked_bar", "heatmap", "funnel"]);
const units = new Set(["人", "元", "%", "pp", "分"]);
const unsafe = /<[a-zA-Z!/]/;
function check(condition: unknown, reason: string): asserts condition {
  if (!condition) throw new Error(reason);
}
function keys(value: object, allowed: string[]) {
  check(value && typeof value === "object" && !Array.isArray(value), "图表协议对象非法");
  check(Object.keys(value).every((key) => allowed.includes(key)), "图表协议包含未允许字段");
}
function text(value: unknown, max: number) {
  check(typeof value === "string" && value.length > 0 && value.length <= max && !unsafe.test(value), "图表文字非法");
}
function same(a: string[], b: string[]) {
  return new Set(a).size === new Set(b).size && a.every((id) => b.includes(id));
}

// 再校验展示输入，导出复用此校验，不信任被篡改的前端状态。
export function validateChartSpec(spec: ChartSpec, facts: Fact[], suppression = 20): void {
  keys(spec, ["schema_version", "id", "title", "kind", "intent", "unit", "metric_label", "series", "annotations", "reconcile", "zero_baseline", "orientation"]);
  check(spec.schema_version === 1 && spec.zero_baseline === true && kinds.has(spec.kind), "图表类型或零基线非法");
  check(Object.hasOwn(intentKinds, spec.intent) && (spec.kind === "table" || intentKinds[spec.intent] === spec.kind), "意图与图型不匹配");
  check(spec.orientation === "horizontal" || spec.orientation === "vertical", "轴编码非法");
  check(units.has(spec.unit), "单位非法");
  text(spec.id, 80); text(spec.title, 80); text(spec.metric_label, 40);
  check(Array.isArray(facts) && facts.length <= 300 && new Set(facts.map((f) => f.id)).size === facts.length, "事实表标识重复或过多");
  const index = new Map(facts.map((fact) => [fact.id, fact]));
  function available(id: string): Fact & { value: number; sample_size: number } {
    const fact = index.get(id);
    check(fact && fact.status === "AVAILABLE" && typeof fact.value === "number" && Number.isFinite(fact.value) &&
      typeof fact.sample_size === "number" && Number.isInteger(fact.sample_size) && fact.sample_size >= Math.max(20, suppression), "事实缺失或样本不足");
    if (fact.unit === "人") check(Number.isInteger(fact.value) && fact.value >= 0 && (fact.value === 0 || fact.value >= suppression), "小样本人数未抑制");
    return fact as Fact & { value: number; sample_size: number };
  }
  check(Array.isArray(spec.series) && spec.series.length > 0 && spec.series.length <= 8, "系列数非法");
  const points = spec.series.flatMap((series) => {
    keys(series, ["name", "fact_ids", "points"]); text(series.name, 24);
    check(Array.isArray(series.points) && series.points.length > 0 && series.points.length <= 100 && Array.isArray(series.fact_ids), "系列数据非法");
    check(same(series.fact_ids, series.points.map((p) => p.fact_id)), "系列事实绑定不完整");
    check(new Set(series.points.map((p) => JSON.stringify([p.category, p.column]))).size === series.points.length, "图表格子重复");
    for (const point of series.points) {
      keys(point, ["category", "column", "fact_id", "value"]); text(point.category, 24);
      check(typeof point.fact_id === "string", "事实标识非法");
      const fact = index.get(point.fact_id);
      check(fact && fact.unit === spec.unit && fact.value === point.value, "图表数值或单位与事实不一致");
      if (fact.status === "AVAILABLE") {
        available(fact.id);
        if (fact.unit === "%") {
          check(fact.denominator_id && available(fact.denominator_id).value > 0 && fact.value! >= 0 && fact.value! <= 100, "百分比缺少分母");
          if (fact.calculation === "WEIGHTED") {
            const weights = fact.weights || {};
            check(same(Object.keys(weights), fact.derived_from) && Object.keys(weights).length > 0, "标准化权重缺少源事实");
            check(Object.values(weights).every((w) => Number.isFinite(w) && w >= 0) && Math.abs(Object.values(weights).reduce((a,b) => a+b,0)-1) < 1e-9, "标准化权重非法");
            const expected = Object.entries(weights).reduce((sum,[id,w]) => { check(available(id).unit === "%", "加权源单位非法"); return sum + available(id).value*w; },0);
            check(Math.abs(expected-fact.value!) <= .01, "标准化基准与权重不一致");
          } else if (fact.derived_from.length) {
            const numerator = fact.derived_from.reduce((sum, id) => sum + available(id).value, 0);
            check(Math.abs(numerator / available(fact.denominator_id).value * 100 - fact.value!) <= .01, "比例与分子分母不一致");
          }
        }
      } else check(["SUPPRESSED", "MISSING"].includes(fact.status) && point.value === null && fact.sample_size === null, "抑制格泄露数值");
      if (spec.kind === "heatmap") text(point.column, 24);
      else check(point.column === null, "非矩阵图不允许列编码");
    }
    return series.points;
  });
  check(new Set(points.map((p) => p.category)).size <= 12 && new Set(points.map((p) => p.column)).size <= 12, "类别过多");
  if (["kpi", "heatmap", "funnel"].includes(spec.kind)) check(spec.series.length === 1, "此图型只允许一个系列");
  if (spec.kind === "kpi") check(points.length === 1, "KPI 只允许一个事实");
  check(Array.isArray(spec.reconcile) && spec.reconcile.length <= 12, "对账规则非法");
  const displayed = new Set(points.map((p) => p.fact_id));
  for (const rule of spec.reconcile) {
    keys(rule, ["kind", "fact_ids", "total_fact_id", "tolerance"]);
    check(["sum", "percentage", "funnel"].includes(rule.kind) && Array.isArray(rule.fact_ids) && rule.fact_ids.length > 0 && rule.fact_ids.length <= 100 && new Set(rule.fact_ids).size === rule.fact_ids.length && rule.fact_ids.every((id) => displayed.has(id)), "对账引用非法");
    check(typeof rule.tolerance === "number" && Number.isFinite(rule.tolerance) && rule.tolerance >= 0 && rule.tolerance <= .05, "对账容差非法");
    const values = rule.fact_ids.map((id) => available(id).value);
    if (rule.kind === "funnel") check(values.every((v, i) => v >= 0 && (i === 0 || v <= values[i - 1])), "漏斗未逐步减少");
    else {
      check(rule.kind !== "percentage" || spec.unit === "%", "占比对账单位非法");
      const target = rule.kind === "percentage" ? 100 : rule.total_fact_id ? available(rule.total_fact_id).value : NaN;
      if (rule.kind === "sum") check(!!rule.total_fact_id && available(rule.total_fact_id).unit === spec.unit, "合计单位不一致");
      check(Math.abs(values.reduce((a, b) => a + b, 0) - target) <= rule.tolerance, "图表无法对账");
    }
  }
  if (spec.kind === "funnel") check(spec.unit === "人" && spec.reconcile.some((r) => r.kind === "funnel" && r.fact_ids.join() === points.map((p) => p.fact_id).join()), "漏斗缺少完整顺序对账");
  if (spec.kind === "stacked_bar" && spec.unit === "%") {
    for (const category of new Set(points.map((p) => p.category))) {
      const ids = points.filter((p) => p.category === category).map((p) => p.fact_id);
      check(spec.reconcile.some((r) => r.kind === "percentage" && same(r.fact_ids, ids)), "百分比堆叠缺少分组对账");
    }
  }
  check(Array.isArray(spec.annotations) && spec.annotations.length <= 8, "标注非法");
  for (const annotation of spec.annotations) {
    keys(annotation, ["text", "fact_ids"]); text(annotation.text, 500);
    check(Array.isArray(annotation.fact_ids) && annotation.fact_ids.length > 0 && annotation.fact_ids.length <= 10, "标注缺少事实");
    annotation.fact_ids.forEach(available);
    const refs = [...annotation.text.matchAll(/\{fact:([a-z][a-z0-9_.-]{0,79})\}/g)].map((m) => m[1]);
    check(refs.every((id) => annotation.fact_ids.includes(id)) && !/[\d０-９]/.test(annotation.text.replace(/\{fact:[^}]+\}/g, "")), "标注数字未绑定事实");
  }
}
