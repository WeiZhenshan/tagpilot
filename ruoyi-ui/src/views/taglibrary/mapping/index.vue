<template>
  <div class="app-container">
    <!-- 顶部信息区：数据集 / 同步版本 / 选择原因 / 最近同步 / 对账统计 -->
    <el-card shadow="never" class="header-card">
      <div class="header-info">
        <span class="header-item header-lib">标签库：{{ libraryName || '-' }}</span>
        <span class="header-item">数据集：{{ libraryInfo.datasetName || '-' }}</span>
        <span class="header-item">同步版本：{{ versionLabel }}</span>
        <span class="header-item">选择原因：{{ syncResult ? syncResult.reason : '-' }}</span>
        <span class="header-item">最近同步：{{ syncTimeLabel }}</span>
        <span v-if="syncResult" class="header-item header-stats">
          新增 {{ syncResult.addedCount }} / 失效 {{ syncResult.missingCount }} / 恢复 {{ syncResult.restoredCount }} / 来源变更 {{ syncResult.changedCount }}
        </span>
      </div>
      <el-alert v-if="syncFailed" type="error" :closable="false" show-icon
        title="本次同步失败（具体原因见提示），以下展示已有映射数据；处理后可点击「重新同步」" />
    </el-card>

    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <div class="toolbar-left">
        <el-button type="primary" size="small" icon="el-icon-document" :loading="saving" @click="handleSaveDraft" v-hasPermi="['taglibrary:tag:mapping:save']">保存草稿</el-button>
        <el-button type="success" size="small" icon="el-icon-upload2" :loading="submitting" @click="handleSubmit" v-hasPermi="['taglibrary:tag:mapping:submit']">提交审核</el-button>
        <el-button size="small" icon="el-icon-refresh" :loading="syncing" @click="handleResync" v-hasPermi="['taglibrary:tag:mapping:sync']">重新同步</el-button>
        <el-dropdown size="small" trigger="click" @command="openBatchDialog" v-hasPermi="['taglibrary:tag:mapping:save']">
          <el-button size="small" icon="el-icon-edit-outline">批量填写<i class="el-icon-arrow-down el-icon--right" /></el-button>
          <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="tagType">标签类型</el-dropdown-item>
            <el-dropdown-item command="dirId">标签目录</el-dropdown-item>
            <el-dropdown-item command="techCaliber">技术口径</el-dropdown-item>
            <el-dropdown-item command="businessCaliber">业务口径</el-dropdown-item>
          </el-dropdown-menu>
        </el-dropdown>
        <el-checkbox v-model="includeMissing" class="missing-toggle" @change="handleToggleMissing">包含失效字段</el-checkbox>
      </div>
      <div class="toolbar-right">
        <el-input v-model="queryParams.keyword" placeholder="标签名称/字段名" clearable size="small" style="width: 170px; margin-right: 8px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
        <el-select v-model="queryParams.status" placeholder="发布状态" clearable size="small" style="width: 120px; margin-right: 8px;" @change="handleQuery">
          <el-option v-for="(label, value) in publishStatusMap" :key="value" :label="label" :value="value" />
        </el-select>
        <el-select v-model="queryParams.dirId" placeholder="标签目录" clearable size="small" style="width: 140px;" @change="handleQuery">
          <el-option v-for="d in dirOptions" :key="d.dirId" :label="d.dirName" :value="d.dirId" />
        </el-select>
      </div>
    </el-row>

    <el-table :data="tagList" v-loading="loading" size="small" :row-class-name="rowClassName">
      <el-table-column label="选择" width="55" align="center">
        <template #default="scope">
          <el-tooltip v-if="!canCheckRow(scope.row)" :content="checkDisabledReason(scope.row)" placement="top">
            <el-checkbox :value="false" disabled />
          </el-tooltip>
          <el-checkbox v-else :value="isChecked(scope.row)" @change="val => toggleRow(scope.row, val)" />
        </template>
      </el-table-column>
      <el-table-column prop="fieldName" label="字段名" min-width="105" show-overflow-tooltip />
      <!-- 标签名称：点击进入输入态 -->
      <el-table-column label="标签名称" min-width="150">
        <template #default="scope">
          <el-input v-if="isEditing(scope.row, 'tagName')" v-model="editCache" ref="cellInput" size="mini" maxlength="128"
            @blur="commitEdit(scope.row)" @keyup.enter.native="$event.target.blur()" />
          <div v-else class="cell-click" @click="startEdit(scope.row, 'tagName')">
            <span>{{ scope.row.edited.tagName }}</span>
            <span v-if="isFieldDirty(scope.row, 'tagName')" class="dirty-dot" title="本次未保存修改" />
          </div>
        </template>
      </el-table-column>
      <!-- 标签类型：点击进入下拉态 -->
      <el-table-column label="标签类型" width="125" align="center">
        <template #default="scope">
          <el-select v-if="isEditing(scope.row, 'tagType')" v-model="editCache" ref="cellSelect" size="mini"
            @change="val => commitEdit(scope.row, val)" @visible-change="v => { if (!v) closeEdit() }">
            <el-option v-for="d in dict.type.tag_type" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <div v-else class="cell-click" @click="startEdit(scope.row, 'tagType')">
            <dict-tag :options="dict.type.tag_type" :value="scope.row.edited.tagType" />
            <span v-if="isFieldDirty(scope.row, 'tagType')" class="dirty-dot" title="本次未保存修改" />
          </div>
        </template>
      </el-table-column>
      <!-- 标签目录：点击打开目录选择弹窗 -->
      <el-table-column label="标签目录" width="115" align="center">
        <template #default="scope">
          <div class="cell-click" @click="openDirDialog(scope.row)">
            <span>{{ dirLabel(scope.row) }}</span>
            <span v-if="isFieldDirty(scope.row, 'dirId')" class="dirty-dot" title="本次未保存修改" />
          </div>
        </template>
      </el-table-column>
      <!-- 发布状态 -->
      <el-table-column label="发布状态" width="90" align="center">
        <template #default="scope">
          <el-tag size="mini" :type="publishTagType(scope.row.status)">{{ publishStatusMap[scope.row.status] || scope.row.status }}</el-tag>
        </template>
      </el-table-column>
      <!-- 元数据审核状态（含变更类型） -->
      <el-table-column label="审核状态" width="130" align="center">
        <template #default="scope">
          <template v-if="scope.row.changeStatus">
            <el-tag v-if="scope.row.changeStatus === 'PENDING'" type="warning" size="mini">待审核</el-tag>
            <el-tag v-else-if="scope.row.ownDraft" type="primary" size="mini">草稿</el-tag>
            <el-tag v-else type="info" size="mini">他人草稿</el-tag>
            <div v-if="scope.row.changeType" class="change-type">{{ changeTypeMap[scope.row.changeType] || scope.row.changeType }}</div>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <!-- 来源状态 -->
      <el-table-column label="来源状态" width="120" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.sourceStatus" size="mini" :type="sourceTagType(scope.row.sourceStatus)">
            {{ sourceStatusMap[scope.row.sourceStatus] || scope.row.sourceStatus }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="dataType" label="数据类型" width="95" align="center" show-overflow-tooltip />
      <!-- 技术口径 -->
      <el-table-column label="技术口径" width="95" align="center">
        <template #default="scope">
          <el-button type="text" size="mini" @click="openCaliberDialog(scope.row, 'techCaliber')">{{ isRowDisabled(scope.row) ? '查看' : '填写' }}</el-button>
          <span v-if="isFieldDirty(scope.row, 'techCaliber')" class="dirty-dot" title="本次未保存修改" />
        </template>
      </el-table-column>
      <!-- 业务口径 -->
      <el-table-column label="业务口径" width="95" align="center">
        <template #default="scope">
          <el-button type="text" size="mini" @click="openCaliberDialog(scope.row, 'businessCaliber')">{{ isRowDisabled(scope.row) ? '查看' : '填写' }}</el-button>
          <span v-if="isFieldDirty(scope.row, 'businessCaliber')" class="dirty-dot" title="本次未保存修改" />
        </template>
      </el-table-column>
      <!-- 操作：撤回本人待审申请 -->
      <el-table-column label="操作" width="70" align="center">
        <template #default="scope">
          <el-button v-if="scope.row.changeStatus === 'PENDING' && scope.row.ownDraft" type="text" size="mini"
            @click="handleWithdraw(scope.row)" v-hasPermi="['taglibrary:tag:mapping:withdraw']">撤回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" :page="queryParams.pageNum" :limit="queryParams.pageSize" @pagination="handlePagination" />

    <!-- 目录选择弹窗 -->
    <el-dialog title="选择标签目录" :visible.sync="dirDialogVisible" width="450px" append-to-body>
      <el-radio-group v-model="dirDialogValue" class="dir-radio-group">
        <el-radio v-for="d in dirOptions" :key="d.dirId" :label="d.dirId">{{ d.dirName }}</el-radio>
      </el-radio-group>
      <el-empty v-if="dirOptions.length === 0" description="暂无目录" :image-size="60" />
      <div slot="footer">
        <el-button size="small" @click="dirDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="confirmDirDialog">确定</el-button>
      </div>
    </el-dialog>

    <!-- 口径填写/查看弹窗 -->
    <el-dialog :title="caliberDialogTitle" :visible.sync="caliberVisible" width="600px" append-to-body>
      <el-input v-model="caliberValue" type="textarea" :rows="6" maxlength="500" show-word-limit
        :readonly="caliberReadonly" :placeholder="caliberReadonly ? '' : '请输入内容'" />
      <div slot="footer">
        <template v-if="caliberReadonly">
          <el-button size="small" @click="caliberVisible = false">关闭</el-button>
        </template>
        <template v-else>
          <el-button size="small" @click="caliberVisible = false">取消</el-button>
          <el-button size="small" type="primary" @click="confirmCaliberDialog">确定</el-button>
        </template>
      </div>
    </el-dialog>

    <!-- 批量填写弹窗（只应用到勾选的可编辑行） -->
    <el-dialog :title="batchDialogTitle" :visible.sync="batchVisible" width="500px" append-to-body>
      <el-alert type="info" :closable="false" show-icon class="batch-tip"
        :title="'将应用到勾选的 ' + checkedEditableRows().length + ' 行（仅修改本地编辑值，保存草稿后生效）'" />
      <el-select v-if="batchField === 'tagType'" v-model="batchValue" placeholder="请选择标签类型" style="width: 100%;">
        <el-option v-for="d in dict.type.tag_type" :key="d.value" :label="d.label" :value="d.value" />
      </el-select>
      <el-radio-group v-else-if="batchField === 'dirId'" v-model="batchValue" class="dir-radio-group">
        <el-radio v-for="d in dirOptions" :key="d.dirId" :label="d.dirId">{{ d.dirName }}</el-radio>
      </el-radio-group>
      <el-input v-else v-model="batchValue" type="textarea" :rows="5" maxlength="500" show-word-limit placeholder="请输入内容" />
      <div slot="footer">
        <el-button size="small" @click="batchVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="confirmBatchDialog">确定</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { mappingList, saveMappingDraft, submitMapping, withdrawMapping, syncMappingFields } from '@/api/taglibrary/mapping'
import { listDir } from '@/api/taglibrary/dir'
import { getLibrary } from '@/api/taglibrary/library'
import { checkPermi } from '@/utils/permission'

const META_FIELDS = ['tagName', 'tagType', 'dirId', 'techCaliber', 'businessCaliber']

export default {
  name: 'TagMapping',
  dicts: ['tag_type'],
  data() {
    return {
      loading: true,
      saving: false,
      submitting: false,
      syncing: false,
      total: 0,
      // 标签库信息（路由 query 传入）
      libraryId: undefined,
      libraryName: '',
      // 标签库详情（数据集名称/最近同步版本/时间）
      libraryInfo: {},
      // 本次会话最近一次同步结果（TagSyncResultVO），同步失败时 syncFailed=true
      syncResult: null,
      syncFailed: false,
      // 标签分页列表（每行带 edited/draftValues/original）
      tagList: [],
      // 跨页行缓存：tagId → 行（保留勾选与未保存修改）
      rowCache: {},
      // 跨页勾选：tagId → true
      checkedMap: {},
      // 是否包含失效字段（来源缺失）
      includeMissing: false,
      dirOptions: [],
      editingCell: '',
      editCache: undefined,
      dirDialogVisible: false,
      dirDialogRow: null,
      dirDialogValue: undefined,
      caliberVisible: false,
      caliberDialogTitle: '',
      caliberReadonly: false,
      caliberRow: null,
      caliberField: '',
      caliberValue: '',
      // 批量填写弹窗
      batchVisible: false,
      batchField: '',
      batchValue: undefined,
      // 发布状态文案
      publishStatusMap: { '4': '待完善', '0': '草稿', '1': '待审批', '2': '已上线', '3': '已下线' },
      // 变更类型文案
      changeTypeMap: { FIRST: '首次建档', METADATA: '元数据修改', SOURCE: '来源确认' },
      // 来源状态文案
      sourceStatusMap: { AVAILABLE: '可用', MISSING: '来源缺失', CHANGED: '来源变更待确认' },
      queryParams: {
        pageNum: 1,
        pageSize: 10,
        libraryId: undefined,
        keyword: '',
        status: undefined,
        dirId: undefined,
        includeMissing: false
      }
    }
  },
  computed: {
    /** 是否有重新同步权限（无权限用户进入页面只加载列表，不触发写入） */
    canSync() {
      return checkPermi(['taglibrary:tag:mapping:sync'])
    },
    /** 顶部版本展示：本次会话同步结果优先，否则库最近同步版本ID */
    versionLabel() {
      if (this.syncResult && this.syncResult.versionId) {
        const no = this.syncResult.versionNo != null ? 'V' + this.syncResult.versionNo : ''
        const name = this.syncResult.versionName ? '（' + this.syncResult.versionName + '）' : ''
        return (no || '版本ID ' + this.syncResult.versionId) + name
      }
      return this.libraryInfo.lastSyncVersionId ? '版本ID ' + this.libraryInfo.lastSyncVersionId : '-'
    },
    syncTimeLabel() {
      if (this.syncResult && this.syncResult.syncTime) {
        return this.syncResult.syncTime
      }
      return this.libraryInfo.lastSyncTime || '-'
    },
    batchDialogTitle() {
      const labels = { tagType: '批量设置标签类型', dirId: '批量设置标签目录', techCaliber: '批量设置技术口径', businessCaliber: '批量设置业务口径' }
      return labels[this.batchField] || '批量填写'
    }
  },
  created() {
    this.libraryId = this.$route.query.libraryId
    this.libraryName = this.$route.query.libraryName || ''
    this.queryParams.libraryId = this.libraryId
    this.loadDirOptions()
  },
  activated() {
    // keep-alive 复用组件时 created 不再执行；库参数变化时整体重新初始化，修复缓存复用不更新问题
    const routeLibraryId = this.$route.query.libraryId
    if (routeLibraryId && String(routeLibraryId) !== String(this.libraryId)) {
      this.reinit(routeLibraryId)
      return
    }
    this.enterAndSync()
  },
  methods: {
    /** 切换标签库重新初始化：清空跨页缓存与勾选 */
    reinit(libraryId) {
      this.libraryId = libraryId
      this.libraryName = this.$route.query.libraryName || ''
      this.queryParams.libraryId = libraryId
      this.queryParams.pageNum = 1
      this.queryParams.keyword = ''
      this.queryParams.status = undefined
      this.queryParams.dirId = undefined
      this.includeMissing = false
      this.queryParams.includeMissing = false
      this.rowCache = {}
      this.checkedMap = {}
      this.syncResult = null
      this.syncFailed = false
      this.libraryInfo = {}
      this.closeEdit()
      this.loadDirOptions()
      this.enterAndSync()
    },
    /** 进入页面：有同步权限则先同步再加载；纯查询权限用户只加载列表 */
    enterAndSync() {
      if (!this.libraryId) {
        this.getList()
        return
      }
      this.loadLibraryInfo()
      if (this.canSync) {
        this.doSync()
      } else {
        this.getList()
      }
    },
    /** 手动重新同步（带未保存修改保护） */
    handleResync() {
      this.guardUnsaved(() => this.doSync())
    },
    /** 调同步接口：成功展示版本信息与对账统计；失败标记 syncFailed 并仍加载列表，绝不显示同步成功 */
    doSync() {
      this.syncing = true
      return syncMappingFields(this.libraryId).then(response => {
        this.syncResult = response.data || null
        this.syncFailed = false
        this.syncing = false
        this.$modal.msgSuccess(response.msg || '同步完成')
        this.loadLibraryInfo()
        this.getList()
      }).catch(() => {
        // 后端业务失败原因已由请求拦截器弹出
        this.syncResult = null
        this.syncFailed = true
        this.syncing = false
        this.getList()
      })
    },
    /** 加载标签库详情（数据集名称/最近同步版本/时间） */
    loadLibraryInfo() {
      getLibrary(this.libraryId).then(response => {
        this.libraryInfo = response.data || {}
      }).catch(() => {})
    },
    /** 查询批量映射标签分页列表 */
    getList() {
      this.loading = true
      this.queryParams.includeMissing = this.includeMissing
      mappingList(this.queryParams).then(response => {
        this.tagList = (response.rows || []).map(row => this.wrapRow(row))
        this.total = response.total
        this.closeEdit()
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    /**
     * 包装行数据：original 为 tl_tag 原始值，draftValues 为已保存草稿覆盖后的基准值，edited 为当前编辑值；
     * 跨页缓存命中且有本次未保存修改时，保留本地编辑值（其余服务端字段取最新）
     */
    wrapRow(row) {
      const original = {
        tagName: row.tagName,
        tagType: row.tagType,
        dirId: row.dirId,
        techCaliber: row.techCaliber,
        businessCaliber: row.businessCaliber
      }
      const draftValues = Object.assign({}, original)
      // 本人已保存草稿：用 afterJson 覆盖基准值
      if (row.ownDraft && row.afterJson) {
        try {
          Object.assign(draftValues, JSON.parse(row.afterJson))
        } catch (e) {
          // afterJson 解析失败时按原始值展示
        }
      }
      const cached = this.rowCache[row.tagId]
      let edited = Object.assign({}, draftValues, { dirName: undefined })
      let localDirty = false
      if (cached && cached._localDirty) {
        edited = Object.assign({}, cached.edited)
        localDirty = true
      }
      row.original = original
      row.draftValues = draftValues
      row.edited = edited
      row._localDirty = localDirty
      this.$set(this.rowCache, row.tagId, row)
      return row
    },
    /** 加载目录选项 */
    loadDirOptions() {
      if (!this.libraryId) return
      listDir(this.libraryId).then(response => {
        this.dirOptions = response.data || response.rows || []
      })
    },
    /** 搜索（带未保存修改保护） */
    handleQuery() {
      this.guardUnsaved(() => {
        this.queryParams.pageNum = 1
        this.getList()
      })
    },
    /** 切换"包含失效字段"（带未保存修改保护） */
    handleToggleMissing(val) {
      this.guardUnsaved(() => {
        this.queryParams.pageNum = 1
        this.getList()
      }, () => {
        // 取消：还原开关
        this.includeMissing = !val
      })
    },
    /** 翻页/改页大小（带未保存修改保护，勾选与编辑跨页保留在缓存中） */
    handlePagination(data) {
      this.guardUnsaved(() => {
        this.queryParams.pageNum = data.page
        this.queryParams.pageSize = data.limit
        this.getList()
      })
    },
    /**
     * 未保存修改保护：保存后继续 / 放弃修改 / 取消
     * confirm=保存后继续（先存草稿再执行动作），cancel=放弃修改继续，close=取消不动
     */
    guardUnsaved(action, onCancel) {
      if (!this.hasUnsaved()) {
        action()
        return
      }
      this.$confirm('当前有未保存的修改，如何处理？', '提示', {
        type: 'warning',
        distinguishCancelAndClose: true,
        confirmButtonText: '保存后继续',
        cancelButtonText: '放弃修改'
      }).then(() => {
        return this.doSaveDraft(false).then(action)
      }).catch(reason => {
        if (reason === 'cancel') {
          this.discardLocalEdits()
          action()
        } else if (onCancel) {
          onCancel()
        }
      })
    },
    /** 是否存在本次未保存修改（跨页，遍历行缓存） */
    hasUnsaved() {
      return Object.keys(this.rowCache).some(id => this.rowCache[id]._localDirty)
    },
    /** 放弃全部本地未保存修改（恢复为已保存草稿/原始值） */
    discardLocalEdits() {
      Object.keys(this.rowCache).forEach(id => {
        const row = this.rowCache[id]
        if (row._localDirty) {
          row.edited = Object.assign({}, row.draftValues)
          row._localDirty = false
        }
      })
    },
    /** 字段值归一化后比较 */
    normalize(val) {
      return val == null ? '' : String(val)
    },
    /** 某字段是否有本次未保存修改（相对已保存草稿基准值） */
    isFieldDirty(row, field) {
      return this.normalize(row.edited[field]) !== this.normalize(row.draftValues[field])
    },
    /** 行是否有本次未保存修改 */
    isRowDirty(row) {
      return META_FIELDS.some(f => this.isFieldDirty(row, f))
    },
    /** 编辑后重算行的本地脏标记 */
    markRowDirty(row) {
      row._localDirty = this.isRowDirty(row)
    },
    /** 是否他人草稿 */
    isOthersDraft(row) {
      return row.changeId != null && !row.ownDraft
    },
    /** 整行只读：待审核中 或 他人草稿 */
    isRowReadonly(row) {
      return row.changeStatus === 'PENDING' || this.isOthersDraft(row)
    },
    /** 失效字段（来源缺失）：置灰、不可编辑、不可勾选 */
    isMissingRow(row) {
      return row.sourceStatus === 'MISSING'
    },
    /** 行不可编辑：只读 或 失效 */
    isRowDisabled(row) {
      return this.isRowReadonly(row) || this.isMissingRow(row)
    },
    /** 行置灰样式 */
    rowClassName({ row }) {
      return this.isMissingRow(row) ? 'missing-row' : ''
    },
    /** 是否允许勾选（可编辑行：无他人草稿、非待审核、非失效） */
    canCheckRow(row) {
      return !this.isRowDisabled(row)
    },
    /** 勾选禁用原因 */
    checkDisabledReason(row) {
      if (row.changeStatus === 'PENDING') return '已提交，待审核'
      if (this.isOthersDraft(row)) return '他人草稿，不可编辑'
      if (this.isMissingRow(row)) return '来源缺失，当前版本不可用'
      return ''
    },
    /** 发布状态标签样式 */
    publishTagType(status) {
      return { '2': 'success', '1': 'warning', '3': 'danger' }[status] || 'info'
    },
    /** 来源状态标签样式 */
    sourceTagType(sourceStatus) {
      return { AVAILABLE: 'success', CHANGED: 'warning' }[sourceStatus] || 'info'
    },
    /** 目录显示名 */
    dirLabel(row) {
      const dir = this.dirOptions.find(d => d.dirId === row.edited.dirId)
      if (dir) return dir.dirName
      return row.edited.dirName || '-'
    },
    /** 是否勾选（跨页） */
    isChecked(row) {
      return !!this.checkedMap[row.tagId]
    },
    /** 勾选/取消勾选（跨页保留） */
    toggleRow(row, checked) {
      if (checked) {
        this.$set(this.checkedMap, row.tagId, true)
      } else {
        this.$delete(this.checkedMap, row.tagId)
      }
    },
    /** 勾选的可编辑行（跨页，从行缓存取） */
    checkedEditableRows() {
      return Object.keys(this.checkedMap)
        .map(id => this.rowCache[id])
        .filter(row => row && this.canCheckRow(row))
    },
    /** 进入单元格编辑态 */
    isEditing(row, field) {
      return this.editingCell === row.tagId + '_' + field
    },
    /** 点击进入编辑态 */
    startEdit(row, field) {
      if (this.isRowDisabled(row)) return
      this.editingCell = row.tagId + '_' + field
      this.editCache = row.edited[field]
      this.$nextTick(() => {
        if (this.$refs.cellInput && this.$refs.cellInput.focus) this.$refs.cellInput.focus()
        if (this.$refs.cellSelect && this.$refs.cellSelect.toggleMenu) this.$refs.cellSelect.toggleMenu()
      })
    },
    /** 提交单元格编辑 */
    commitEdit(row, val) {
      let value = val !== undefined ? val : this.editCache
      if (this.editingCell.endsWith('_tagName')) {
        value = (value == null ? '' : String(value)).trim()
        if (!value) {
          this.$modal.msgWarning('标签名称不能为空')
          value = row.edited.tagName
        }
      }
      row.edited[this.editingCell.substring(String(row.tagId).length + 1)] = value
      this.markRowDirty(row)
      this.closeEdit()
    },
    /** 关闭编辑态 */
    closeEdit() {
      this.editingCell = ''
      this.editCache = undefined
    },
    /** 打开目录选择弹窗 */
    openDirDialog(row) {
      if (this.isRowDisabled(row)) return
      this.dirDialogRow = row
      this.dirDialogValue = row.edited.dirId
      this.dirDialogVisible = true
    },
    /** 确认目录选择 */
    confirmDirDialog() {
      const dir = this.dirOptions.find(d => d.dirId === this.dirDialogValue)
      this.dirDialogRow.edited.dirId = this.dirDialogValue
      this.dirDialogRow.edited.dirName = dir ? dir.dirName : undefined
      this.markRowDirty(this.dirDialogRow)
      this.dirDialogVisible = false
    },
    /** 打开口径弹窗（填写/查看） */
    openCaliberDialog(row, field) {
      this.caliberRow = row
      this.caliberField = field
      this.caliberValue = row.edited[field] || ''
      this.caliberReadonly = this.isRowDisabled(row)
      this.caliberDialogTitle = (field === 'techCaliber' ? '技术口径' : '业务口径') + '（' + row.fieldName + '）'
      this.caliberVisible = true
    },
    /** 确认口径填写 */
    confirmCaliberDialog() {
      this.caliberRow.edited[this.caliberField] = this.caliberValue
      this.markRowDirty(this.caliberRow)
      this.caliberVisible = false
    },
    /** 打开批量填写弹窗 */
    openBatchDialog(field) {
      const rows = this.checkedEditableRows()
      if (rows.length === 0) {
        this.$modal.msgWarning('请先勾选要批量填写的行')
        return
      }
      this.batchField = field
      this.batchValue = undefined
      this.batchVisible = true
    },
    /** 确认批量填写：只修改勾选行的明确选中属性（本地编辑值） */
    confirmBatchDialog() {
      if (this.batchValue == null || this.batchValue === '') {
        this.$modal.msgWarning('请先设置要批量填写的内容')
        return
      }
      const rows = this.checkedEditableRows()
      const dir = this.batchField === 'dirId' ? this.dirOptions.find(d => d.dirId === this.batchValue) : null
      rows.forEach(row => {
        row.edited[this.batchField] = this.batchValue
        if (this.batchField === 'dirId') {
          row.edited.dirName = dir ? dir.dirName : undefined
        }
        this.markRowDirty(row)
      })
      this.$modal.msgSuccess('已批量填写 ' + rows.length + ' 行，保存草稿后生效')
      this.batchVisible = false
    },
    /** 保存草稿（按钮入口，空修改时提示） */
    handleSaveDraft() {
      this.doSaveDraft(true).then(() => this.getList()).catch(() => {})
    },
    /**
     * 保存草稿实现：跨页收集所有本地脏行，携带 baseVersion/revision；
     * 成功后用响应回填 changeId/revision 并更新已保存基准值
     */
    doSaveDraft(warnWhenEmpty) {
      const dirtyRows = Object.keys(this.rowCache)
        .map(id => this.rowCache[id])
        .filter(row => row._localDirty && !this.isRowDisabled(row))
      if (dirtyRows.length === 0) {
        if (warnWhenEmpty) this.$modal.msgWarning('没有需要保存的修改')
        return Promise.resolve()
      }
      const items = dirtyRows.map(row => ({
        tagId: row.tagId,
        tagName: row.edited.tagName,
        tagType: row.edited.tagType,
        dirId: row.edited.dirId,
        techCaliber: row.edited.techCaliber,
        businessCaliber: row.edited.businessCaliber,
        baseVersion: row.version,
        revision: row.ownDraft && row.changeStatus === 'DRAFT' ? row.revision : null
      }))
      this.saving = true
      return saveMappingDraft(items).then(response => {
        this.$modal.msgSuccess(response.msg || '草稿保存成功')
        this.saving = false
        const savedItems = response.data || []
        // 回填保存后的申请标识与修订号，并把本地编辑值转为已保存草稿基准
        savedItems.forEach(item => {
          const row = this.rowCache[item.tagId]
          if (row) {
            row.changeId = item.changeId
            row.revision = item.revision
            row.changeStatus = 'DRAFT'
            row.ownDraft = true
            row.draftValues = Object.assign({}, row.edited)
            delete row.draftValues.dirName
            row._localDirty = false
          }
        })
        // 与当前值一致被后端跳过（草稿被删除）的行：移出缓存，下次刷新按服务端状态重建
        const savedTagIds = savedItems.map(item => item.tagId)
        dirtyRows.forEach(row => {
          if (savedTagIds.indexOf(row.tagId) === -1) {
            this.$delete(this.rowCache, row.tagId)
          }
        })
        return savedItems
      }).catch(() => {
        this.saving = false
        return Promise.reject()
      })
    },
    /** 提交所选：先把所选行最新编辑内容保存为草稿（拿到新 changeId/revision），再提交，防止提交旧草稿 */
    handleSubmit() {
      let rows = this.checkedEditableRows()
      if (rows.length === 0) {
        this.$modal.msgWarning('请先勾选要提交的行')
        return
      }
      const noChangeRows = rows.filter(row => !row.changeId && !row._localDirty)
      if (noChangeRows.length > 0) {
        this.$modal.msgWarning('所选行中有 ' + noChangeRows.length + ' 行没有修改内容，请先编辑或取消勾选')
        return
      }
      this.$confirm('确认提交所选 ' + rows.length + ' 条进入审核？（将先保存最新编辑内容）', '提示', { type: 'warning' }).then(() => {
        this.submitting = true
        // 先保存所选行的最新编辑内容，再按保存后返回的 changeId 提交
        return this.doSaveDraft(false)
      }).then(() => {
        const changeIds = rows
          .map(row => this.rowCache[row.tagId])
          .filter(row => row && row.changeId != null && row.changeStatus === 'DRAFT' && row.ownDraft)
          .map(row => row.changeId)
        if (changeIds.length === 0) {
          this.$modal.msgWarning('所选行没有可提交的草稿')
          this.getList()
          return Promise.reject()
        }
        return submitMapping(changeIds)
      }).then(() => {
        this.$modal.msgSuccess('已提交审核')
        this.submitting = false
        // 提交的行脱离本地缓存，重新拉取服务端状态
        rows.forEach(row => {
          this.$delete(this.rowCache, row.tagId)
          this.$delete(this.checkedMap, row.tagId)
        })
        this.getList()
      }).catch(() => {
        this.submitting = false
      })
    },
    /** 撤回本人待审核申请 */
    handleWithdraw(row) {
      this.$confirm('确认撤回标签「' + row.edited.tagName + '」的待审核申请？撤回后回到草稿状态', '提示', { type: 'warning' }).then(() => {
        return withdrawMapping([row.changeId])
      }).then(() => {
        this.$modal.msgSuccess('已撤回')
        this.$delete(this.rowCache, row.tagId)
        this.getList()
      }).catch(() => {})
    }
  }
}
</script>

<style scoped>
.header-card {
  margin-bottom: 12px;
}

.header-card >>> .el-card__body {
  padding: 10px 14px;
}

.header-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  font-size: 13px;
  color: #606266;
}

.header-item {
  margin-right: 20px;
  line-height: 24px;
}

.header-lib {
  font-weight: 600;
  color: #303133;
}

.header-stats {
  color: #409eff;
}

.toolbar {
  margin-bottom: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-left .el-dropdown {
  margin-left: 10px;
}

.missing-toggle {
  margin-left: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.cell-click {
  cursor: pointer;
  min-height: 23px;
}

.change-type {
  font-size: 12px;
  color: #909399;
  line-height: 16px;
}

.dirty-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #f56c6c;
  margin-left: 6px;
  vertical-align: middle;
}

.dir-radio-group {
  display: flex;
  flex-direction: column;
}

.dir-radio-group >>> .el-radio {
  margin-bottom: 10px;
  margin-right: 0;
}

.batch-tip {
  margin-bottom: 12px;
}

.missing-row {
  color: #c0c4cc;
  background-color: #fafafa;
}
</style>
