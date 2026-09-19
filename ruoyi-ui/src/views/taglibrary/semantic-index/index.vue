<template>
  <div class="app-container">
    <el-form :inline="true" size="small" @submit.native.prevent="load">
      <el-form-item label="标签库">
        <el-select v-model="libraryId" placeholder="请选择标签库" filterable clearable style="width: 240px" @change="handleLibraryChange">
          <el-option v-for="lib in libraries" :key="lib.libraryId" :label="lib.libraryName" :value="lib.libraryId" />
        </el-select>
      </el-form-item>
      <el-form-item><el-button type="primary" :loading="loading" @click="load">查询快照</el-button></el-form-item>
      <el-form-item><el-button v-hasPermi="['taglibrary:semantic:publish']" :disabled="!libraryId" @click="quality">发布前检查</el-button></el-form-item>
      <el-form-item><el-button v-hasPermi="['taglibrary:semantic:publish']" :disabled="!libraryId" :loading="publishing" @click="publish">发布快照</el-button></el-form-item>
    </el-form>
    <el-alert title="发布会校验复核状态、来源依据与完整度。新构建就绪后，需激活才会承接检索。" type="info" :closable="false" />
    <el-table v-loading="loading" :data="snapshots" size="small" highlight-current-row @current-change="select" empty-text="尚无快照，请先完成业务语义复核">
      <el-table-column prop="snapshotId" label="快照" min-width="220" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column label="实际覆盖" width="110"><template slot-scope="s">{{ report(s.row.qualityReport).coverage || '-' }}</template></el-table-column>
      <el-table-column prop="tagCount" label="标签" width="80" /><el-table-column prop="conceptCount" label="概念" width="80" /><el-table-column prop="codeValueCount" label="码值" width="80" />
      <el-table-column prop="publishTime" label="发布时间" width="170" />
      <el-table-column label="操作" width="190"><template slot-scope="s"><el-button type="text" @click.stop="show('质量门禁报告', report(s.row.qualityReport))">质量报告</el-button><el-button type="text" @click.stop="download(s.row)">下载</el-button></template></el-table-column>
    </el-table>
    <pagination v-show="total > 0" :total="total" :page.sync="page" :limit.sync="pageSize" @pagination="load" />
    <section class="query-section" aria-labelledby="semantic-query-title">
      <h3 id="semantic-query-title">自然语言查询</h3>
      <p>使用当前已激活的索引查找标签。遇到口径不明确或无法精确表达的条件，会提示补充信息。</p>
      <el-form @submit.native.prevent="retrieve">
        <el-form-item label="查询条件">
          <el-input v-model="requirement" type="textarea" :rows="3" :maxlength="500" show-word-limit aria-label="查询条件" placeholder="例如：近30天有异名跨行转入的客户" />
        </el-form-item>
        <el-button type="primary" :loading="retrieving" :disabled="!libraryId || !requirement.trim()" @click="retrieve">查询标签</el-button>
      </el-form>
      <el-alert v-if="queryError" :title="queryError" type="error" :closable="false" class="query-result" />
      <div v-if="queryResult" class="query-result" aria-live="polite">
        <el-alert :title="decisionText" :type="queryResult.decision === 'CANDIDATES_ONLY' ? 'info' : 'warning'" :closable="false" />
        <p>快照：{{ queryResult.snapshot_id }} · 构建：{{ queryResult.build_id }}</p>
        <el-table :data="queryResult.candidates || []" size="small" empty-text="当前可用范围内没有候选标签">
          <el-table-column prop="name" label="候选标签" min-width="180" />
          <el-table-column prop="family_key" label="所属标签族" min-width="240" show-overflow-tooltip />
          <el-table-column prop="code" label="原始码值" width="110" />
          <el-table-column label="反馈" width="110"><template slot-scope="s"><el-button type="text" :disabled="feedbackSaved || feedbackSaving" @click="feedback(s.row)">符合需求</el-button></template></el-table-column>
        </el-table>
        <p v-if="feedbackSaved">反馈已记录。</p>
      </div>
    </section>
    <section v-if="selected" class="build-section">
      <div class="build-toolbar"><h3>{{ selected.snapshotId }} 的索引构建</h3><div>
        <el-select v-model="storeType" size="small" aria-label="存储模式" class="store-select"><el-option label="LOCAL 基线" value="LOCAL" /><el-option label="Milvus" value="MILVUS" /></el-select>
        <el-button v-hasPermi="['taglibrary:semantic:bootstrap']" type="primary" size="small" :loading="building" @click="build">新建索引</el-button>
        <el-button size="small" @click="loadBuilds">刷新</el-button></div></div>
      <el-table v-loading="buildLoading" :data="builds" size="small" empty-text="该快照尚无索引构建">
        <el-table-column prop="buildId" label="构建" min-width="240" show-overflow-tooltip /><el-table-column prop="storeType" label="存储" width="95" /><el-table-column prop="embeddingModel" label="模型" min-width="140" show-overflow-tooltip /><el-table-column prop="status" label="状态" width="100" /><el-table-column prop="docCount" label="文档数" width="85" />
        <el-table-column label="操作" width="210"><template slot-scope="s">
          <el-button v-hasPermi="['taglibrary:semantic:bootstrap']" type="text" @click="stats(s.row)">实时状态</el-button>
          <el-button type="text" @click="show('评测摘要', report(s.row.evalSummary))">评测</el-button>
          <el-button v-if="['READY', 'RETIRED'].includes(s.row.status)" v-hasPermi="['taglibrary:semantic:publish']" type="text" :disabled="activating" @click="activate(s.row)">{{ s.row.status === 'RETIRED' ? '回滚至此' : '激活' }}</el-button>
        </template></el-table-column>
      </el-table>
    </section>
    <el-dialog :title="detailTitle" :visible.sync="detailVisible" width="75%"><pre class="report">{{ detail }}</pre></el-dialog>
  </div>
</template>
<script>
import { listLibrary } from '@/api/taglibrary/library'
import { snapshotQuality, listSnapshots, listBuilds, publishSnapshot, downloadSnapshot, startBuild, buildStats, activateBuild, retrieveSemantic, submitFeedback } from '@/api/taglibrary/semantic'
export default {
  name: 'TagSemanticIndex',
  data() { return { libraryId: Number(this.$route.query.libraryId) || undefined, libraries: [], snapshots: [], selected: null, builds: [], page: 1, pageSize: 20, total: 0, storeType: 'MILVUS', loading: false, publishing: false, building: false, buildLoading: false, activating: false, detailTitle: '', detail: '', detailVisible: false, requirement: '', retrieving: false, queryResult: null, queryError: '', feedbackSaved: false, feedbackSaving: false } },
  computed: {
    decisionText() { return { CANDIDATES_ONLY: '已找到候选标签，请核对业务口径；查询不会自动执行客群筛选。', CLARIFY: '查询条件需要补充时间范围或明确业务口径，请修改后重试。', INEXPRESSIBLE: '现有码值分档无法精确表达该条件，请调整条件或选择连续数值标签。' }[this.queryResult && this.queryResult.decision] || '请核对候选标签的业务口径。' }
  },
  mounted() { this.loadLibraries() },
  methods: {
    loadLibraries() {
      listLibrary({ pageNum: 1, pageSize: 100 }).then(response => {
        this.libraries = response.rows || []
        if (this.libraryId) this.load()
      })
    },
    handleLibraryChange() {
      this.queryResult = null; this.queryError = ''; this.feedbackSaved = false
      this.snapshots = []; this.selected = null; this.builds = []; this.total = 0; this.page = 1
      if (this.libraryId) this.load()
    },
    async retrieve() {
      if (!this.libraryId || !this.requirement.trim() || this.retrieving) return
      const libraryId = this.libraryId
      this.retrieving = true; this.queryResult = null; this.queryError = ''; this.feedbackSaved = false
      try { const r = await retrieveSemantic({ libraryId, requirement: this.requirement.trim() }); if (this.libraryId === libraryId) this.queryResult = r.data }
      catch (error) { if (this.libraryId === libraryId) this.queryError = error.message || '查询失败，请确认已发布快照、激活索引且检索服务可用。' }
      finally { this.retrieving = false }
    },
    async feedback(row) {
      const result = this.queryResult
      if (!result || this.feedbackSaved || this.feedbackSaving) return
      this.feedbackSaving = true
      try { await submitFeedback({ traceId: result.trace_id, buildId: result.build_id, snapshotId: result.snapshot_id, recommendedTagId: row.tag_id, finalTagId: row.tag_id, action: 'ACCEPT' }); if (this.queryResult === result) this.feedbackSaved = true }
      finally { this.feedbackSaving = false }
    },
    report(value) { try { return JSON.parse(value || '{}') } catch (_) { return { message: value } } },
    show(title, data) { this.detailTitle = title; this.detail = JSON.stringify(data, null, 2); this.detailVisible = true },
    async load() { if (!this.libraryId) return; this.loading = true; try { const r = await listSnapshots({ libraryId: this.libraryId, pageNum: this.page, pageSize: this.pageSize }); this.snapshots = r.rows; this.total = r.total; this.selected = null; this.builds = [] } finally { this.loading = false } },
    async select(row) { this.selected = row; if (row) await this.loadBuilds() },
    async loadBuilds() { if (!this.selected) return; const id = this.selected.snapshotId; this.buildLoading = true; try { const r = await listBuilds(id); if (this.selected && this.selected.snapshotId === id) this.builds = r.data } finally { this.buildLoading = false } },
    async quality() { this.show('发布门禁检查', (await snapshotQuality(this.libraryId)).data) },
    async publish() { this.publishing = true; try { await publishSnapshot(this.libraryId); this.$modal.msgSuccess('快照已发布'); await this.load() } finally { this.publishing = false } },
    async download(row) { const data = await downloadSnapshot(row.snapshotId); const url = URL.createObjectURL(new Blob([data], { type: 'application/x-ndjson' })); const a = document.createElement('a'); a.href = url; a.download = row.snapshotId + '.jsonl'; a.click(); URL.revokeObjectURL(url) },
    async build() { this.building = true; try { await startBuild(this.selected.snapshotId, this.storeType); this.$modal.msgSuccess('构建完成，等待激活'); await this.loadBuilds() } finally { this.building = false } },
    async stats(row) { this.show('索引状态与行集对账', (await buildStats(row.buildId)).data) },
    async activate(row) { this.activating = true; try { await activateBuild(row.buildId); this.$modal.msgSuccess('激活成功'); await this.loadBuilds() } finally { this.activating = false } }
  }
}
</script>
<style scoped>
.build-section { margin-top: 36px; clear: both; }
.build-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.build-toolbar h3 { font-size: 16px; overflow-wrap: anywhere; }
.store-select { width: 140px; margin-right: 10px; }
.report { max-height: 65vh; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.query-section { clear: both; padding-top: 28px; }
.query-section h3 { font-size: 16px; }
.query-result { margin-top: 16px; overflow-wrap: anywhere; }
</style>
