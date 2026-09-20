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
      <el-form-item>
        <el-button type="primary" plain icon="el-icon-chat-dot-round" :disabled="!libraryId" @click="goAgentWorkbench" v-hasPermi="['taglibrary:semantic:list']">打开智能体</el-button>
      </el-form-item>
    </el-form>
    <el-alert title="发布会校验复核状态、来源依据与完整度。新构建就绪后，需激活才会承接检索。自然语言查询请到智能体工作台。" type="info" :closable="false" />
    <el-table v-loading="loading" :data="snapshots" size="small" highlight-current-row @current-change="select" empty-text="尚无快照，请先完成业务语义复核">
      <el-table-column prop="snapshotId" label="快照" min-width="220" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column label="实际覆盖" width="110"><template slot-scope="s">{{ report(s.row.qualityReport).coverage || '-' }}</template></el-table-column>
      <el-table-column prop="tagCount" label="标签" width="80" /><el-table-column prop="conceptCount" label="概念" width="80" /><el-table-column prop="codeValueCount" label="码值" width="80" />
      <el-table-column prop="publishTime" label="发布时间" width="170" />
      <el-table-column label="操作" width="190"><template slot-scope="s"><el-button type="text" @click.stop="show('质量门禁报告', report(s.row.qualityReport))">质量报告</el-button><el-button type="text" @click.stop="download(s.row)">下载</el-button></template></el-table-column>
    </el-table>
    <pagination v-show="total > 0" :total="total" :page.sync="page" :limit.sync="pageSize" @pagination="load" />
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
import { snapshotQuality, listSnapshots, listBuilds, publishSnapshot, downloadSnapshot, startBuild, buildStats, activateBuild } from '@/api/taglibrary/semantic'
import { agentWorkbenchLocation } from '@/utils/agentWorkbench'
export default {
  name: 'TagSemanticIndex',
  data() { return { libraryId: Number(this.$route.query.libraryId) || undefined, libraries: [], snapshots: [], selected: null, builds: [], page: 1, pageSize: 20, total: 0, storeType: 'MILVUS', loading: false, publishing: false, building: false, buildLoading: false, activating: false, detailTitle: '', detail: '', detailVisible: false } },
  mounted() { this.loadLibraries() },
  methods: {
    loadLibraries() {
      listLibrary({ pageNum: 1, pageSize: 100 }).then(response => {
        this.libraries = response.rows || []
        if (this.libraryId) this.load()
      })
    },
    handleLibraryChange() {
      this.snapshots = []; this.selected = null; this.builds = []; this.total = 0; this.page = 1
      if (this.libraryId) this.load()
    },
    goAgentWorkbench() {
      const library = this.libraries.find(item => item.libraryId === this.libraryId) || {}
      this.$router.push(agentWorkbenchLocation({
        libraryId: this.libraryId,
        libraryName: library.libraryName,
        from: '/taglibrary/semantic-index'
      }))
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
</style>
