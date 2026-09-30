<template>
  <div class="app-container insight-management">
    <header class="insight-header">
      <div><h2>洞察技能</h2><p>查看技能用途与关联标签，管理可用版本。</p></div>
      <el-button :disabled="!libraryId || loading" @click="openAudit">运行记录</el-button>
    </header>
    <el-form class="insight-filters" :inline="true" @submit.native.prevent>
      <el-form-item label="标签库" for="insight-library">
        <el-select id="insight-library" v-model="libraryId" filterable :loading="librariesLoading" placeholder="请选择标签库" @change="changeLibrary">
          <el-option v-for="item in libraries" :key="item.libraryId" :label="item.libraryName" :value="item.libraryId" />
        </el-select>
      </el-form-item>
      <el-form-item label="技能" for="insight-search"><el-input id="insight-search" v-model="keyword" label="搜索技能或关联标签" clearable placeholder="搜索技能或关联标签" prefix-icon="el-icon-search" /></el-form-item>
      <el-form-item label="状态" for="insight-status"><el-select id="insight-status" v-model="statusFilter" clearable placeholder="全部状态"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      <el-button icon="el-icon-refresh" :loading="loading" :disabled="!libraryId" @click="load">刷新</el-button>
    </el-form>
    <div v-if="error" class="insight-error" role="alert"><span>{{ error }}</span><el-button type="text" @click="libraries.length ? load() : loadLibraries()">重试</el-button></div>
    <el-table v-loading="loading" :data="filteredSkills" row-key="id" :empty-text="emptyText">
      <el-table-column prop="name" label="技能名称" min-width="190" />
      <el-table-column prop="question" label="用途" min-width="260" />
      <el-table-column label="关联标签" min-width="280"><template slot-scope="scope">
        <span v-if="!scope.row.tags.length" class="insight-muted">尚未关联标签</span>
        <template v-else>
          <span class="insight-tag-summary">{{ scope.row.tags.slice(0, 3).join('、') }}</span>
          <el-tooltip v-if="scope.row.tags.length > 3" :content="scope.row.tags.join('、')" placement="top">
            <el-button type="text" class="insight-tag-more" :aria-label="'查看' + scope.row.name + '的全部关联标签'" @click="openSkill(scope.row)">共 {{ scope.row.tags.length }} 项</el-button>
          </el-tooltip>
        </template>
      </template></el-table-column>
      <el-table-column label="状态" width="110"><template slot-scope="scope"><el-tag size="small" :type="statusType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="110" fixed="right"><template slot-scope="scope"><el-button type="text" :disabled="loading" :aria-label="'管理' + scope.row.name" @click="openSkill(scope.row)">查看 / 管理</el-button></template></el-table-column>
    </el-table>
    <p v-if="libraryId && !loading && !error && skills.length" class="insight-footnote">共 {{ filteredSkills.length }} 项技能。已发布技能可在智能体工作台中使用。</p>

    <el-drawer :title="selectedSkill ? selectedSkill.name : '技能详情'" :visible.sync="detailOpen" size="min(680px, 100vw)">
      <div v-if="selectedSkill" class="insight-detail" v-loading="loading">
        <p class="insight-purpose">{{ selectedSkill.question }}</p>
        <h3>关联标签</h3>
        <div class="insight-tags"><el-tag v-for="name in selectedSkill.tags" :key="name" size="small" type="info">{{ name }}</el-tag><span v-if="!selectedSkill.tags.length" class="insight-muted">尚未关联标签</span></div>
        <el-collapse class="insight-required"><el-collapse-item title="所需数据" name="metrics"><span>{{ requiredNames(selectedSkill.manifest).join('、') }}</span></el-collapse-item></el-collapse>
        <div class="insight-section-heading"><h3>版本管理</h3><el-button v-hasPermi="['taglibrary:insight:edit']" size="small" :disabled="!!pending" @click="openDraft">新增版本</el-button></div>
        <p v-if="detailError" class="insight-error" role="alert">{{ detailError }}</p>
        <el-table :data="selectedVersions" empty-text="暂无版本，新增版本后可配置关联标签。">
          <el-table-column prop="version" label="版本" width="90" />
          <el-table-column label="状态" width="100"><template slot-scope="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column>
          <el-table-column label="操作" min-width="250"><template slot-scope="scope">
            <el-button type="text" :disabled="!!pending" @click="showBindings(scope.row)">关联标签</el-button>
            <el-button type="text" :disabled="!!pending" @click="trial(scope.row)">查看示例</el-button>
            <el-button v-if="scope.row.status === 'DRAFT'" v-hasPermi="['taglibrary:insight:review']" type="text" :loading="pending === 'review:' + scope.row.version" :disabled="!!pending" @click="changeVersion('review', scope.row)">复核</el-button>
            <el-button v-if="['REVIEWED', 'RETIRED'].includes(scope.row.status)" v-hasPermi="['taglibrary:insight:publish']" type="text" :loading="pending === 'publish:' + scope.row.version" :disabled="!!pending" @click="changeVersion('publish', scope.row)">{{ scope.row.status === 'RETIRED' ? '重新发布' : '发布' }}</el-button>
            <el-button v-if="scope.row.status === 'PUBLISHED'" v-hasPermi="['taglibrary:insight:publish']" type="text" :loading="pending === 'retire:' + scope.row.version" :disabled="!!pending" @click="changeVersion('retire', scope.row)">下线</el-button>
          </template></el-table-column>
        </el-table>
      </div>
    </el-drawer>
    <el-dialog :title="bindingTitle" :visible.sync="bindingsOpen" width="min(620px, 92vw)">
      <el-table :data="bindingRows" empty-text="此版本尚未关联标签。"><el-table-column prop="metric" label="用途" min-width="180" /><el-table-column prop="tags" label="标签名称" min-width="240" /></el-table>
    </el-dialog>
    <el-dialog title="新增技能版本" :visible.sync="editing" width="min(900px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <insight-version-form v-if="editing && selectedSkill" :manifest="selectedSkill.manifest" :metrics="metrics" :library-id="libraryId" :previous="draftPrevious" :versions="selectedVersions" :tag-names="tagNames" :saving="saving" :error="draftError" @save="save" @cancel="editing = false" @clear-error="draftError = ''" />
    </el-dialog>
    <el-dialog title="洞察示例" :visible.sync="trialOpen" width="min(760px, 92vw)">
      <p class="insight-dialog-hint">使用模拟数据展示技能输出，不代表真实客群结果。</p>
      <el-table :data="trialFacts" empty-text="此技能暂无可展示的示例。"><el-table-column prop="label" label="指标" min-width="200" /><el-table-column prop="value" label="数值" /><el-table-column prop="unit" label="单位" width="80" /></el-table>
    </el-dialog>
    <el-dialog title="运行记录" :visible.sync="auditOpen" width="min(960px, 94vw)">
      <div v-if="auditError" class="insight-error" role="alert"><span>{{ auditError }}</span><el-button type="text" @click="openAudit">重试</el-button></div>
      <el-table v-loading="auditLoading" :data="audit" empty-text="暂无运行记录。">
        <el-table-column label="状态" width="110"><template slot-scope="scope">{{ runStatusLabel(scope.row.status) }}</template></el-table-column>
        <el-table-column label="耗时" width="100"><template slot-scope="scope">{{ (Number(scope.row.elapsed_ms || 0) / 1000).toFixed(1) }} 秒</template></el-table-column>
        <el-table-column prop="rating" label="评分" width="70" /><el-table-column prop="comment_text" label="反馈" min-width="220" show-overflow-tooltip /><el-table-column prop="create_time" label="时间" min-width="170" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script>
import InsightVersionForm from './components/InsightVersionForm'
import { listLibrary } from '@/api/taglibrary/library'
import { getTag } from '@/api/taglibrary/tag'
import { checkPermi } from '@/utils/permission'
import { insightCatalog, insightAudit, saveInsightVersion, reviewInsightVersion, publishInsightVersion, retireInsight, trialInsight } from '@/api/taglibrary/insight'

const STATUS = { UNCONFIGURED: '待配置', DRAFT: '草稿', REVIEWED: '待发布', PUBLISHED: '已发布', RETIRED: '已下线' }
const CATEGORIES = { liquid: '流动资产', fixed: '定期资产', investment: '投资资产', wealth: '理财', fund: '基金', insurance: '保险' }

export default {
  name: 'InsightSkill',
  components: { InsightVersionForm },
  data() {
    return {
      libraryId: undefined, libraries: [], librariesLoading: false, skills: [], versions: [], metrics: [], tagNames: {},
      loading: false, loadSequence: 0, error: '', keyword: '', statusFilter: '', selectedId: '', detailOpen: false, detailError: '', pending: '',
      bindingsOpen: false, bindingTitle: '', bindingRows: [], editing: false, saving: false, draftPrevious: {}, draftError: '',
      trialOpen: false, trialFacts: [], auditOpen: false, auditLoading: false, auditError: '', audit: [], auditSequence: 0,
      statusOptions: Object.keys(STATUS).map(value => ({ value, label: STATUS[value] }))
    }
  },
  computed: {
    skillRows() {
      return this.skills.map(skill => {
        const manifest = skill.manifest
        const versions = this.versionsFor(manifest.id)
        const current = versions.find(row => row.status === 'PUBLISHED') || versions[0]
        return { id: manifest.id, name: manifest.name, question: manifest.question, manifest, current, status: current ? current.status : 'UNCONFIGURED', tags: current ? this.boundNames(current) : [] }
      })
    },
    filteredSkills() {
      const keyword = this.keyword.trim().toLowerCase()
      return this.skillRows.filter(row => (!this.statusFilter || row.status === this.statusFilter) && (!keyword || [row.name, row.question, ...row.tags].join(' ').toLowerCase().includes(keyword)))
    },
    selectedSkill() { return this.skillRows.find(row => row.id === this.selectedId) },
    selectedVersions() { return this.versionsFor(this.selectedId) },
    emptyText() {
      if (this.loading) return '正在加载技能…'
      if (this.error) return '技能读取失败，请重试。'
      if (!this.librariesLoading && !this.libraries.length) return '暂无可访问的标签库。'
      if (!this.libraryId) return '请选择标签库。'
      return this.skills.length ? '没有匹配的技能，请调整搜索或状态。' : '当前标签库暂无洞察技能。'
    }
  },
  created() { this.loadLibraries() },
  methods: {
    async loadLibraries() {
      this.librariesLoading = true
      this.error = ''
      try {
        const r = await listLibrary({ pageNum: 1, pageSize: 1000 })
        this.libraries = r.rows || []
        const requested = this.$route.query.libraryId
        const library = this.libraries.find(item => String(item.libraryId) === String(requested)) || this.libraries.find(item => item.libraryName === '个人客户经营标签库') || this.libraries[0]
        if (library) { this.libraryId = library.libraryId; await this.load() }
      } catch (e) { this.error = '标签库读取失败，请重试。' } finally { this.librariesLoading = false }
    },
    changeLibrary() {
      this.detailOpen = false
      this.editing = false
      this.bindingsOpen = false
      this.trialOpen = false
      this.auditOpen = false
      this.auditSequence++
      this.auditLoading = false
      this.selectedId = ''
      this.keyword = ''
      this.statusFilter = ''
      this.load()
    },
    async load() {
      const sequence = ++this.loadSequence
      const library = this.libraryId
      this.skills = []
      this.versions = []
      this.metrics = []
      this.tagNames = {}
      this.error = ''
      if (!library) { this.loading = false; return }
      this.loading = true
      try {
        const r = await insightCatalog(library)
        if (sequence !== this.loadSequence) return
        this.skills = r.data.skills || []
        this.versions = r.data.versions || []
        this.metrics = r.data.metrics || []
        await this.loadTagNames(sequence, library)
      } catch (e) {
        if (sequence === this.loadSequence) this.error = '技能读取失败，请重试。'
      } finally { if (sequence === this.loadSequence) this.loading = false }
    },
    async loadTagNames(sequence, library) {
      if (!checkPermi(['taglibrary:tag:query'])) return
      const ids = [...new Set(this.versions.flatMap(row => this.definition(row).bindings || []).flatMap(binding => binding.tag_ids || []))]
      const names = {}
      // 只读取已关联标签；分批限制并发，不扫描整个标签库。
      for (let offset = 0; offset < ids.length; offset += 8) {
        const batch = ids.slice(offset, offset + 8)
        const results = await Promise.allSettled(batch.map(id => getTag(id)))
        if (sequence !== this.loadSequence) return
        results.forEach((result, index) => {
          if (result.status === 'fulfilled' && result.value.data && String(result.value.data.libraryId) === String(library)) names[batch[index]] = result.value.data.tagName
        })
      }
      if (sequence === this.loadSequence) this.tagNames = names
    },
    definition(row) {
      try {
        const value = JSON.parse(row.definition_json)
        if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
        return { ...value, bindings: Array.isArray(value.bindings) ? value.bindings.filter(binding => binding && typeof binding === 'object' && binding.metric !== 'customer_count').map(binding => ({ ...binding, tag_ids: Array.isArray(binding.tag_ids) ? binding.tag_ids : [] })) : [] }
      } catch (_) { return {} }
    },
    versionsFor(id) {
      return this.versions.filter(row => row.skill_id === id).slice().sort((a, b) => {
        const left = String(a.version).split('.').map(Number), right = String(b.version).split('.').map(Number)
        for (let i = 0; i < 3; i++) { const difference = (right[i] || 0) - (left[i] || 0); if (difference) return difference }
        return 0
      })
    },
    metricName(id) { const metric = this.metrics.find(item => item.id === id); return metric ? metric.name : id === 'org_scope' ? '所属机构' : '其他数据' },
    requiredNames(manifest) { return (manifest.metrics || []).map(id => this.metricName(id)) },
    tagName(id) { return this.tagNames[id] || '标签名称不可用' },
    boundNames(row) { return [...new Set((this.definition(row).bindings || []).flatMap(binding => (binding.tag_ids || []).map(id => this.tagName(id))))] },
    statusLabel(value) { return STATUS[value] || '状态未知' },
    statusType(value) { return { PUBLISHED: 'success', DRAFT: 'warning', REVIEWED: 'warning', RETIRED: 'info', UNCONFIGURED: 'info' }[value] || 'info' },
    runStatusLabel(value) { return { COMPLETED: '已完成', FAILED: '失败', RUNNING: '运行中', QUEUED: '排队中', CANCELLED: '已取消', INTERRUPTED: '已中断' }[value] || '待确认' },
    openSkill(row) { this.selectedId = row.id; this.detailError = ''; this.detailOpen = true },
    showBindings(row) {
      this.bindingTitle = row.version + ' · 关联标签'
      this.bindingRows = (this.definition(row).bindings || []).map(binding => ({ metric: this.metricName(binding.metric) + (CATEGORIES[binding.category] ? ' · ' + CATEGORIES[binding.category] : ''), tags: (binding.tag_ids || []).map(id => this.tagName(id)).join('、') || '尚未关联标签' }))
      this.bindingsOpen = true
    },
    openDraft() {
      const current = this.selectedVersions[0]
      this.draftPrevious = current ? { ...this.definition(current), version: current.version } : {}
      this.draftError = ''
      this.editing = true
    },
    async save(body) {
      if (this.saving) return
      this.draftError = ''
      this.saving = true
      const library = this.libraryId
      try {
        await saveInsightVersion(library, body)
        if (library !== this.libraryId) return
        this.editing = false
        this.$modal.msgSuccess('草稿已保存')
        await this.load()
      } catch (e) { if (library === this.libraryId) this.draftError = e.message || '保存失败，请检查配置后重试。' } finally { this.saving = false }
    },
    async trial(row) {
      if (this.pending) return
      const library = this.libraryId
      this.pending = 'trial:' + row.version
      this.detailError = ''
      try {
        const r = await trialInsight(library, row.skill_id, row.version)
        if (library !== this.libraryId) return
        const results = r.data.report.results || []
        this.trialFacts = results.length ? results[0].facts : []
        this.trialOpen = true
      } catch (e) { if (library === this.libraryId) this.detailError = e.message || '示例读取失败，请重试。' } finally { this.pending = '' }
    },
    async changeVersion(action, row) {
      if (this.pending) return
      const library = this.libraryId
      const messages = { review: '确认已核对标签绑定与业务口径？复核通过后可发布此版本。', publish: '确认发布 ' + row.version + ' 版本？发布后将替换当前使用的版本。', retire: '确认下线此技能？下线后将停止提供该技能的洞察服务。' }
      this.pending = action + ':' + row.version
      this.detailError = ''
      try {
        await this.$modal.confirm(messages[action])
        if (library !== this.libraryId) return
        if (action === 'review') await reviewInsightVersion(library, row.skill_id, row.version)
        if (action === 'publish') await publishInsightVersion(library, row.skill_id, row.version)
        if (action === 'retire') await retireInsight(library, row.skill_id)
        if (library !== this.libraryId) return
        this.$modal.msgSuccess({ review: '复核完成', publish: '已发布', retire: '已下线' }[action])
        await this.load()
      } catch (e) { if (e !== 'cancel' && e !== 'close' && library === this.libraryId) this.detailError = e.message || '操作失败，请重试。' }
      finally { this.pending = '' }
    },
    async openAudit() {
      const sequence = ++this.auditSequence, library = this.libraryId
      this.auditOpen = true
      this.auditLoading = true
      this.auditError = ''
      this.audit = []
      try { const r = await insightAudit(library); if (sequence === this.auditSequence) this.audit = r.data || [] }
      catch (e) { if (sequence === this.auditSequence) this.auditError = '运行记录读取失败，请重试。' }
      finally { if (sequence === this.auditSequence) this.auditLoading = false }
    }
  }
}
</script>

<style scoped>
.insight-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 24px; }
.insight-header h2 { margin: 0 0 8px; font-size: 20px; font-weight: 600; color: #303133; }
.insight-header p, .insight-footnote, .insight-dialog-hint { margin: 0; color: #606266; font-size: 13px; line-height: 1.7; }
.insight-filters { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 16px; }
.insight-filters .el-form-item { display: inline-flex; align-items: center; margin-right: 0; margin-bottom: 16px; }
.insight-filters .el-select { width: 210px; }
.insight-filters .el-form-item:nth-child(2) .el-input { width: 230px; }
.insight-filters .el-form-item:last-of-type .el-select { width: 130px; }
.insight-muted { color: #606266; }
.insight-tag-summary { overflow-wrap: anywhere; }
.insight-tag-more { margin-left: 8px; }
.insight-footnote { margin-top: 16px; }
.insight-error { display: flex; align-items: center; gap: 16px; margin: 0 0 16px; color: #b42318; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.insight-detail { padding: 0 24px 24px; }
.insight-purpose { margin: 0 0 24px; font-size: 14px; line-height: 1.7; color: #606266; }
.insight-detail h3 { margin: 24px 0 12px; font-size: 15px; font-weight: 600; color: #303133; }
.insight-tags { display: flex; flex-wrap: wrap; gap: 8px; line-height: 1.7; }
.insight-tags .el-tag { height: auto; white-space: normal; }
.insight-required { margin-top: 16px; }
.insight-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.insight-dialog-hint { margin-bottom: 16px; }
.insight-management ::v-deep .el-table .cell { word-break: normal; overflow-wrap: anywhere; }
.insight-management ::v-deep .el-button--text { color: #1769b0; }
.insight-management ::v-deep .el-button--text:hover { color: #124e84; }
.insight-management ::v-deep .el-button--text.is-disabled { color: #909399; }
.insight-management ::v-deep .el-button:focus-visible, .insight-management ::v-deep .el-collapse-item__header:focus-visible { outline: 2px solid #1769b0; outline-offset: 2px; }
.insight-management ::v-deep .el-tag--success { color: #27743a; }
.insight-management ::v-deep .el-tag--warning { color: #8a5b0f; }
.insight-management ::v-deep .el-tag--info, .insight-management ::v-deep .el-table__empty-text { color: #606266; }
.insight-management ::v-deep .el-input__inner::placeholder { color: #75777d; }
.insight-management ::v-deep .el-drawer__body { overflow-y: auto; }
.insight-management ::v-deep .el-drawer__header { color: #303133; margin-bottom: 24px; }
.insight-management ::v-deep .el-dialog__body { padding-top: 12px; }
.insight-management ::v-deep .el-textarea + .insight-error { margin-top: 12px; }
@media (max-width: 600px) {
  .insight-header { align-items: flex-start; }
  .insight-filters { display: block; }
  .insight-filters .el-form-item { display: flex; }
  .insight-filters ::v-deep .el-form-item__content { flex: 1; min-width: 0; }
  .insight-filters .el-select, .insight-filters .el-form-item:nth-child(2) .el-input, .insight-filters .el-form-item:last-of-type .el-select { width: 100%; }
  .insight-detail { padding: 0 16px 16px; }
}
</style>
