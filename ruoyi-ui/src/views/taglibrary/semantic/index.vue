<template>
  <div class="app-container">
    <el-form :inline="true" size="small" @submit.native.prevent="load">
      <el-form-item label="标签库">
        <el-select v-model="libraryId" placeholder="请选择标签库" filterable clearable style="width: 240px" @change="handleLibraryChange">
          <el-option v-for="lib in libraries" :key="lib.libraryId" :label="lib.libraryName" :value="lib.libraryId" />
        </el-select>
      </el-form-item>
      <el-form-item><el-button type="primary" icon="el-icon-search" :loading="loading" @click="load">加载语义资产</el-button></el-form-item>
      <el-form-item>
        <el-button v-hasPermi="['taglibrary:semantic:bootstrap']" icon="el-icon-download" :loading="exporting" :disabled="!libraryId" @click="exportCurrentFreeze">导出实时冻结</el-button>
      </el-form-item>
      <el-form-item>
        <el-button v-hasPermi="['taglibrary:semantic:bootstrap']" type="primary" plain icon="el-icon-document-add" :loading="expanding" :disabled="!libraryId" @click="expandDrafts">生成并导入规则草稿</el-button>
      </el-form-item>
      <el-form-item>
        <el-button v-hasPermi="['taglibrary:semantic:bootstrap']" icon="el-icon-upload2" :loading="importing" :disabled="!libraryId" @click="pickImportFile">导入规则草稿</el-button>
        <input ref="importFile" type="file" accept=".jsonl,.txt" style="display: none" @change="handleImportFile">
      </el-form-item>
    </el-form>
    <el-alert v-if="!loadedLibrary" title="选择标签库，维护语义草稿、复核依据和检索词典。" type="info" :closable="false" />
    <template v-else>
      <el-alert title="「生成并导入规则草稿」会按当前库导出实时冻结、运行规则扩展并导入。也可手动导入已生成的 rule_init_result.jsonl（含 tag_semantic / concept / code_value_semantic）。semantic-freeze-*.jsonl 不能直接导入。" type="warning" :closable="false" show-icon class="import-hint" />
      <el-tabs v-model="tab">
      <el-tab-pane label="标签与族" name="tags">
        <el-table v-loading="loading" :data="tags" size="small" empty-text="该库尚无语义草稿，请点击「生成并导入规则草稿」，或上传已有的 rule_init_result.jsonl">
          <el-table-column prop="tagName" label="标签" min-width="180" show-overflow-tooltip />
          <el-table-column prop="conceptId" label="概念编号" width="100" />
          <el-table-column prop="familyKey" label="所属族" min-width="260" show-overflow-tooltip />
          <el-table-column prop="semanticType" label="语义类型" width="150" />
          <el-table-column prop="completenessScore" label="完整度" width="80" />
          <el-table-column label="状态" width="95"><template slot-scope="s">{{ s.row.reviewStatus === 'REVIEWED' ? '已复核' : '草稿' }}</template></el-table-column>
          <el-table-column label="操作" width="130"><template slot-scope="s"><el-button type="text" @click="open(s.row)">维护 / 复核</el-button></template></el-table-column>
        </el-table>
        <pagination v-if="total > pageSize" :total="total" :page.sync="page" :limit.sync="pageSize" @pagination="load" />
      </el-tab-pane>
      <el-tab-pane label="业务概念" name="concepts" lazy><semantic-records resource="concept" title="业务概念" id-key="conceptId" :fields="conceptFields" :query="{ libraryId: loadedLibrary }" :defaults="{ libraryId: loadedLibrary, status: '0', tagObject: '客户' }" /></el-tab-pane>
      <el-tab-pane label="全部别名" name="all-aliases" lazy><semantic-records resource="alias" title="别名" id-key="aliasId" :fields="allAliasFields" :query="{}" :defaults="{ targetType: 'TAG', aliasType: 'SYNONYM', weight: 1 }" /></el-tab-pane>
      <el-tab-pane label="业务词典" name="terms" lazy><semantic-records resource="term" title="词条" id-key="termId" :fields="termFields" :query="{}" /></el-tab-pane>
    </el-tabs>
    </template>
    <el-drawer :title="selected.tagName || '标签语义'" :visible.sync="drawer" size="78%" :wrapper-closable="false">
      <div v-if="drawer" class="semantic-detail">
        <el-alert :title="'来源：' + (selected.source || '未注明') + '；依据哈希：' + (selected.basisHash || '缺失，需重新初始化')" type="info" :closable="false" />
        <el-tabs v-model="detailTab">
          <el-tab-pane label="语义口径" name="semantic">
            <el-form label-width="110px" size="small">
              <el-form-item label="概念编号"><el-input-number v-model="selected.conceptId" :min="1" :controls="false" /></el-form-item>
              <el-form-item label="所属族"><el-input v-model="selected.familyKey" /></el-form-item>
              <el-form-item label="语义类型"><el-select v-model="selected.semanticType"><el-option v-for="type in types" :key="type" :label="type" :value="type" /></el-select></el-form-item>
              <el-form-item label="业务定义"><el-input v-model="selected.definitionLong" type="textarea" :rows="3" /></el-form-item>
              <el-form-item label="敏感等级"><el-select v-model="selected.sensitivity"><el-option v-for="level in ['LOW', 'MEDIUM', 'HIGH', 'UNKNOWN']" :key="level" :label="level" :value="level" /></el-select></el-form-item>
              <el-form-item label="单位"><el-input v-model="selected.unit" /></el-form-item>
              <el-form-item label="结构化口径"><el-input v-model="selected.caliberStruct" type="textarea" :rows="5" /></el-form-item>
              <el-form-item label="允许操作符"><el-input v-model="selected.allowedOperators" /></el-form-item>
              <el-form-item>
                <el-button v-hasPermi="['taglibrary:semantic:edit']" type="primary" :loading="saving" @click="saveTag">保存草稿</el-button>
                <el-button v-if="selected.reviewStatus !== 'REVIEWED'" v-hasPermi="['taglibrary:semantic:review']" :loading="saving" @click="reviewTag">业务复核</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="码值区间与层级" name="codes" lazy><semantic-records resource="code-value" title="码值语义" id-key="tagId" :fields="codeFields" :detail-id="selected.tagId" :defaults="{ tagId: selected.tagId, isUnknownBucket: 0 }" /></el-tab-pane>
          <el-tab-pane label="别名" name="aliases" lazy><semantic-records resource="alias" title="别名" id-key="aliasId" :fields="aliasFields" :query="{ targetType: 'TAG', targetId: String(selected.tagId) }" :defaults="{ targetType: 'TAG', targetId: String(selected.tagId), aliasType: 'SYNONYM', weight: 1 }" /></el-tab-pane>
          <el-tab-pane label="易混淆" name="confusable" lazy><semantic-records resource="confusable" title="易混淆对" id-key="pairId" :fields="confusableFields" :detail-id="selected.tagId" :defaults="{ tagIdA: selected.tagId }" /></el-tab-pane>
          <el-tab-pane label="安全画像" name="profile">
            <p>仅支持已复核、LOW 敏感等级的业务标签。小样本和低频枚举桶会被抑制。</p>
            <el-button size="small" @click="getProfile">查看最新画像</el-button><el-button v-hasPermi="['taglibrary:semantic:bootstrap']" size="small" :loading="profileLoading" @click="runProfile">重新聚合</el-button>
            <el-descriptions v-if="profile" :column="2" border class="profile-summary"><el-descriptions-item label="样本量">{{ profile.sampleSize }}</el-descriptions-item><el-descriptions-item label="空值率">{{ profile.nullRate }}</el-descriptions-item><el-descriptions-item label="中位数">{{ profile.p50 }}</el-descriptions-item><el-descriptions-item label="来源版本">{{ profile.sourceVersionId }}</el-descriptions-item></el-descriptions>
          </el-tab-pane>
          <el-tab-pane label="正反例" name="examples" lazy><semantic-records resource="example" title="示例" id-key="exampleId" :fields="exampleFields" :detail-id="selected.tagId" :defaults="{ tagId: selected.tagId, exampleType: 'POS' }" /></el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </div>
</template>
<script>
import SemanticRecords from './Records'
import { listLibrary } from '@/api/taglibrary/library'
import { profileTag, aggregateProfile, semanticList, semanticDetail, saveSemantic, reviewSemantic, bootstrapExport, bootstrapImport, bootstrapExpand } from '@/api/taglibrary/semantic'
const f = (key, label, extra = {}) => ({ key, label, ...extra })
export default {
  name: 'TagSemantic', components: { SemanticRecords },
  data() { return {
    libraryId: Number(this.$route.query.libraryId) || undefined, libraries: [], loadedLibrary: null, tags: [], profile: null, profileLoading: false, loading: false, saving: false, exporting: false, importing: false, expanding: false, tab: 'tags', drawer: false, selected: {}, detailTab: 'semantic', page: 1, pageSize: 20, total: 0,
    types: ['BOOL', 'ENUM_NOMINAL', 'ENUM_ORDINAL', 'ENUM_HIERARCHY', 'NUM_AMOUNT', 'NUM_COUNT', 'NUM_RATIO', 'NUM_SCORE', 'TEXT_FREE', 'DATE', 'ID_KEY'],
    conceptFields: [f('conceptCode', '概念编码', { required: true, immutable: true }), f('conceptName', '概念名称', { required: true }), f('tagObject', '标签对象', { required: true }), f('domainDirId', '业务域编号', { number: true, required: true }), f('definition', '定义', { multiline: true }), f('parentId', '父概念编号', { number: true }), f('status', '状态', { options: ['0', '1'] })],
    termFields: [f('term', '词条', { required: true }), f('termType', '类别', { options: ['FUZZY_TIME', 'FUZZY_QUANTITY', 'FUZZY_CATEGORY', 'ORDINAL_WORD', 'NEGATION', 'BOUNDARY'], required: true }), f('options', '候选含义 JSON', { multiline: true }), f('defaultPolicy', '处理策略', { options: ['ASK', 'SUGGEST'] })],
    codeFields: [f('code', '原始码值', { required: true }), f('codeDefinition', '中文含义（来源码表）', { readonly: true }), f('dimensionId', '来源维表编号', { readonly: true }), f('rankNo', '顺序', { number: true }), f('lowerBound', '下界'), f('upperBound', '上界'), f('lowerInclusive', '包含下界', { number: true }), f('upperInclusive', '包含上界', { number: true }), f('boundUnit', '单位'), f('parentTagId', '父标签编号', { number: true }), f('parentCode', '父码值'), f('levelNo', '层级', { number: true }), f('isUnknownBucket', '未知桶 0/1', { number: true })],
    allAliasFields: [f('targetType', '目标类型', { options: ['TAG', 'CONCEPT', 'CODE_VALUE'], required: true }), f('targetId', '目标编号 / 标签#码值', { required: true }), f('aliasText', '别名', { required: true }), f('aliasType', '类型', { options: ['SYNONYM', 'COLLOQUIAL', 'ABBREVIATION', 'NEGATIVE'] })],
    aliasFields: [f('aliasText', '别名', { required: true }), f('aliasType', '类型', { options: ['SYNONYM', 'COLLOQUIAL', 'ABBREVIATION', 'NEGATIVE'], required: true })],
    confusableFields: [f('tagIdA', '标签 A', { number: true, required: true }), f('tagIdB', '标签 B', { number: true, required: true }), f('confusionType', '混淆类型', { required: true }), f('differenceNote', '业务差异', { multiline: true, required: true }), f('disambiguationHint', '澄清提示', { multiline: true })],
    exampleFields: [f('exampleType', '类型', { options: ['POS', 'NEG'] }), f('utterance', '业务表达', { multiline: true, required: true }), f('expectedCondition', '期望条件 JSON', { multiline: true })]
  } },
  mounted() {
    this.loadLibraries()
  },
  methods: {
    loadLibraries() {
      listLibrary({ pageNum: 1, pageSize: 100 }).then(response => {
        this.libraries = response.rows || []
        if (this.libraryId) this.load()
      })
    },
    handleLibraryChange() { this.loadedLibrary = null; this.tags = []; this.total = 0; this.page = 1; if (this.libraryId) this.load() },
    async load() {
      if (!this.libraryId) return
      if (this.libraryId !== this.loadedLibrary) this.page = 1
      this.loading = true
      try {
        const result = await semanticList('tag', { libraryId: this.libraryId, pageNum: this.page, pageSize: this.pageSize })
        this.tags = result.rows
        this.total = result.total
        this.loadedLibrary = this.libraryId
      } finally { this.loading = false }
    },
    draftSummary(result) {
      const rejected = (result && result.rejected) || []
      return {
        rejected,
        text: `概念 ${result.importedConceptCount || 0}、标签 ${result.importedTagCount || 0}、码值 ${result.importedCodeCount || 0}；跳过已复核 ${result.skippedReviewedCount || 0}；拒绝 ${rejected.length}`
      }
    },
    async expandDrafts() {
      if (!this.libraryId || this.expanding) return
      try {
        await this.$modal.confirm('将按当前标签库导出实时冻结，运行规则扩展并导入草稿。不会自动复核。全库可能需要一两分钟。')
      } catch (_) {
        return
      }
      const libraryId = this.libraryId
      this.expanding = true
      try {
        const response = await bootstrapExpand({ libraryId })
        const result = response.data || {}
        const summary = this.draftSummary(result)
        const unresolved = result.unresolved == null ? '' : `；规则未能自动判定的口径 ${result.unresolved} 条，未当作导入失败`
        const onlyReviewed = summary.rejected.length > 0 && summary.rejected.every(row => row && row.code === 'REVIEWED_SKIP')
        if (onlyReviewed) {
          this.$alert(`没有改写已复核内容。跳过 ${result.skippedReviewedCount || summary.rejected.length} 行，概念、标签、码值都保持原复核结果。规则草稿不能覆盖已复核口径。${unresolved}`, '导入结果', { type: 'info' })
        } else if (summary.rejected.length) {
          this.$alert(`导入完成：${summary.text}${unresolved}。部分行被拒绝，请核对冻结依据。`, '导入结果', { type: 'warning' })
        } else {
          this.$modal.msgSuccess(`导入完成：${summary.text}${unresolved}`)
        }
        if (this.libraryId === libraryId) await this.load()
      } finally {
        this.expanding = false
      }
    },
    pickImportFile() {
      if (!this.libraryId || this.importing) return
      const input = this.$refs.importFile
      if (input) {
        input.value = ''
        input.click()
      }
    },
    readTextFile(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result || ''))
        reader.onerror = () => reject(new Error('文件读取失败'))
        reader.readAsText(file, 'utf-8')
      })
    },
    detectImportJsonlFormat(jsonl) {
      const kinds = new Set()
      for (const line of jsonl.split(/\r?\n/)) {
        if (!line.trim()) continue
        try {
          const row = JSON.parse(line)
          if (row.kind) kinds.add(row.kind)
        } catch (_) {
          return 'invalid'
        }
        if (kinds.size >= 4) break
      }
      if (kinds.has('meta') || kinds.has('tag') || kinds.has('domain')) return 'freeze'
      if (kinds.has('tag_semantic') || kinds.has('concept') || kinds.has('code_value_semantic')) return 'draft'
      return kinds.size ? 'unknown' : 'empty'
    },
    async handleImportFile(event) {
      const file = event.target.files && event.target.files[0]
      if (!file || !this.libraryId) return
      const libraryId = this.libraryId
      this.importing = true
      try {
        const jsonl = await this.readTextFile(file)
        if (!jsonl.trim()) {
          this.$modal.msgError('导入文件为空')
          return
        }
        const format = this.detectImportJsonlFormat(jsonl)
        if (format === 'freeze') {
          this.$modal.msgError('这是「实时冻结」文件（semantic-freeze-*.jsonl），不能直接导入。请先对冻结文件运行 Python expand_full，再导入生成的 rule_init_result.jsonl。')
          return
        }
        if (format !== 'draft') {
          this.$modal.msgError('文件格式不符：需要 rule_init_result.jsonl，且每行 kind 为 concept / tag_semantic / code_value_semantic。')
          return
        }
        const response = await bootstrapImport({ libraryId, jsonl })
        const result = response.data || {}
        const summary = this.draftSummary(result)
        if (summary.rejected.length) {
          this.$alert(`导入完成：${summary.text}。部分行被拒绝，请检查 rule_init_result.jsonl 是否与当前冻结依据一致。`, '导入结果', { type: 'warning' })
        } else {
          this.$modal.msgSuccess(`导入完成：${summary.text}`)
        }
        if (this.libraryId === libraryId) await this.load()
      } catch (_) {
        /* 统一请求层已提示失败 */
      } finally {
        this.importing = false
        if (event.target) event.target.value = ''
      }
    },
    async exportCurrentFreeze() {
      if (!this.libraryId) return
      this.exporting = true
      try {
        const response = await bootstrapExport({ libraryId: this.libraryId })
        const result = response.data || {}
        if ((result.issues || []).length) {
          this.$modal.msgError(`实时冻结存在 ${result.issues.length} 个来源问题，已拒绝下载`)
          return
        }
        const blob = new Blob([result.jsonl || ''], { type: 'application/x-ndjson;charset=utf-8' })
        const link = document.createElement('a')
        const url = URL.createObjectURL(blob)
        link.href = url
        link.download = `semantic-freeze-L${this.libraryId}-${result.contentHash || 'unhashed'}.jsonl`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
        this.$modal.msgSuccess(`已导出 ${result.tagCount} 个字段、${result.codeValueCount} 个码值`)
      } finally { this.exporting = false }
    },
    open(row) { this.profile = null; this.selected = { ...row }; this.detailTab = 'semantic'; this.drawer = true },
    async getProfile() { this.profile = (await profileTag(this.selected.tagId)).data },
    async runProfile() { this.profileLoading = true; try { this.profile = (await aggregateProfile(this.selected.tagId)).data } finally { this.profileLoading = false } },
    async saveTag() {
      try { JSON.parse(this.selected.caliberStruct || '{}'); JSON.parse(this.selected.allowedOperators || '[]') } catch (_) { this.$modal.msgError('结构化口径与操作符须为合法 JSON'); return }
      this.saving = true
      try { await saveSemantic('tag', this.selected); this.selected = (await semanticDetail('tag', this.selected.tagId)).data; this.$modal.msgSuccess('草稿已保存'); await this.load() } finally { this.saving = false }
    },
    async reviewTag() {
      try { const { value } = await this.$prompt('请输入已核实的业务依据', '复核标签', { inputValidator: v => !!(v && v.trim()) || '请填写依据' }); this.saving = true; await reviewSemantic('tag', this.selected.tagId, value); this.selected = (await semanticDetail('tag', this.selected.tagId)).data; await this.load(); this.$modal.msgSuccess('复核完成') } catch (_) { /* 统一请求层显示失败；取消保留草稿 */ } finally { this.saving = false }
    }
  }
}
</script>
<style scoped>
.import-hint { margin-bottom: 12px; }
.profile-summary { margin-top: 20px; }
.semantic-detail { padding: 0 24px 24px; height: calc(100vh - 90px); overflow: auto; }
.semantic-detail .el-tabs { margin-top: 18px; }
</style>
