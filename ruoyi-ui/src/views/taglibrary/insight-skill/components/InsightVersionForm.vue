<template>
  <div class="version-editor">
    <p class="version-context">{{ manifest.name }}<span v-if="previous.version"> · 已沿用 {{ previous.version }} 的配置</span></p>
    <el-tabs v-model="tab">
      <el-tab-pane label="基本信息" name="basic">
        <el-form :model="form" label-position="top" size="small" :disabled="saving" @submit.native.prevent>
          <div class="version-grid">
            <el-form-item label="版本号" required for="insight-new-version"><el-input id="insight-new-version" v-model="form.version" label="版本号" placeholder="例如 0.1.0" maxlength="24" /></el-form-item>
            <el-form-item label="数据日期" required for="insight-data-date"><el-date-picker id="insight-data-date" v-model="form.data_as_of" type="date" value-format="yyyy-MM-dd" format="yyyy-MM-dd" placeholder="选择实际数据日期" /></el-form-item>
          </div>
          <el-form-item label="对比口径说明" required><el-input v-model="form.benchmark_definition" label="对比口径说明" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="填写对比客户范围和统计口径" /></el-form-item>
          <el-collapse class="version-advanced"><el-collapse-item title="版本设置" name="versions">
            <div class="version-grid">
              <el-form-item label="标签绑定版本"><el-input v-model="form.binding_version" label="标签绑定版本" placeholder="例如 0.1.0" maxlength="24" /></el-form-item>
              <el-form-item label="对比口径版本"><el-input v-model="form.benchmark_version" label="对比口径版本" placeholder="例如 0.1.0" maxlength="24" /></el-form-item>
            </div>
          </el-collapse-item></el-collapse>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="关联标签" name="bindings">
        <div v-if="tagError" class="version-error" role="alert"><span>{{ tagError }}</span><el-button type="text" :loading="tagsLoading" @click="loadTags">重试</el-button></div>
        <p v-else class="version-hint">客户数在使用技能时按当前客群实时统计，无需配置。其余指标按中文名称选择标签。</p>
        <div class="version-bindings" v-loading="tagsLoading">
          <section v-for="row in metricRows" :key="row.key" class="version-binding">
            <div class="version-binding-heading">
              <el-checkbox v-if="['product_holding', 'org_scope'].includes(row.metric)" v-model="row.enabled" :disabled="saving">{{ rowLabel(row) }}</el-checkbox>
              <strong v-else>{{ rowLabel(row) }}</strong>
              <span class="version-unit">{{ metricUnit(row.metric) }}</span>
            </div>
            <div v-if="row.enabled" class="version-binding-controls">
              <div class="version-field">
                <label :for="sourceId(row, 0)">{{ row.kind === 'RATIO_GT' ? '分子标签' : '来源标签' }}</label>
                <el-select :id="sourceId(row, 0)" :value="row.tag_ids[0]" filterable clearable :disabled="saving || tagsLoading" placeholder="搜索中文标签名称" no-data-text="暂无可选标签" @input="setSource(row, 0, $event)">
                  <el-option v-for="tag in optionsFor(row)" :key="tag.tagId" :value="tag.tagId" :label="tag.tagName" :disabled="tag.unavailable" />
                </el-select>
              </div>
              <div v-if="row.kind === 'RATIO_GT'" class="version-field">
                <label :for="sourceId(row, 1)">分母标签</label>
                <el-select :id="sourceId(row, 1)" :value="row.tag_ids[1]" filterable clearable :disabled="saving || tagsLoading" placeholder="选择分母标签" no-data-text="暂无可选标签" @input="setSource(row, 1, $event)">
                  <el-option v-for="tag in optionsFor(row)" :key="tag.tagId" :value="tag.tagId" :label="tag.tagName" :disabled="tag.unavailable" />
                </el-select>
              </div>
              <div class="version-field">
                <label :for="'kind-' + row.key">计算方式</label>
                <el-select :id="'kind-' + row.key" v-model="row.kind" :disabled="saving" @change="changeKind(row)"><el-option v-for="kind in kinds(row.metric)" :key="kind.value" :value="kind.value" :label="kind.label" /></el-select>
              </div>
              <div v-if="['GT', 'RATIO_GT'].includes(row.kind)" class="version-field">
                <label>阈值</label><el-input-number v-model="row.threshold" :disabled="saving" :min="-1e15" :max="1e15" :controls="false" :label="rowLabel(row) + '阈值'" placeholder="填写阈值" />
                <span v-if="row.kind === 'RATIO_GT'" class="version-hint">填写比值，例如 0.3 表示 30%。</span>
              </div>
              <div v-if="canMap(row)" class="version-mapping">
                <el-checkbox v-model="row.useMapping" :disabled="saving" @change="enableMapping(row)">设置码值映射</el-checkbox>
                <div v-if="row.useMapping" class="version-mapping-fields">
                  <p class="version-hint">将标签的原始码值转换为数值。{{ mappingMax(row.metric) === 1 ? '0 表示否，1 表示是。' : '目标值范围为 0 至 12。' }}</p>
                  <div v-for="(item, index) in row.mappings" :key="index" class="version-mapping-row">
                    <el-input v-model="item.source" size="small" :disabled="saving" :label="rowLabel(row) + '第' + (index + 1) + '条源码值'" maxlength="24" placeholder="源码值" />
                    <el-input-number v-model="item.target" size="small" :disabled="saving" :min="0" :max="mappingMax(row.metric)" :precision="0" :controls="false" :label="rowLabel(row) + '第' + (index + 1) + '条目标值'" placeholder="目标值" />
                    <el-button type="text" :disabled="saving" :aria-label="'删除' + rowLabel(row) + '第' + (index + 1) + '条映射'" @click="row.mappings.splice(index, 1)">删除</el-button>
                  </div>
                  <el-button type="text" :disabled="saving || row.mappings.length >= 32" @click="row.mappings.push({ source: '', target: undefined })">添加映射</el-button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </el-tab-pane>
      <el-tab-pane v-if="manifest.metrics.includes('suitability') || form.suitability.some(item => item.enabled)" label="产品适当性" name="suitability">
        <p class="version-hint">为需要计算机会人数的品类配置最低风险等级。</p>
        <div v-for="item in form.suitability" :key="item.category" class="version-suitability">
          <el-checkbox v-model="item.enabled" :disabled="saving">{{ productCategories[item.category] }}</el-checkbox>
          <div v-if="item.enabled" class="version-field"><label>最低风险等级</label><el-input-number v-model="item.minimum" :disabled="saving" :min="0" :max="10" :precision="0" :label="productCategories[item.category] + '最低风险等级'" /></div>
        </div>
      </el-tab-pane>
    </el-tabs>
    <p v-if="validationError || error" class="version-error" role="alert">{{ validationError || error }}</p>
    <footer class="version-actions">
      <el-button :disabled="saving" @click="$emit('cancel')">取消</el-button>
      <el-button v-if="tab === 'basic'" :disabled="saving" @click="tab = 'bindings'">配置关联标签</el-button>
      <el-button v-else :disabled="saving" @click="tab = 'basic'">基本信息</el-button>
      <el-button type="primary" :loading="saving" :disabled="tagsLoading || !!tagError" @click="submit">保存草稿</el-button>
    </footer>
  </div>
</template>

<script>
import { listTag } from '@/api/taglibrary/tag'
import { activeSnapshot, eligibleTags } from '@/api/taglibrary/semantic'
import { checkPermi } from '@/utils/permission'
import { PRODUCT_CATEGORIES, ASSET_CATEGORIES, bindingKinds, mappingAllowed, mappingMaximum, createVersionForm, serializeVersionForm, applyPersonalCustomerBindings } from '../versionForm'

export default {
  name: 'InsightVersionForm',
  props: {
    manifest: { type: Object, required: true }, metrics: { type: Array, required: true }, libraryId: { type: [Number, String], required: true },
    previous: { type: Object, default: () => ({}) }, versions: { type: Array, default: () => [] }, tagNames: { type: Object, default: () => ({}) }, saving: Boolean, error: String
  },
  data() { return { form: createVersionForm(this.manifest, this.previous), tab: 'basic', options: [], tagsLoading: false, tagError: '', validationError: '', tagSequence: 0, productCategories: PRODUCT_CATEGORIES } },
  computed: {
    metricRows() { return this.form.rows }
  },
  created() { this.loadTags() },
  beforeDestroy() { this.tagSequence++ },
  methods: {
    kinds: bindingKinds, canMap: mappingAllowed, mappingMax: mappingMaximum,
    metricName(id) { const metric = this.metrics.find(item => item.id === id); return metric ? metric.name : id === 'org_scope' ? '所属机构' : '其他数据' },
    metricUnit(id) { const metric = this.metrics.find(item => item.id === id); return metric ? metric.unit === 'pp' ? '百分点' : metric.unit : '' },
    rowLabel(row) { const category = PRODUCT_CATEGORIES[row.category] || ASSET_CATEGORIES[row.category]; return this.metricName(row.metric) + (category ? ' · ' + category : '') + (row.metric === 'org_scope' ? '（可选）' : '') },
    sourceId(row, index) { return 'source-' + row.key + '-' + index },
    setSource(row, index, value) {
      const ids = row.tag_ids.slice()
      ids[index] = value === '' ? undefined : value
      while (ids.length && ids[ids.length - 1] === undefined) ids.pop()
      row.tag_ids = ids
    },
    changeKind(row) { if (row.kind !== 'RATIO_GT') row.tag_ids = row.tag_ids.slice(0, 1); if (!this.canMap(row)) row.useMapping = false },
    enableMapping(row) { if (row.useMapping && !row.mappings.length) row.mappings.push({ source: '', target: undefined }) },
    optionsFor(row) {
      const options = this.options.slice()
      row.tag_ids.forEach(id => { if (id && !options.some(tag => tag.tagId === id)) options.push({ tagId: id, tagName: (this.tagNames[id] || '原关联标签') + '（不可用，请重新选择）', unavailable: true }) })
      return options
    },
    async loadTags() {
      const sequence = ++this.tagSequence
      this.tagsLoading = true
      this.tagError = ''
      this.options = []
      try {
        if (!checkPermi(['taglibrary:tag:list'])) throw new Error('当前账号无法读取标签候选，请联系管理员开通标签列表权限。')
        let eligible
        if (checkPermi(['taglibrary:semantic:list'])) {
          const active = await activeSnapshot(this.libraryId)
          const r = await eligibleTags(this.libraryId, active.data.snapshot_id)
          eligible = new Set((r.data || []).map(Number))
        }
        const tags = []
        let pageNum = 1
        while (true) {
          const r = await listTag({ libraryId: this.libraryId, status: '2', sourceStatus: 'AVAILABLE', pageNum, pageSize: 500 })
          if (sequence !== this.tagSequence) return
          const rows = r.rows || []
          tags.push(...rows)
          if (!rows.length || tags.length >= Number(r.total || rows.length)) break
          pageNum++
        }
        if (sequence !== this.tagSequence) return
        this.options = tags.filter(tag => String(tag.libraryId) === String(this.libraryId) && tag.status === '2' && tag.sourceStatus === 'AVAILABLE' && tag.isObjectKey !== '1' && (!eligible || eligible.has(Number(tag.tagId)))).map(tag => ({ tagId: Number(tag.tagId), tagName: tag.tagName, fieldName: tag.fieldName }))
        if (!(this.previous.bindings || []).length) applyPersonalCustomerBindings(this.form, this.manifest, this.libraryId, this.options)
        if (!this.options.length) this.tagError = '当前标签库暂无可关联的标签，请先上线标签后重试。'
      } catch (e) { if (sequence === this.tagSequence) this.tagError = e.message || '标签候选读取失败，请重试。' }
      finally { if (sequence === this.tagSequence) this.tagsLoading = false }
    },
    submit() {
      if (this.saving || this.tagsLoading || this.tagError) return
      this.validationError = ''
      this.$emit('clear-error')
      try {
        const body = serializeVersionForm(this.form, this.manifest, this.metrics, this.versions, this.rowLabel)
        const unavailable = body.bindings.find(binding => binding.tag_ids.some(id => !this.options.some(tag => tag.tagId === id)))
        if (unavailable) throw new Error(this.rowLabel(unavailable) + '包含不可用的标签，请重新选择。')
        this.$emit('save', body)
      } catch (e) {
        this.validationError = e.message || '配置有误，请检查后重试。'
        this.tab = /版本|日期|口径/.test(this.validationError) ? 'basic' : /最低风险等级/.test(this.validationError) ? 'suitability' : 'bindings'
      }
    }
  }
}
</script>

<style scoped>
.version-context { margin: 0 0 12px; color: #303133; font-size: 14px; line-height: 1.7; }
.version-context span, .version-hint, .version-unit { color: #606266; font-size: 13px; line-height: 1.7; }
.version-hint { margin: 0 0 12px; }
.version-editor ::v-deep .el-tab-pane { max-height: 55vh; overflow-y: auto; padding: 4px 8px 8px 0; }
.version-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.version-editor .el-date-editor, .version-field .el-select, .version-field .el-input-number { width: 100%; }
.version-editor ::v-deep .el-form-item__label { padding-bottom: 4px; color: #303133; }
.version-binding { padding: 16px 0; border-bottom: 1px solid #ebeef5; }
.version-binding:first-child { padding-top: 0; }
.version-binding-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.version-binding-heading strong { font-size: 14px; font-weight: 500; color: #303133; }
.version-binding-controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; }
.version-field label { display: block; margin-bottom: 6px; color: #606266; font-size: 13px; line-height: 1.5; }
.version-mapping { grid-column: 1 / -1; }
.version-mapping-fields { margin-top: 12px; }
.version-mapping-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; align-items: center; gap: 12px; margin-bottom: 8px; }
.version-mapping-row .el-input-number { width: 100%; }
.version-suitability { display: flex; align-items: center; gap: 24px; padding: 16px 0; border-bottom: 1px solid #ebeef5; }
.version-suitability .version-field { max-width: 220px; }
.version-advanced { margin-top: 16px; }
.version-actions { display: flex; justify-content: flex-end; gap: 12px; padding-top: 20px; }
.version-actions .el-button + .el-button { margin-left: 0; }
.version-error { display: flex; gap: 12px; align-items: center; margin: 12px 0 0; color: #b42318; font-size: 13px; line-height: 1.7; }
.version-editor ::v-deep .el-button--text, .version-editor ::v-deep .el-tabs__item.is-active, .version-editor ::v-deep .el-checkbox__input.is-checked + .el-checkbox__label { color: #1769b0; }
.version-editor ::v-deep .el-tabs__active-bar { background-color: #1769b0; }
.version-editor ::v-deep .el-button--primary { background-color: #1769b0; border-color: #1769b0; }
.version-editor ::v-deep .el-button--primary:hover { background-color: #124e84; border-color: #124e84; }
.version-editor ::v-deep .el-input__count { color: #606266; }
.version-editor ::v-deep .el-input__inner::placeholder, .version-editor ::v-deep .el-textarea__inner::placeholder { color: #75777d; }
.version-editor ::v-deep .el-button:focus-visible { outline: 2px solid #1769b0; outline-offset: 2px; }
@media (max-width: 600px) {
  .version-grid, .version-binding-controls { grid-template-columns: minmax(0, 1fr); }
  .version-actions { gap: 8px; flex-wrap: wrap; }
  .version-suitability { align-items: flex-start; flex-direction: column; gap: 12px; }
}
</style>
