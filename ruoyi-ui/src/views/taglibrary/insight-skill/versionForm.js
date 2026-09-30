// 表单与版本登记协议之间的转换；不自动推断标签、业务阈值或码值映射。
export const PRODUCT_CATEGORIES = { wealth: '理财', fund: '基金', insurance: '保险' }
export const ASSET_CATEGORIES = { liquid: '流动资产', fixed: '定期资产', investment: '投资资产' }
const DIRECT_METRICS = ['aum', 'liquid_aum', 'fixed_aum', 'investment_aum', 'value_score', 'product_holding', 'product_gap']
export const VERSION_PATTERN = /^\d+\.\d+\.\d+$/

export function bindingKinds(metric) {
  const kinds = [{ value: 'DIRECT', label: '直接使用标签值' }]
  if (metric === 'aum_tier') kinds.push({ value: 'AUM_TIER', label: '按当前 AUM 分层（30万 / 100万）' })
  if (DIRECT_METRICS.includes(metric)) return kinds
  kinds.push({ value: 'IS_NULL', label: '判断是否为空' }, { value: 'GT', label: '大于指定值' }, { value: 'RATIO_GT', label: '两个标签的比值大于指定值' })
  if (metric === 'recent_contact') kinds.push({ value: 'RECENT_CONTACT', label: '按最近触达日期计算' })
  return kinds
}

export function mappingAllowed(row) {
  return row.kind === 'DIRECT' && !['aum', 'liquid_aum', 'fixed_aum', 'investment_aum', 'value_score', 'channel'].includes(row.metric)
}
export function mappingMaximum(metric) { return ['risk_level', 'aum_tier', 'org_scope'].includes(metric) ? 12 : 1 }

export function createVersionForm(manifest, previous = {}) {
  const existing = previous.bindings || []
  const rows = []
  function add(metric, category = '') {
    const binding = existing.find(item => item.metric === metric && (item.category || '') === category)
    rows.push({
      key: metric + ':' + category, metric, category,
      enabled: metric === 'product_holding' ? !!binding : metric === 'org_scope' ? !!binding : true,
      tag_ids: binding ? binding.tag_ids.slice() : [], kind: binding ? binding.kind || 'DIRECT' : 'DIRECT',
      threshold: binding && binding.threshold !== undefined ? binding.threshold : undefined,
      useMapping: !!(binding && binding.enum_map),
      mappings: binding && binding.enum_map ? Object.entries(binding.enum_map).map(([source, target]) => ({ source, target })) : []
    })
  }
  ;(manifest.metrics || []).forEach(metric => {
    if (['suitability', 'customer_count'].includes(metric)) return
    const categories = metric === 'asset_holder' ? ASSET_CATEGORIES : metric === 'product_holding' ? PRODUCT_CATEGORIES : null
    if (categories) Object.keys(categories).forEach(category => add(metric, category))
    else add(metric)
  })
  if (!(manifest.metrics || []).includes('org_scope')) add('org_scope')
  const parts = VERSION_PATTERN.test(previous.version || '') ? previous.version.split('.').map(Number) : [0, 1, -1]
  parts[2]++
  return {
    version: parts.join('.'), data_as_of: previous.data_as_of || '',
    binding_version: previous.binding_version || '0.1.0', benchmark_version: previous.benchmark_version || '0.1.0',
    benchmark_definition: previous.benchmark_definition || '', rows,
    suitability: Object.keys(PRODUCT_CATEGORIES).map(category => ({ category, enabled: Object.prototype.hasOwnProperty.call(previous.suitability || {}, category), minimum: (previous.suitability || {})[category] }))
  }
}

// 库107已核对的明确来源；未确定的业务口径保留为空，不以相近标签代替。
export function applyPersonalCustomerBindings(form, manifest, libraryId, tags) {
  if (Number(libraryId) !== 107) return
  const sources = {
    aum: ['CUR_POINT_AUM', 'DIRECT'],
    aum_tier: ['CUR_POINT_AUM', 'AUM_TIER'],
    liquid_aum: ['CUR_DEMAND_DEPOSIT_BALANCE', 'DIRECT'],
    fixed_aum: ['CUR_TIME_DEPOSIT_BALANCE', 'DIRECT'],
    'asset_holder:liquid': ['CUR_DEMAND_DEPOSIT_BALANCE', 'GT', 0],
    'asset_holder:fixed': ['CUR_TIME_DEPOSIT_BALANCE', 'GT', 0],
    aum_missing: ['CUR_POINT_AUM', 'IS_NULL'],
    'product_holding:wealth': ['CUR_HOLDING_WMP_FLAG', 'DIRECT'],
    risk_level: ['CUR_WMP_RISK_ASSESSMENT_LEVEL', 'DIRECT'],
    marketing_excluded: ['CUR_MARKETING_BLACKLIST_FLAG', 'DIRECT'],
    value_score: ['CUR_POINT_AUM', 'DIRECT'],
    product_gap: ['CUR_HOLDING_WMP_FLAG', 'DIRECT'],
    do_not_disturb: ['DO_NOT_DISTURB_CUST_WECOM_TAG_FLAG', 'DIRECT'],
    recent_contact: ['HIST_WECOM_CHAT_LATEST_CONTACT_DATE', 'RECENT_CONTACT']
  }
  form.rows.forEach(row => {
    if (row.tag_ids.length) return
    const source = sources[row.category ? row.metric + ':' + row.category : row.metric]
    if (!source) return
    const matches = tags.filter(tag => tag.fieldName === source[0])
    if (matches.length !== 1) return
    row.tag_ids = [matches[0].tagId]
    row.kind = source[1]
    row.threshold = source[2]
    row.enabled = true
    if (row.metric === 'risk_level') {
      row.useMapping = true
      row.mappings = [1, 2, 3, 4, 5].map(target => ({ source: 'C' + target, target }))
    }
  })
}

export function serializeVersionForm(form, manifest, metrics, existingVersions, label) {
  const version = form.version.trim()
  if (!VERSION_PATTERN.test(version)) throw new Error('请填写三段式版本号，例如 0.1.0。')
  if (existingVersions.some(row => row.version === version)) throw new Error('此版本号已存在，请使用新版本号。')
  const date = form.data_as_of
  const parsedDate = new Date(date + 'T00:00:00Z')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== date) throw new Error('请选择有效的数据日期。')
  if (!VERSION_PATTERN.test(form.binding_version.trim()) || !VERSION_PATTERN.test(form.benchmark_version.trim())) throw new Error('标签绑定版本和对比口径版本须使用三段式版本号。')
  if (!form.benchmark_definition.trim() || form.benchmark_definition.trim().length > 500) throw new Error('请填写对比口径说明（最多 500 字）。')
  const bindings = []
  for (const row of form.rows) {
    if (row.metric === 'customer_count' || !row.enabled || !row.tag_ids.length) continue
    const name = label(row)
    if (!bindingKinds(row.metric).some(kind => kind.value === row.kind)) throw new Error(name + '的计算方式不可用，请重新选择。')
    const count = row.kind === 'RATIO_GT' ? 2 : 1
    if (row.tag_ids.length !== count) throw new Error(name + (count === 2 ? '需要选择分子和分母两个标签。' : '只能选择一个来源标签。'))
    if (row.tag_ids.some(id => !Number.isSafeInteger(id) || id <= 0)) throw new Error(name + '的来源标签无效，请重新选择。')
    const metric = metrics.find(item => item.id === row.metric)
    const binding = { metric: row.metric, tag_ids: row.tag_ids.slice(), kind: row.kind, unit: row.metric === 'org_scope' ? '人' : metric && metric.unit }
    if (!binding.unit) throw new Error(name + '缺少单位定义，请刷新技能后重试。')
    if (row.category) binding.category = row.category
    if (['GT', 'RATIO_GT'].includes(row.kind)) {
      if (typeof row.threshold !== 'number' || !Number.isFinite(row.threshold) || Math.abs(row.threshold) > 1e15) throw new Error('请填写' + name + '的有效阈值。')
      binding.threshold = row.threshold
    }
    if (row.useMapping) {
      if (!mappingAllowed(row)) throw new Error(name + '的当前计算方式不支持码值映射。')
      if (!row.mappings.length || row.mappings.length > 32) throw new Error(name + '需要配置 1 至 32 条码值映射。')
      const mapping = {}
      for (const item of row.mappings) {
        const source = item.source.trim()
        if (!/^[A-Za-z0-9_-]{1,24}$/.test(source)) throw new Error(name + '的源码值须为字母、数字、下划线或短横线，最多 24 位。')
        if (Object.prototype.hasOwnProperty.call(mapping, source)) throw new Error(name + '的源码值重复，请调整。')
        if (!Number.isInteger(item.target) || item.target < 0 || item.target > mappingMaximum(row.metric)) throw new Error(name + '的目标值超出允许范围。')
        // 使用 defineProperty，避免特殊源码值影响普通对象的原型。
        Object.defineProperty(mapping, source, { value: item.target, enumerable: true })
      }
      binding.enum_map = mapping
    }
    bindings.push(binding)
  }
  if (!bindings.length) throw new Error('请至少关联一个标签后保存草稿。')
  if (bindings.length > 60) throw new Error('关联指标不能超过 60 项。')
  const suitability = {}
  form.suitability.filter(item => item.enabled).forEach(item => {
    if (!Number.isInteger(item.minimum) || item.minimum < 0 || item.minimum > 10) throw new Error('请填写' + PRODUCT_CATEGORIES[item.category] + '的最低风险等级（0 至 10）。')
    suitability[item.category] = item.minimum
  })
  return { skill_id: manifest.id, version, data_as_of: date, binding_version: form.binding_version.trim(), benchmark_version: form.benchmark_version.trim(), benchmark_definition: form.benchmark_definition.trim(), bindings, suitability }
}
