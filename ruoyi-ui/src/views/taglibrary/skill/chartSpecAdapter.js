/**
 * InsightChartSpec → 视图描述适配器。
 *
 * 契约约定：`spec.rows` 是**已聚合、已校验**的数据，前端只负责按 `spec.view` 渲染，
 * **不得再计算任何指标**。本文件只做"结构映射"，不做业务计算。
 *
 * 支持 view.mark 白名单中的：
 *   kpi / table / bar / line / area / stacked_bar / pie / histogram /
 *   scatter / heatmap / funnel / waterfall / treemap
 */

/** 契约声明的全部可用 mark */
export const SUPPORTED_MARKS = [
  'kpi', 'table', 'bar', 'line', 'area', 'stacked_bar', 'pie',
  'histogram', 'scatter', 'heatmap', 'funnel', 'waterfall', 'treemap'
]

/** 渲染类型：KPI 卡片 / ECharts 图表 / 数据表 */
export const KIND_KPI = 'kpi'
export const KIND_ECHARTS = 'echarts'
export const KIND_TABLE = 'table'

const PALETTE = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#9B59B6', '#00BCD4', '#FF9800']

function num(value) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isNaN(parsed) ? null : parsed
}

function distinct(rows, field) {
  const seen = []
  const set = new Set()
  rows.forEach(row => {
    const value = row[field]
    const key = value === null || value === undefined ? '' : String(value)
    if (!set.has(key)) {
      set.add(key)
      seen.push(value)
    }
  })
  return seen
}

function labelOf(value) {
  return value === null || value === undefined || value === '' ? '（空）' : String(value)
}

/** 解析字段语义角色 */
function resolveFields(spec) {
  const fields = Array.isArray(spec.fields) ? spec.fields : []
  const byRole = role => fields.filter(f => f && f.role === role).map(f => f.field)
  const dimensions = byRole('dimension')
  const measures = byRole('measure')
  const encoding = (spec.view && spec.view.encoding) || {}
  const dimension = pick(encoding, ['x', 'y', 'name', 'category', 'row', 'column']) || dimensions[0] || null
  const measure = pick(encoding, ['value', 'measure', 'size']) || measures[0] || null
  return {
    dimensions,
    measures,
    encoding,
    dimension,
    measure,
    group: encoding.color || encoding.series || byRole('group')[0] || null
  }
}

function pick(encoding, keys) {
  for (const key of keys) {
    if (encoding[key]) return encoding[key]
  }
  return null
}

function isHorizontal(spec) {
  return spec.view && spec.view.orientation === 'horizontal'
}

function baseOption(spec) {
  const title = { text: spec.title || '' }
  if (spec.subtitle) title.subtext = spec.subtitle
  return {
    title,
    color: PALETTE,
    tooltip: { trigger: 'axis', confine: true },
    legend: { type: 'scroll', top: 28, textStyle: { fontSize: 11 } },
    grid: { left: 12, right: 18, bottom: 12, top: 64, containLabel: true }
  }
}

/** 按维度/分组/度量组装柱线面类系列（rows 已是聚合结果，只做取值映射） */
function seriesOption(spec, chartType, stacked) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const dim = meta.dimension
  const measure = meta.measure
  const group = meta.group
  if (!dim || !measure) return null

  const categories = distinct(rows, dim)
  const groups = group ? distinct(rows, group) : [null]
  const horizontal = isHorizontal(spec)

  const series = groups.map((groupValue, groupIndex) => {
    const subset = group ? rows.filter(r => String(r[group]) === String(groupValue)) : rows
    const data = categories.map(category => {
      const row = subset.find(r => String(r[dim]) === String(category))
      return row ? num(row[measure]) : null
    })
    return {
      name: group ? labelOf(groupValue) : labelOf(measure),
      type: chartType,
      stack: stacked ? 'total' : undefined,
      emphasis: { focus: 'series' },
      areaStyle: chartType === 'line' && spec.view.mark === 'area' ? { opacity: 0.25 } : undefined,
      smooth: chartType === 'line',
      data,
      itemStyle: { color: PALETTE[groupIndex % PALETTE.length] }
    }
  })

  const categoryAxis = { type: 'category', data: categories.map(labelOf), axisLabel: { interval: 0, rotate: categories.length > 6 ? 30 : 0, fontSize: 11 } }
  const valueAxis = { type: 'value', name: unitOf(meta, spec) }

  const option = baseOption(spec)
  option.tooltip = { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } }
  option.xAxis = horizontal ? valueAxis : categoryAxis
  option.yAxis = horizontal ? categoryAxis : valueAxis
  option.series = series
  return option
}

function unitOf(meta, spec) {
  const fields = Array.isArray(spec.fields) ? spec.fields : []
  const found = fields.find(f => f && f.field === meta.measure)
  return found && found.unit ? found.unit : ''
}

function pieOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const nameField = meta.encoding.name || meta.dimension
  const valueField = meta.encoding.value || meta.measure
  if (!nameField || !valueField) return null
  return {
    title: { text: spec.title || '', subtext: spec.subtitle || '' },
    color: PALETTE,
    tooltip: { trigger: 'item', confine: true },
    legend: { type: 'scroll', top: 28, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['38%', '64%'],
      center: ['50%', '58%'],
      avoidLabelOverlap: true,
      label: { formatter: '{b}: {c}' },
      data: rows.map(row => ({ name: labelOf(row[nameField]), value: num(row[valueField]) }))
    }]
  }
}

function funnelOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const nameField = meta.encoding.name || meta.dimension
  const valueField = meta.encoding.value || meta.measure
  if (!nameField || !valueField) return null
  return {
    title: { text: spec.title || '', subtext: spec.subtitle || '' },
    color: PALETTE,
    tooltip: { trigger: 'item', confine: true },
    legend: { type: 'scroll', top: 28, textStyle: { fontSize: 11 } },
    series: [{
      type: 'funnel',
      left: '10%',
      width: '80%',
      top: 64,
      label: { formatter: '{b}: {c}' },
      data: rows.map(row => ({ name: labelOf(row[nameField]), value: num(row[valueField]) }))
    }]
  }
}

function scatterOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const xField = meta.encoding.x || meta.measures[0]
  const yField = meta.encoding.y || meta.measures[1] || meta.measures[0]
  const group = meta.group
  if (!xField || !yField) return null
  const groups = group ? distinct(rows, group) : [null]
  const option = baseOption(spec)
  option.tooltip = { trigger: 'item', confine: true }
  option.xAxis = { type: 'value', name: xField }
  option.yAxis = { type: 'value', name: yField }
  option.series = groups.map((groupValue, index) => ({
    name: group ? labelOf(groupValue) : labelOf(yField),
    type: 'scatter',
    symbolSize: 12,
    itemStyle: { color: PALETTE[index % PALETTE.length] },
    data: (group ? rows.filter(r => String(r[group]) === String(groupValue)) : rows)
      .map(row => [num(row[xField]), num(row[yField])])
  }))
  return option
}

function heatmapOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const xField = meta.encoding.x || meta.dimensions[0]
  const yField = meta.encoding.y || meta.dimensions[1]
  const valueField = meta.encoding.value || meta.measure
  if (!xField || !yField || !valueField) return null
  const xCategories = distinct(rows, xField)
  const yCategories = distinct(rows, yField)
  const data = rows.map(row => [
    xCategories.findIndex(v => String(v) === String(row[xField])),
    yCategories.findIndex(v => String(v) === String(row[yField])),
    num(row[valueField])
  ])
  const values = data.map(item => item[2]).filter(v => v !== null)
  return {
    title: { text: spec.title || '', subtext: spec.subtitle || '' },
    tooltip: { position: 'top', confine: true },
    grid: { left: 12, right: 18, bottom: 24, top: 64, containLabel: true },
    xAxis: { type: 'category', data: xCategories.map(labelOf), splitArea: { show: true }, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'category', data: yCategories.map(labelOf), splitArea: { show: true }, axisLabel: { fontSize: 11 } },
    visualMap: {
      min: values.length ? Math.min(...values) : 0,
      max: values.length ? Math.max(...values) : 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0
    },
    series: [{ type: 'heatmap', data, label: { show: true } }]
  }
}

function treemapOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const nameField = meta.encoding.name || meta.dimension
  const valueField = meta.encoding.value || meta.measure
  if (!nameField || !valueField) return null
  return {
    title: { text: spec.title || '', subtext: spec.subtitle || '' },
    color: PALETTE,
    tooltip: { trigger: 'item', confine: true },
    series: [{
      type: 'treemap',
      top: 64,
      roam: false,
      label: { formatter: '{b}: {c}' },
      data: rows.map(row => ({ name: labelOf(row[nameField]), value: num(row[valueField]) }))
    }]
  }
}

/** 瀑布图：契约要求 rows 已给出基数(base)与增量(delta)，前端只做堆叠，不做累计计算 */
function waterfallOption(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const dim = meta.dimension
  const valueField = meta.measure
  const baseField = meta.encoding.base
  if (!dim || !valueField || !baseField) {
    return seriesOption(spec, 'bar', false)
  }
  const categories = distinct(rows, dim)
  const baseSeries = categories.map(category => {
    const row = rows.find(r => String(r[dim]) === String(category))
    return row ? num(row[baseField]) : null
  })
  const deltaSeries = categories.map(category => {
    const row = rows.find(r => String(r[dim]) === String(category))
    return row ? num(row[valueField]) : null
  })
  const option = baseOption(spec)
  option.tooltip = { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } }
  option.xAxis = { type: 'category', data: categories.map(labelOf), axisLabel: { fontSize: 11 } }
  option.yAxis = { type: 'value' }
  option.series = [
    { name: '基数', type: 'bar', stack: 'waterfall', itemStyle: { color: 'transparent' }, emphasis: { itemStyle: { color: 'transparent' } }, data: baseSeries },
    { name: '增量', type: 'bar', stack: 'waterfall', itemStyle: { color: PALETTE[0] }, data: deltaSeries }
  ]
  return option
}

function kpiView(spec) {
  const meta = resolveFields(spec)
  const rows = spec.rows || []
  const fields = Array.isArray(spec.fields) ? spec.fields : []
  let items = []
  if (fields.length) {
    items = fields.map(field => {
      const row = rows[0] || {}
      const raw = row[field.field]
      const value = field.role === 'measure' || raw !== undefined ? raw : null
      return {
        label: field.alias || field.field,
        value: value === null || value === undefined ? '-' : value,
        unit: field.unit || ''
      }
    })
  } else if (rows.length) {
    items = Object.keys(rows[0]).map(key => ({ label: key, value: rows[0][key], unit: '' }))
  }
  return { kind: KIND_KPI, items }
}

function tableView(spec) {
  const rows = spec.rows || []
  return { kind: KIND_TABLE, columns: specColumns(spec), rows }
}

/** 依据 spec.fields 推导展示列；缺省回退到首行键名 */
function specColumns(spec) {
  const rows = spec.rows || []
  const fields = Array.isArray(spec.fields) ? spec.fields : []
  if (fields.length) {
    return fields.map(f => ({ prop: f.field, label: f.alias || f.field, unit: f.unit || '' }))
  }
  return Object.keys(rows[0] || {}).map(key => ({ prop: key, label: key, unit: '' }))
}

/** 注解文本（highlight / reference 等） */
function annotationNotes(spec) {
  return (spec.annotations || [])
    .map(item => {
      const text = item.text || ''
      if (!text) return null
      const target = item.category || item.field || item.series || ''
      return target ? `${target}：${text}` : text
    })
    .filter(Boolean)
}

function accessibilityOf(spec) {
  const accessibility = spec.accessibility || {}
  return {
    summary: accessibility.summary || '',
    dataTable: accessibility.data_table !== false,
    doNotUseColorOnly: accessibility.do_not_use_color_only === true
  }
}

/**
 * 主入口：把一条 InsightChartSpec 转成可直接渲染的视图描述。
 * @returns {{mark:string, kind:string, option?:Object, items?:Array, columns?:Array, rows?:Array,
 *            summary:string, notes:Array<string>, dataTable:boolean, title:string}}
 */
export function buildChartView(spec) {
  const safeSpec = spec || {}
  const mark = String((safeSpec.view && safeSpec.view.mark) || 'table').toLowerCase()
  const accessibility = accessibilityOf(safeSpec)
  const base = {
    mark,
    kind: KIND_TABLE,
    summary: accessibility.summary,
    notes: annotationNotes(safeSpec),
    dataTable: accessibility.dataTable,
    title: safeSpec.title || '',
    columns: specColumns(safeSpec),
    rows: safeSpec.rows || []
  }

  if (mark === 'kpi') {
    return Object.assign(base, kpiView(safeSpec))
  }
  if (mark === 'table') {
    return Object.assign(base, tableView(safeSpec))
  }

  let option = null
  switch (mark) {
    case 'bar':
      option = seriesOption(safeSpec, 'bar', false)
      break
    case 'histogram':
      option = seriesOption(safeSpec, 'bar', false)
      break
    case 'stacked_bar':
      option = seriesOption(safeSpec, 'bar', true)
      break
    case 'line':
    case 'area':
      option = seriesOption(safeSpec, 'line', false)
      break
    case 'pie':
      option = pieOption(safeSpec)
      break
    case 'funnel':
      option = funnelOption(safeSpec)
      break
    case 'scatter':
      option = scatterOption(safeSpec)
      break
    case 'heatmap':
      option = heatmapOption(safeSpec)
      break
    case 'waterfall':
      option = waterfallOption(safeSpec)
      break
    case 'treemap':
      option = treemapOption(safeSpec)
      break
    default:
      option = null
  }

  if (!option) {
    // 未知或字段不足的 mark 退化为数据表，保证数据一定可见（绝不静默丢数据）
    return Object.assign(base, tableView(safeSpec))
  }
  return Object.assign(base, { kind: KIND_ECHARTS, option })
}

/** 批量转换 */
export function buildChartViews(specs) {
  return (specs || []).map(buildChartView)
}
