<template>
  <div class="app-container">
    <el-tabs v-model="activeTab" @tab-click="handleTabClick">
      <!-- Tab1 标签库待审批 -->
      <el-tab-pane label="标签库待审批" name="library">
        <el-table :data="libraryList" v-loading="libraryLoading" size="small">
          <el-table-column prop="libraryName" label="名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="libraryCode" label="编码" min-width="110" show-overflow-tooltip />
          <el-table-column label="分类" width="110" align="center">
            <template #default="scope">
              <dict-tag :options="dict.type.tag_library_category" :value="scope.row.category" />
            </template>
          </el-table-column>
          <el-table-column label="标签对象" width="100" align="center">
            <template #default="scope">
              <dict-tag :options="dict.type.tag_object" :value="scope.row.tagObject" />
            </template>
          </el-table-column>
          <el-table-column prop="ownerName" label="负责人" width="90" align="center" />
          <el-table-column prop="datasetName" label="关联数据集" min-width="130" show-overflow-tooltip />
          <el-table-column prop="updateTime" label="提交时间" width="160" align="center" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="scope">
              <el-button type="text" size="mini" icon="el-icon-check" @click="openAuditDialog(scope.row)" v-hasPermi="['taglibrary:library:audit']">通过</el-button>
              <el-button type="text" size="mini" icon="el-icon-close" @click="openAuditDialog(scope.row, false)" v-hasPermi="['taglibrary:library:audit']">驳回</el-button>
            </template>
          </el-table-column>
        </el-table>
        <pagination v-show="libraryTotal > 0" :total="libraryTotal" :page.sync="libraryQuery.pageNum" :limit.sync="libraryQuery.pageSize" @pagination="getLibraryList" />
      </el-tab-pane>

      <!-- Tab2 标签待审批 -->
      <el-tab-pane label="标签待审批" name="tag">
        <el-form :inline="true" :model="tagQuery" size="small">
          <el-form-item label="库名称">
            <el-input v-model="tagQuery.libraryName" placeholder="请输入库名称" clearable style="width: 160px;" @keyup.enter.native="handleTagQuery" />
          </el-form-item>
          <el-form-item label="标签名">
            <el-input v-model="tagQuery.tagName" placeholder="请输入标签名" clearable style="width: 160px;" @keyup.enter.native="handleTagQuery" />
          </el-form-item>
          <el-form-item label="标签类型">
            <el-select v-model="tagQuery.tagType" placeholder="请选择" clearable style="width: 120px;" @change="handleTagQuery">
              <el-option v-for="d in dict.type.tag_type" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="el-icon-search" @click="handleTagQuery">搜索</el-button>
            <el-button icon="el-icon-refresh" @click="resetTagQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <el-row class="toolbar" type="flex" justify="space-between" align="middle">
          <el-button-group>
            <el-button size="small" type="success" icon="el-icon-check" :disabled="tagSelection.length === 0" @click="openBatchAudit(true)" v-hasPermi="['taglibrary:tag:audit']">批量通过</el-button>
            <el-button size="small" type="danger" icon="el-icon-close" :disabled="tagSelection.length === 0" @click="openBatchAudit(false)" v-hasPermi="['taglibrary:tag:audit']">批量驳回</el-button>
          </el-button-group>
          <span class="selection-tip">已选 {{ tagSelection.length }} 项</span>
        </el-row>
        <el-table :data="tagList" v-loading="tagLoading" size="small" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="45" align="center" />
          <el-table-column prop="libraryName" label="所属库" min-width="130" show-overflow-tooltip />
          <el-table-column prop="tagName" label="标签名" min-width="130" show-overflow-tooltip />
          <el-table-column prop="fieldName" label="源字段名" min-width="110" show-overflow-tooltip />
          <el-table-column label="类型" width="90" align="center">
            <template #default="scope">
              <dict-tag :options="dict.type.tag_type" :value="scope.row.tagType" />
            </template>
          </el-table-column>
          <el-table-column prop="createWay" label="创建方式" width="80" align="center" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="scope">
              <el-tag :type="statusType(scope.row.status)" size="mini">{{ statusLabel(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updateTime" label="提交时间" width="160" align="center" />
        </el-table>
        <pagination v-show="tagTotal > 0" :total="tagTotal" :page.sync="tagQuery.pageNum" :limit.sync="tagQuery.pageSize" @pagination="getTagList" />
      </el-tab-pane>

      <!-- Tab3 元数据变更审批 -->
      <el-tab-pane label="元数据变更审批" name="meta">
        <el-row class="toolbar" type="flex" justify="space-between" align="middle">
          <el-button-group>
            <el-button size="small" type="success" icon="el-icon-check" :disabled="metaSelection.length === 0" @click="openMetaBatchAudit(true)" v-hasPermi="['taglibrary:tag:mapping:audit']">批量通过</el-button>
            <el-button size="small" type="danger" icon="el-icon-close" :disabled="metaSelection.length === 0" @click="openMetaBatchAudit(false)" v-hasPermi="['taglibrary:tag:mapping:audit']">批量驳回</el-button>
          </el-button-group>
          <span class="selection-tip">已选 {{ metaSelection.length }} 项</span>
        </el-row>
        <el-table :data="metaList" v-loading="metaLoading" size="small" @selection-change="handleMetaSelectionChange">
          <el-table-column type="selection" width="45" align="center" />
          <el-table-column prop="libraryName" label="标签库" min-width="130" show-overflow-tooltip />
          <el-table-column prop="fieldName" label="字段名" min-width="110" show-overflow-tooltip />
          <el-table-column prop="tagName" label="标签名" min-width="130" show-overflow-tooltip />
          <el-table-column prop="applyBy" label="申请人" width="90" align="center" />
          <el-table-column prop="submitTime" label="提交时间" width="160" align="center" />
          <el-table-column prop="changedFields" label="变更字段" min-width="140" show-overflow-tooltip />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="scope">
              <el-button type="text" size="mini" icon="el-icon-view" @click="openMetaDetail(scope.row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <pagination v-show="metaTotal > 0" :total="metaTotal" :page.sync="metaQuery.pageNum" :limit.sync="metaQuery.pageSize" @pagination="getMetaList" />
      </el-tab-pane>

      <!-- Tab4 审批记录 -->
      <el-tab-pane label="审批记录" name="log">
        <el-form :inline="true" :model="logQuery" size="small">
          <el-form-item label="业务类型">
            <el-select v-model="logQuery.bizType" placeholder="全部" clearable style="width: 130px;" @change="handleLogQuery">
              <el-option label="标签库" value="library" />
              <el-option label="标签" value="tag" />
              <el-option label="元数据变更" value="tagMeta" />
            </el-select>
          </el-form-item>
          <el-form-item label="业务名称">
            <el-input v-model="logQuery.bizName" placeholder="请输入名称" clearable style="width: 160px;" @keyup.enter.native="handleLogQuery" />
          </el-form-item>
          <el-form-item label="申请人">
            <el-input v-model="logQuery.applyBy" placeholder="请输入申请人" clearable style="width: 140px;" @keyup.enter.native="handleLogQuery" />
          </el-form-item>
          <el-form-item label="时间">
            <el-date-picker v-model="logTimeRange" type="datetimerange" range-separator="~" start-placeholder="开始时间" end-placeholder="结束时间"
              value-format="yyyy-MM-dd HH:mm:ss" style="width: 340px;" @change="handleLogQuery" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="el-icon-search" @click="handleLogQuery">搜索</el-button>
            <el-button icon="el-icon-refresh" @click="resetLogQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <el-table :data="logList" v-loading="logLoading" size="small">
          <el-table-column label="业务类型" width="100" align="center">
            <template #default="scope">
              <el-tag :type="bizTypeTagType(scope.row.bizType)" size="mini">{{ bizTypeLabel(scope.row.bizType) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="bizName" label="业务名称" min-width="140" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.bizName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="action" label="动作" width="70" align="center" />
          <el-table-column label="变更前" width="80" align="center">
            <template #default="scope">{{ statusLabel(scope.row.fromStatus) }}</template>
          </el-table-column>
          <el-table-column label="变更后" width="80" align="center">
            <template #default="scope">{{ statusLabel(scope.row.toStatus) }}</template>
          </el-table-column>
          <el-table-column prop="applyBy" label="申请人" width="90" align="center" />
          <el-table-column prop="auditBy" label="审批人" width="90" align="center">
            <template #default="scope">{{ scope.row.auditBy || '-' }}</template>
          </el-table-column>
          <el-table-column prop="auditTime" label="审批时间" width="150" align="center">
            <template #default="scope">{{ scope.row.auditTime || '-' }}</template>
          </el-table-column>
          <el-table-column prop="auditComment" label="意见" min-width="120" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.auditComment || '-' }}</template>
          </el-table-column>
        </el-table>
        <pagination v-show="logTotal > 0" :total="logTotal" :page.sync="logQuery.pageNum" :limit.sync="logQuery.pageSize" @pagination="getLogList" />
      </el-tab-pane>
    </el-tabs>

    <!-- 审批弹窗 -->
    <el-dialog :title="auditTitle" :visible.sync="auditVisible" width="500px" append-to-body>
      <el-form label-width="80px" size="small">
        <el-form-item label="审批对象">
          <span>{{ auditTarget }}</span>
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="auditComment" type="textarea" :rows="3" placeholder="请输入审批意见（可选）" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="auditVisible = false">取消</el-button>
        <el-button v-if="auditPass" size="small" type="success" icon="el-icon-check" @click="handleAudit(true)">通过</el-button>
        <el-button v-if="!auditPass" size="small" type="danger" icon="el-icon-close" @click="handleAudit(false)">驳回</el-button>
      </div>
    </el-dialog>

    <!-- 元数据变更详情弹窗（当前值 → 申请值 对比） -->
    <el-dialog title="元数据变更详情" :visible.sync="metaDetailVisible" width="680px" append-to-body>
      <div v-loading="metaDetailLoading">
        <el-table :data="metaFieldRows" size="small" border>
          <el-table-column prop="label" label="字段" width="120" />
          <el-table-column label="当前值" min-width="200" show-overflow-tooltip>
            <template #default="scope">
              <span :class="{ 'meta-unchanged': !scope.row.changed }">{{ fmtVal(scope.row.current) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="申请值" min-width="200" show-overflow-tooltip>
            <template #default="scope">
              <span :class="{ 'meta-unchanged': !scope.row.changed }">{{ fmtVal(scope.row.after) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div slot="footer">
        <el-button size="small" @click="metaDetailVisible = false">关闭</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { listLibrary, auditLibrary, listAuditLogs } from '@/api/taglibrary/library'
import { listAuditTags, auditTag } from '@/api/taglibrary/tag'
import { metaAuditList, metaAuditDetail, auditMetaChange } from '@/api/taglibrary/metaAudit'

export default {
  name: 'TagAudit',
  dicts: ['tag_object', 'tag_library_category', 'tag_type'],
  data() {
    return {
      activeTab: 'library',
      tabLoaded: { library: false, tag: false, meta: false, log: false },
      // 状态映射（0草稿 1待审批 2已上线 3已下线）
      statusMap: {
        '0': { label: '草稿', type: 'info' },
        '1': { label: '待审批', type: 'warning' },
        '2': { label: '已上线', type: 'success' },
        '3': { label: '已下线', type: 'danger' }
      },
      // Tab1 标签库待审批
      libraryList: [],
      libraryTotal: 0,
      libraryLoading: false,
      libraryQuery: { pageNum: 1, pageSize: 10, status: '1' },
      // Tab2 标签待审批
      tagList: [],
      tagTotal: 0,
      tagLoading: false,
      tagSelection: [],
      tagQuery: { pageNum: 1, pageSize: 10, status: '1', libraryName: '', tagName: '', tagType: '' },
      // Tab3 元数据变更审批
      metaList: [],
      metaTotal: 0,
      metaLoading: false,
      metaSelection: [],
      metaQuery: { pageNum: 1, pageSize: 10 },
      // 元数据变更详情弹窗
      metaDetailVisible: false,
      metaDetailLoading: false,
      metaDetail: {},
      // 元数据对比字段（key → 中文名）
      metaFields: [
        { key: 'tagName', label: '标签名称' },
        { key: 'tagType', label: '标签类型' },
        { key: 'dirId', label: '标签目录(ID)' },
        { key: 'techCaliber', label: '技术口径' },
        { key: 'businessCaliber', label: '业务口径' }
      ],
      // Tab4 审批记录
      logList: [],
      logTotal: 0,
      logLoading: false,
      logTimeRange: [],
      logQuery: { pageNum: 1, pageSize: 10, bizType: '', bizName: '', applyBy: '', beginTime: '', endTime: '' },
      // 审批弹窗
      auditVisible: false,
      auditTitle: '',
      auditTarget: '',
      auditComment: '',
      auditIds: [],
      auditBizType: '',
      auditPass: true
    }
  },
  computed: {
    /** 元数据变更详情：五字段 当前值/申请值 对比行，无变化字段置灰 */
    metaFieldRows() {
      const d = this.metaDetail || {}
      const before = d.before || {}
      const after = d.after || {}
      const current = d.current || {}
      return this.metaFields.map(f => {
        const b = before[f.key]
        const a = after[f.key]
        return {
          key: f.key,
          label: f.label,
          current: current[f.key],
          after: a,
          changed: String(b === undefined || b === null ? '' : b) !== String(a === undefined || a === null ? '' : a)
        }
      })
    }
  },
  created() {
    this.getLibraryList()
    this.tabLoaded.library = true
  },
  methods: {
    /** Tab 切换：首次进入才加载 */
    handleTabClick(tab) {
      if (this.tabLoaded[tab.name]) return
      this.tabLoaded[tab.name] = true
      if (tab.name === 'tag') this.getTagList()
      else if (tab.name === 'meta') this.getMetaList()
      else if (tab.name === 'log') this.getLogList()
    },
    /** 状态文案/样式 */
    statusLabel(status) {
      const m = this.statusMap[status]
      return m ? m.label : (status || '-')
    },
    statusType(status) {
      const m = this.statusMap[status]
      return m ? m.type : 'info'
    },
    /** 审批记录业务类型文案/样式 */
    bizTypeLabel(bizType) {
      const map = { library: '标签库', tag: '标签', tagMeta: '元数据变更' }
      return map[bizType] || bizType || '-'
    },
    bizTypeTagType(bizType) {
      const map = { library: 'primary', tag: 'warning', tagMeta: 'success' }
      return map[bizType] || 'info'
    },
    /** 空值占位 */
    fmtVal(v) {
      return v === undefined || v === null || v === '' ? '-' : v
    },
    /** Tab1：待审批标签库列表 */
    getLibraryList() {
      this.libraryLoading = true
      listLibrary(this.libraryQuery).then(response => {
        this.libraryList = response.rows
        this.libraryTotal = response.total
        this.libraryLoading = false
      }).catch(() => { this.libraryLoading = false })
    },
    /** Tab2：待审批标签列表 */
    getTagList() {
      this.tagLoading = true
      listAuditTags(this.tagQuery).then(response => {
        this.tagList = response.rows
        this.tagTotal = response.total
        this.tagLoading = false
      }).catch(() => { this.tagLoading = false })
    },
    handleTagQuery() {
      this.tagQuery.pageNum = 1
      this.getTagList()
    },
    resetTagQuery() {
      this.tagQuery = { pageNum: 1, pageSize: 10, status: '1', libraryName: '', tagName: '', tagType: '' }
      this.handleTagQuery()
    },
    handleSelectionChange(selection) {
      this.tagSelection = selection
    },
    /** Tab3：元数据变更待审批列表 */
    getMetaList() {
      this.metaLoading = true
      metaAuditList(this.metaQuery).then(response => {
        this.metaList = response.rows
        this.metaTotal = response.total
        this.metaLoading = false
      }).catch(() => { this.metaLoading = false })
    },
    handleMetaSelectionChange(selection) {
      this.metaSelection = selection
    },
    /** Tab3：批量审批弹窗（复用共用审批弹窗） */
    openMetaBatchAudit(pass) {
      this.auditBizType = 'meta'
      this.auditIds = this.metaSelection.map(t => t.changeId)
      this.auditTarget = this.auditIds.length + ' 条元数据变更'
      this.auditTitle = pass ? '批量通过元数据变更' : '批量驳回元数据变更'
      this.auditPass = pass
      this.auditComment = ''
      this.auditVisible = true
    },
    /** Tab3：元数据变更详情（当前值 → 申请值 对比） */
    openMetaDetail(row) {
      this.metaDetail = {}
      this.metaDetailVisible = true
      this.metaDetailLoading = true
      metaAuditDetail(row.changeId).then(response => {
        this.metaDetail = response.data || {}
        this.metaDetailLoading = false
      }).catch(() => { this.metaDetailLoading = false })
    },
    /** Tab4：审批记录列表 */
    getLogList() {
      this.logLoading = true
      listAuditLogs(this.logQuery).then(response => {
        this.logList = response.rows
        this.logTotal = response.total
        this.logLoading = false
      }).catch(() => { this.logLoading = false })
    },
    handleLogQuery() {
      this.logQuery.pageNum = 1
      this.logQuery.beginTime = this.logTimeRange && this.logTimeRange.length > 0 ? this.logTimeRange[0] : ''
      this.logQuery.endTime = this.logTimeRange && this.logTimeRange.length > 0 ? this.logTimeRange[1] : ''
      this.getLogList()
    },
    resetLogQuery() {
      this.logTimeRange = []
      this.logQuery = { pageNum: 1, pageSize: 10, bizType: '', bizName: '', applyBy: '', beginTime: '', endTime: '' }
      this.handleLogQuery()
    },
    /** 打开审批弹窗（Tab1 库级：单条；Tab2 标签级：批量） */
    openAuditDialog(row, pass) {
      this.auditBizType = 'library'
      this.auditIds = [row.libraryId]
      this.auditTarget = row.libraryName
      this.auditTitle = pass === false ? '驳回标签库' : '通过标签库'
      this.auditPass = pass !== false
      this.auditComment = ''
      this.auditVisible = true
    },
    openBatchAudit(pass) {
      this.auditBizType = 'tag'
      this.auditIds = this.tagSelection.map(t => t.tagId)
      this.auditTarget = this.auditIds.length + ' 个标签'
      this.auditTitle = pass ? '批量通过标签' : '批量驳回标签'
      this.auditPass = pass
      this.auditComment = ''
      this.auditVisible = true
    },
    /** 审批提交（通过/驳回） */
    handleAudit(pass) {
      const text = pass ? '确认审批通过？' : '确认审批驳回？'
      this.$confirm(text, '提示', { type: 'warning' }).then(() => {
        if (this.auditBizType === 'library') {
          return auditLibrary({ ids: this.auditIds, pass: pass, auditComment: this.auditComment })
        }
        if (this.auditBizType === 'meta') {
          return auditMetaChange({ changeIds: this.auditIds, pass: pass, auditComment: this.auditComment })
        }
        return auditTag({ ids: this.auditIds, pass: pass, auditComment: this.auditComment })
      }).then(() => {
        this.$modal.msgSuccess(pass ? '已通过' : '已驳回')
        this.auditVisible = false
        this.refreshAfterAudit()
      }).catch(() => {})
    },
    /** 审批成功后刷新相关 Tab */
    refreshAfterAudit() {
      if (this.auditBizType === 'library') {
        this.getLibraryList()
      } else if (this.auditBizType === 'meta') {
        this.getMetaList()
      } else {
        this.getTagList()
      }
      if (this.tabLoaded.log) this.getLogList()
    }
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}

.selection-tip {
  font-size: 12px;
  color: #909399;
}

.meta-unchanged {
  color: #c0c4cc;
}
</style>
