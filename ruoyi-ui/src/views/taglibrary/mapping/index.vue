<template>
  <div class="app-container">
    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <div class="toolbar-left">
        <el-button type="primary" size="small" icon="el-icon-document" :loading="saving" @click="handleSaveDraft" v-hasPermi="['taglibrary:tag:mapping:save']">保存草稿</el-button>
        <el-button type="success" size="small" icon="el-icon-upload2" :loading="submitting" @click="handleSubmit" v-hasPermi="['taglibrary:tag:mapping:submit']">提交审核</el-button>
        <span class="library-title">标签库：{{ libraryName || '-' }}</span>
      </div>
      <div class="toolbar-right">
        <el-input v-model="queryParams.tagName" placeholder="标签名称" clearable size="small" style="width: 150px; margin-right: 8px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
        <el-input v-model="queryParams.fieldName" placeholder="字段名" clearable size="small" style="width: 150px; margin-right: 8px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
        <el-select v-model="queryParams.dirId" placeholder="标签目录" clearable size="small" style="width: 140px;" @change="handleQuery">
          <el-option v-for="d in dirOptions" :key="d.dirId" :label="d.dirName" :value="d.dirId" />
        </el-select>
      </div>
    </el-row>

    <el-table :data="tagList" v-loading="loading" size="small">
      <el-table-column label="选择" width="60" align="center">
        <template #default="scope">
          <el-tooltip v-if="!canSubmitRow(scope.row)" :content="submitDisabledReason(scope.row)" placement="top">
            <el-checkbox :value="false" disabled />
          </el-tooltip>
          <el-checkbox v-else :value="isChecked(scope.row)" @change="val => toggleRow(scope.row, val)" />
        </template>
      </el-table-column>
      <el-table-column prop="fieldName" label="字段名" min-width="110" show-overflow-tooltip />
      <!-- 标签名称：点击进入输入态 -->
      <el-table-column label="标签名称" min-width="170">
        <template #default="scope">
          <el-input v-if="isEditing(scope.row, 'tagName')" v-model="editCache" ref="cellInput" size="mini" maxlength="128"
            @blur="commitEdit(scope.row)" @keyup.enter.native="$event.target.blur()" />
          <div v-else class="cell-click" @click="startEdit(scope.row, 'tagName')">
            <span>{{ scope.row.edited.tagName }}</span>
            <el-tag v-if="scope.row.changeStatus === 'PENDING'" type="warning" size="mini" class="cell-tag">待审核</el-tag>
            <el-tag v-else-if="isOthersDraft(scope.row)" type="info" size="mini" class="cell-tag">他人草稿</el-tag>
            <span v-if="isFieldDirty(scope.row, 'tagName')" class="dirty-dot" title="已修改" />
          </div>
        </template>
      </el-table-column>
      <!-- 标签类型：点击进入下拉态 -->
      <el-table-column label="标签类型" width="140" align="center">
        <template #default="scope">
          <el-select v-if="isEditing(scope.row, 'tagType')" v-model="editCache" ref="cellSelect" size="mini"
            @change="val => commitEdit(scope.row, val)" @visible-change="v => { if (!v) closeEdit() }">
            <el-option v-for="d in dict.type.tag_type" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <div v-else class="cell-click" @click="startEdit(scope.row, 'tagType')">
            <dict-tag :options="dict.type.tag_type" :value="scope.row.edited.tagType" />
            <span v-if="isFieldDirty(scope.row, 'tagType')" class="dirty-dot" title="已修改" />
          </div>
        </template>
      </el-table-column>
      <!-- 标签目录：点击打开目录选择弹窗 -->
      <el-table-column label="标签目录" width="140" align="center">
        <template #default="scope">
          <div class="cell-click" @click="openDirDialog(scope.row)">
            <span>{{ dirLabel(scope.row) }}</span>
            <span v-if="isFieldDirty(scope.row, 'dirId')" class="dirty-dot" title="已修改" />
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="dataType" label="数据类型" width="100" align="center" show-overflow-tooltip />
      <!-- 技术口径 -->
      <el-table-column label="技术口径" width="100" align="center">
        <template #default="scope">
          <el-button type="text" size="mini" @click="openCaliberDialog(scope.row, 'techCaliber')">{{ isRowReadonly(scope.row) ? '查看' : '填写' }}</el-button>
          <span v-if="isFieldDirty(scope.row, 'techCaliber')" class="dirty-dot" title="已修改" />
        </template>
      </el-table-column>
      <!-- 业务口径 -->
      <el-table-column label="业务口径" width="100" align="center">
        <template #default="scope">
          <el-button type="text" size="mini" @click="openCaliberDialog(scope.row, 'businessCaliber')">{{ isRowReadonly(scope.row) ? '查看' : '填写' }}</el-button>
          <span v-if="isFieldDirty(scope.row, 'businessCaliber')" class="dirty-dot" title="已修改" />
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
  </div>
</template>

<script>
import { mappingList, saveMappingDraft, submitMapping, syncMappingFields } from '@/api/taglibrary/mapping'
import { listDir } from '@/api/taglibrary/dir'

export default {
  name: 'TagMapping',
  dicts: ['tag_type'],
  data() {
    return {
      // 遮罩层
      loading: true,
      // 保存草稿中
      saving: false,
      // 提交审核中
      submitting: false,
      // 总条数
      total: 0,
      // 标签库信息（路由 query 传入）
      libraryId: undefined,
      libraryName: '',
      // 标签分页列表（每行带 edited/original）
      tagList: [],
      // 目录选项
      dirOptions: [],
      // 当前页勾选的待提交 tagId
      checkedTagIds: [],
      // 当前编辑单元格标识：tagId_field
      editingCell: '',
      // 单元格编辑缓存值
      editCache: undefined,
      // 目录选择弹窗
      dirDialogVisible: false,
      dirDialogRow: null,
      dirDialogValue: undefined,
      // 口径弹窗
      caliberVisible: false,
      caliberDialogTitle: '',
      caliberReadonly: false,
      caliberRow: null,
      caliberField: '',
      caliberValue: '',
      // 查询参数
      queryParams: {
        pageNum: 1,
        pageSize: 10,
        libraryId: undefined,
        tagName: '',
        fieldName: '',
        dirId: undefined
      }
    }
  },
  created() {
    this.libraryId = this.$route.query.libraryId
    this.libraryName = this.$route.query.libraryName || ''
    this.queryParams.libraryId = this.libraryId
    this.loadDirOptions()
  },
  activated() {
    // keep-alive 复用组件时 created 不再执行，进入/返回本页都在此先同步关联数据集字段再加载列表
    this.enterAndSync()
  },
  methods: {
    /** 进入页面：先增量同步关联数据集的所有字段为标签，再加载映射列表（同步失败仍展示现有数据） */
    enterAndSync() {
      if (!this.libraryId) {
        this.getList()
        return
      }
      syncMappingFields(this.libraryId)
        .then(() => this.getList())
        .catch(() => this.getList())
    },
    /** 查询批量映射标签分页列表 */
    getList() {
      this.loading = true
      mappingList(this.queryParams).then(response => {
        this.tagList = (response.rows || []).map(row => this.wrapRow(row))
        this.total = response.total
        this.checkedTagIds = []
        this.closeEdit()
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    /** 包装行数据：edited 为当前编辑值，original 为 tl_tag 原始值 */
    wrapRow(row) {
      const original = {
        tagName: row.tagName,
        tagType: row.tagType,
        dirId: row.dirId,
        techCaliber: row.techCaliber,
        businessCaliber: row.businessCaliber
      }
      const edited = Object.assign({}, original, { dirName: undefined })
      // 本人草稿：用 afterJson 覆盖显示值
      if (row.ownDraft && row.afterJson) {
        try {
          Object.assign(edited, JSON.parse(row.afterJson))
        } catch (e) {
          // afterJson 解析失败时按原始值展示
        }
      }
      row.original = original
      row.edited = edited
      return row
    },
    /** 加载目录选项 */
    loadDirOptions() {
      if (!this.libraryId) return
      listDir(this.libraryId).then(response => {
        this.dirOptions = response.data || response.rows || []
      })
    },
    /** 搜索 */
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
    },
    /** 翻页/改页大小：有未保存修改时先确认 */
    handlePagination(data) {
      const oldPage = this.queryParams.pageNum
      const oldSize = this.queryParams.pageSize
      const applyPage = () => {
        this.queryParams.pageNum = data.page
        this.queryParams.pageSize = data.limit
      }
      if (this.tagList.some(row => this.isRowDirty(row))) {
        this.$confirm('当前有未保存的修改，是否先保存草稿？', '提示', { type: 'warning' }).then(() => {
          // 确认：先保存草稿，成功后按新分页刷新
          applyPage()
          return this.doSaveDraft(false).catch(() => {
            // 保存失败：回退分页参数，停留当前页
            this.queryParams.pageNum = oldPage
            this.queryParams.pageSize = oldSize
          })
        }).catch(() => {
          // 取消：放弃修改，直接翻页刷新
          applyPage()
          this.getList()
        })
      } else {
        applyPage()
        this.getList()
      }
    },
    /** 字段值归一化后比较 */
    normalize(val) {
      return val == null ? '' : String(val)
    },
    /** 某字段是否已修改 */
    isFieldDirty(row, field) {
      return this.normalize(row.edited[field]) !== this.normalize(row.original[field])
    },
    /** 行是否有未保存修改 */
    isRowDirty(row) {
      return ['tagName', 'tagType', 'dirId', 'techCaliber', 'businessCaliber'].some(f => this.isFieldDirty(row, f))
    },
    /** 是否他人草稿 */
    isOthersDraft(row) {
      return row.changeId != null && !row.ownDraft
    },
    /** 整行只读：待审核中 或 他人草稿 */
    isRowReadonly(row) {
      return row.changeStatus === 'PENDING' || this.isOthersDraft(row)
    },
    /** 是否允许勾选提交 */
    canSubmitRow(row) {
      return row.ownDraft && row.changeStatus === 'DRAFT'
    },
    /** 提交勾选禁用原因 */
    submitDisabledReason(row) {
      if (row.changeStatus === 'PENDING') return '已提交，待审核'
      if (this.isOthersDraft(row)) return '他人草稿，不可提交'
      return '该行没有草稿，请先修改并保存草稿'
    },
    /** 目录显示名 */
    dirLabel(row) {
      const dir = this.dirOptions.find(d => d.dirId === row.edited.dirId)
      if (dir) return dir.dirName
      return row.edited.dirName || '-'
    },
    /** 是否勾选 */
    isChecked(row) {
      return this.checkedTagIds.indexOf(row.tagId) !== -1
    },
    /** 勾选/取消勾选 */
    toggleRow(row, checked) {
      const idx = this.checkedTagIds.indexOf(row.tagId)
      if (checked && idx === -1) {
        this.checkedTagIds.push(row.tagId)
      } else if (!checked && idx !== -1) {
        this.checkedTagIds.splice(idx, 1)
      }
    },
    /** 进入单元格编辑态 */
    isEditing(row, field) {
      return this.editingCell === row.tagId + '_' + field
    },
    /** 点击进入编辑态 */
    startEdit(row, field) {
      if (this.isRowReadonly(row)) return
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
      this.closeEdit()
    },
    /** 关闭编辑态 */
    closeEdit() {
      this.editingCell = ''
      this.editCache = undefined
    },
    /** 打开目录选择弹窗 */
    openDirDialog(row) {
      if (this.isRowReadonly(row)) return
      this.dirDialogRow = row
      this.dirDialogValue = row.edited.dirId
      this.dirDialogVisible = true
    },
    /** 确认目录选择 */
    confirmDirDialog() {
      const dir = this.dirOptions.find(d => d.dirId === this.dirDialogValue)
      this.dirDialogRow.edited.dirId = this.dirDialogValue
      this.dirDialogRow.edited.dirName = dir ? dir.dirName : undefined
      this.dirDialogVisible = false
    },
    /** 打开口径弹窗（填写/查看） */
    openCaliberDialog(row, field) {
      this.caliberRow = row
      this.caliberField = field
      this.caliberValue = row.edited[field] || ''
      this.caliberReadonly = this.isRowReadonly(row)
      this.caliberDialogTitle = (field === 'techCaliber' ? '技术口径' : '业务口径') + '（' + row.fieldName + '）'
      this.caliberVisible = true
    },
    /** 确认口径填写 */
    confirmCaliberDialog() {
      this.caliberRow.edited[this.caliberField] = this.caliberValue
      this.caliberVisible = false
    },
    /** 保存草稿（按钮入口，空修改时提示） */
    handleSaveDraft() {
      this.doSaveDraft(true)
    },
    /** 保存草稿实现 */
    doSaveDraft(warnWhenEmpty) {
      const dirtyRows = this.tagList.filter(row => this.isRowDirty(row) && !this.isRowReadonly(row))
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
        businessCaliber: row.edited.businessCaliber
      }))
      this.saving = true
      return saveMappingDraft(items).then(() => {
        this.$modal.msgSuccess('草稿保存成功')
        this.saving = false
        this.getList()
      }).catch(() => {
        this.saving = false
        // 保存失败时不翻页，回退页码状态由用户重试
        return Promise.reject()
      })
    },
    /** 提交审核 */
    handleSubmit() {
      const rows = this.tagList.filter(row => this.isChecked(row) && this.canSubmitRow(row))
      if (rows.length === 0) {
        this.$modal.msgWarning('请先勾选要提交的草稿行')
        return
      }
      this.$confirm('确认提交所选 ' + rows.length + ' 条草稿进入审核？', '提示', { type: 'warning' }).then(() => {
        this.submitting = true
        return submitMapping(rows.map(row => row.changeId))
      }).then(() => {
        this.$modal.msgSuccess('已提交审核')
        this.submitting = false
        this.getList()
      }).catch(() => {
        this.submitting = false
      })
    }
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.library-title {
  margin-left: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.cell-click {
  cursor: pointer;
  min-height: 23px;
}

.cell-tag {
  margin-left: 6px;
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
</style>
