<template>
  <div class="app-container">
    <!-- 查询栏 -->
    <el-form :inline="true" :model="queryParams" size="small">
      <el-form-item label="维表名称">
        <el-input v-model="queryParams.dimensionName" placeholder="请输入维表名称" clearable style="width: 160px;" @keyup.enter.native="handleQuery" />
      </el-form-item>
      <el-form-item label="维表名">
        <el-input v-model="queryParams.dimensionCode" placeholder="请输入维表名" clearable style="width: 160px;" @keyup.enter.native="handleQuery" />
      </el-form-item>
      <el-form-item label="数据连接">
        <el-select v-model="queryParams.datasourceId" placeholder="全部" clearable style="width: 160px;">
          <el-option v-for="d in datasourceOptions" :key="d.datasourceId" :label="d.sourceName" :value="d.datasourceId" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 110px;">
          <el-option label="启用" value="0" />
          <el-option label="停用" value="1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-search" @click="handleQuery">搜索</el-button>
        <el-button icon="el-icon-refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <el-button-group>
        <el-button size="small" type="primary" icon="el-icon-plus" @click="handleAdd" v-hasPermi="['databroker:dimension:add']">新建维表</el-button>
        <el-button size="small" type="danger" icon="el-icon-delete" @click="handleBatchDelete" v-hasPermi="['databroker:dimension:remove']">批量删除</el-button>
      </el-button-group>
      <span class="selection-tip">已选 {{ selection.length }} 项</span>
    </el-row>

    <!-- 维表列表 -->
    <el-table :data="dimensionList" v-loading="loading" size="small" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="45" align="center" />
      <el-table-column prop="dimensionName" label="维表名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="datasourceName" label="数据连接" min-width="120" show-overflow-tooltip />
      <el-table-column prop="sourceTableName" label="原始表名" min-width="140" show-overflow-tooltip />
      <el-table-column prop="dimensionCode" label="维表名" min-width="120" show-overflow-tooltip />
      <el-table-column label="当前状态" width="90" align="center">
        <template #default="scope">
          <el-switch v-if="canEditStatus" v-model="scope.row.status" active-value="0" inactive-value="1" @change="handleStatusChange(scope.row)" />
          <el-tag v-else :type="scope.row.status === '0' ? 'success' : 'info'" size="mini">
            {{ scope.row.status === '0' ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createBy" label="创建人" width="90" align="center" />
      <el-table-column prop="createTime" label="创建时间" width="160" align="center" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="scope">
          <el-button type="text" size="mini" icon="el-icon-view" @click="handleDetail(scope.row)">详情</el-button>
          <el-button type="text" size="mini" icon="el-icon-edit" @click="handleEdit(scope.row)" v-hasPermi="['databroker:dimension:edit']">编辑</el-button>
          <el-button type="text" size="mini" icon="el-icon-delete" @click="handleDelete(scope.row)" v-hasPermi="['databroker:dimension:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <pagination v-show="total > 0" :total="total" :page.sync="queryParams.pageNum" :limit.sync="queryParams.pageSize" @pagination="getList" />

    <!-- 新建维表弹窗 -->
    <el-dialog title="新建维表" :visible.sync="addVisible" width="640px" append-to-body @close="resetAddForm">
      <el-form ref="addForm" :model="addForm" :rules="addRules" label-width="110px" size="small">
        <el-form-item label="维表名称" prop="dimensionName">
          <el-input v-model="addForm.dimensionName" placeholder="请输入维表名称" maxlength="64" />
        </el-form-item>
        <el-form-item label="维表名" prop="dimensionCode">
          <el-input v-model="addForm.dimensionCode" placeholder="英文编码，字母/数字/下划线" maxlength="64" />
        </el-form-item>
        <el-form-item label="数据连接" prop="datasourceId">
          <el-select v-model="addForm.datasourceId" placeholder="请选择数据连接" filterable style="width: 100%;" @change="handleAddDatasourceChange">
            <el-option v-for="d in datasourceOptions" :key="d.datasourceId" :label="d.sourceName" :value="d.datasourceId" />
          </el-select>
        </el-form-item>
        <el-form-item label="原始表名" prop="sourceTableId">
          <el-select v-model="addForm.sourceTableId" placeholder="请先选择数据连接" filterable style="width: 100%;" :loading="tableLoading" @change="handleAddTableChange">
            <el-option v-for="t in tableOptions" :key="t.tableId" :label="t.objectName + (t.cnName ? '（' + t.cnName + '）' : '')" :value="t.tableId" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="addFieldChecks.length > 0" label="标准字段校验">
          <div class="field-check-list">
            <div v-for="f in addFieldChecks" :key="f.columnName" class="field-check-item">
              <span class="field-check-name">{{ f.columnName }}</span>
              <span v-if="f.exists" class="field-check-ok"><i class="el-icon-circle-check" /> 存在</span>
              <span v-else class="field-check-miss"><i class="el-icon-circle-close" /> 缺失</span>
            </div>
          </div>
          <el-alert v-if="hasMissingFields" type="warning" :closable="false" title="缺失标准字段，无法登记" class="field-check-alert" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="addForm.remark" type="textarea" :rows="2" placeholder="请输入备注" maxlength="500" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="addVisible = false">取消</el-button>
        <el-button size="small" type="primary" :disabled="hasMissingFields" :loading="submitLoading" @click="submitAdd">确定</el-button>
      </div>
    </el-dialog>

    <!-- 编辑维表弹窗 -->
    <el-dialog title="编辑维表" :visible.sync="editVisible" width="560px" append-to-body>
      <el-form ref="editForm" :model="editForm" :rules="editRules" label-width="100px" size="small">
        <el-form-item label="维表名称" prop="dimensionName">
          <el-input v-model="editForm.dimensionName" placeholder="请输入维表名称" maxlength="64" />
        </el-form-item>
        <el-form-item label="维表名">
          <span>{{ editForm.dimensionCode }}</span>
        </el-form-item>
        <el-form-item label="数据连接">
          <span>{{ editForm.datasourceName }}</span>
        </el-form-item>
        <el-form-item label="原始表名">
          <span>{{ editForm.sourceTableName }}</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" placeholder="请输入备注" maxlength="500" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="editVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="submitLoading" @click="submitEdit">确定</el-button>
      </div>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer :title="'维表详情：' + (detail.dimensionName || '')" :visible.sync="drawerVisible" size="55%">
      <div class="drawer-body" v-loading="detailLoading">
        <!-- 登记基础信息 -->
        <div class="drawer-section-title">登记基础信息</div>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="维表名称">{{ detail.dimensionName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="维表名">{{ detail.dimensionCode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="数据连接">{{ detail.datasourceName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="原始表名">{{ detail.sourceTableName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.status === '0' ? 'success' : 'info'" size="mini">{{ detail.status === '0' ? '启用' : '停用' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.createBy || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.createTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 标准字段校验结果 -->
        <div class="drawer-section-title">标准字段校验结果</div>
        <el-alert v-if="detailFieldChecks === null" type="error" :closable="false" :title="detailCheckError || '连接失败，无法校验标准字段'" />
        <div v-else class="field-check-list">
          <div v-for="f in detailFieldChecks" :key="f.columnName" class="field-check-item">
            <span class="field-check-name">{{ f.columnName }}</span>
            <span v-if="f.exists" class="field-check-ok"><i class="el-icon-circle-check" /> 存在</span>
            <span v-else class="field-check-miss"><i class="el-icon-circle-close" /> 缺失</span>
          </div>
        </div>

        <!-- 已关联标签库 -->
        <div class="drawer-section-title">已关联标签库</div>
        <el-table :data="libraryList" v-loading="libraryLoading" size="small" empty-text="暂无关联">
          <el-table-column prop="libraryName" label="标签库名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="90" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.status === '2' ? 'success' : 'info'" size="mini">{{ scope.row.status === '2' ? '已上线' : '未上线' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <!-- 物理码值只读分页预览 -->
        <div class="drawer-section-title">物理码值预览</div>
        <el-table :data="valuesList" v-loading="valuesLoading" size="small">
          <el-table-column prop="tagNameEn" label="英文字段" min-width="120" show-overflow-tooltip />
          <el-table-column prop="tagCode" label="码值" min-width="110" show-overflow-tooltip />
          <el-table-column prop="tagNameCn" label="中文名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="codeDefinition" label="码值定义" min-width="140" show-overflow-tooltip />
          <el-table-column prop="codeSort" label="排序" width="70" align="center" />
          <el-table-column prop="lastUpdateTime" label="最后更新时间" width="160" align="center" />
        </el-table>
        <pagination v-show="valuesTotal > 0" :total="valuesTotal" :page.sync="valuesQuery.pageNum" :limit.sync="valuesQuery.pageSize" @pagination="getValuesList" />
      </div>
    </el-drawer>
  </div>
</template>

<script>
import {
  listDimension, getDimension, addDimension, updateDimension, delDimension,
  changeDimensionStatus, datasourceOptions, tableOptions, fieldChecks,
  listDimensionValues, listLinkedLibraries
} from '@/api/databroker/dimension'
import { checkPermi } from '@/utils/permission'

export default {
  name: 'DimensionManage',
  data() {
    return {
      // 列表
      dimensionList: [],
      total: 0,
      loading: false,
      selection: [],
      queryParams: { pageNum: 1, pageSize: 10, dimensionName: '', dimensionCode: '', datasourceId: undefined, status: '' },
      // 下拉选项
      datasourceOptions: [],
      tableOptions: [],
      tableLoading: false,
      // 新建弹窗
      addVisible: false,
      submitLoading: false,
      addForm: { dimensionName: '', dimensionCode: '', datasourceId: undefined, sourceTableId: undefined, remark: '' },
      addFieldChecks: [],
      addRules: {
        dimensionName: [{ required: true, message: '维表名称不能为空', trigger: 'blur' }],
        dimensionCode: [
          { required: true, message: '维表名不能为空', trigger: 'blur' },
          { pattern: /^[A-Za-z0-9_]{1,64}$/, message: '仅支持字母、数字、下划线，长度1-64位', trigger: 'blur' }
        ],
        datasourceId: [{ required: true, message: '请选择数据连接', trigger: 'change' }],
        sourceTableId: [{ required: true, message: '请选择原始表名', trigger: 'change' }]
      },
      // 编辑弹窗
      editVisible: false,
      editForm: { dimensionId: undefined, dimensionName: '', dimensionCode: '', datasourceName: '', sourceTableName: '', remark: '' },
      editRules: {
        dimensionName: [{ required: true, message: '维表名称不能为空', trigger: 'blur' }]
      },
      // 详情抽屉
      drawerVisible: false,
      detailLoading: false,
      detail: {},
      detailFieldChecks: null,
      detailCheckError: '',
      libraryList: [],
      libraryLoading: false,
      valuesList: [],
      valuesTotal: 0,
      valuesLoading: false,
      valuesQuery: { pageNum: 1, pageSize: 10 }
    }
  },
  computed: {
    /** 是否有状态切换权限（无权限时只读展示 el-tag） */
    canEditStatus() {
      return checkPermi(['databroker:dimension:status'])
    },
    /** 新建弹窗是否存在缺失标准字段 */
    hasMissingFields() {
      return this.addFieldChecks.some(f => !f.exists)
    }
  },
  created() {
    this.getList()
    this.getDatasourceOptions()
  },
  methods: {
    /** 维表列表 */
    getList() {
      this.loading = true
      listDimension(this.queryParams).then(response => {
        this.dimensionList = response.rows
        this.total = response.total
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    /** 数据连接下拉选项 */
    getDatasourceOptions() {
      datasourceOptions().then(response => {
        this.datasourceOptions = response.data
      }).catch(() => {})
    },
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
    },
    resetQuery() {
      this.queryParams = { pageNum: 1, pageSize: 10, dimensionName: '', dimensionCode: '', datasourceId: undefined, status: '' }
      this.handleQuery()
    },
    handleSelectionChange(selection) {
      this.selection = selection
    },
    /** 状态切换：直接调接口，失败时回滚（不弹确认框） */
    handleStatusChange(row) {
      changeDimensionStatus(row.dimensionId, row.status).then(() => {
        this.$modal.msgSuccess(row.status === '0' ? '启用成功' : '停用成功')
      }).catch(() => {
        row.status = row.status === '0' ? '1' : '0'
      })
    },
    /** 新建 */
    handleAdd() {
      this.resetAddForm()
      this.addVisible = true
    },
    resetAddForm() {
      this.addForm = { dimensionName: '', dimensionCode: '', datasourceId: undefined, sourceTableId: undefined, remark: '' }
      this.tableOptions = []
      this.addFieldChecks = []
      if (this.$refs.addForm) this.$refs.addForm.clearValidate()
    },
    /** 新建弹窗：数据连接变化，加载物理表 */
    handleAddDatasourceChange(datasourceId) {
      this.addForm.sourceTableId = undefined
      this.addFieldChecks = []
      this.tableOptions = []
      if (!datasourceId) return
      this.tableLoading = true
      tableOptions(datasourceId).then(response => {
        this.tableOptions = response.data
        this.tableLoading = false
      }).catch(() => { this.tableLoading = false })
    },
    /** 新建弹窗：原始表变化，校验六个标准字段 */
    handleAddTableChange(sourceTableId) {
      this.addFieldChecks = []
      if (!sourceTableId) return
      fieldChecks(sourceTableId).then(response => {
        this.addFieldChecks = response.data || []
      }).catch(() => {})
    },
    /** 提交登记 */
    submitAdd() {
      this.$refs.addForm.validate(valid => {
        if (!valid) return
        this.submitLoading = true
        addDimension(this.addForm).then(() => {
          this.$modal.msgSuccess('登记成功')
          this.addVisible = false
          this.submitLoading = false
          this.getList()
        }).catch(() => { this.submitLoading = false })
      })
    },
    /** 编辑（仅维表名称、备注可改，其余只读展示） */
    handleEdit(row) {
      this.editForm = {
        dimensionId: row.dimensionId,
        dimensionName: row.dimensionName,
        dimensionCode: row.dimensionCode,
        datasourceName: row.datasourceName,
        sourceTableName: row.sourceTableName,
        remark: row.remark
      }
      this.editVisible = true
    },
    submitEdit() {
      this.$refs.editForm.validate(valid => {
        if (!valid) return
        this.submitLoading = true
        updateDimension({
          dimensionId: this.editForm.dimensionId,
          dimensionName: this.editForm.dimensionName,
          remark: this.editForm.remark
        }).then(() => {
          this.$modal.msgSuccess('修改成功')
          this.editVisible = false
          this.submitLoading = false
          this.getList()
        }).catch(() => { this.submitLoading = false })
      })
    },
    /** 删除单条 */
    handleDelete(row) {
      this.$confirm('确认删除维表"' + row.dimensionName + '"吗？', '提示', { type: 'warning' }).then(() => {
        return delDimension(row.dimensionId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.getList()
      }).catch(() => {})
    },
    /** 批量删除 */
    handleBatchDelete() {
      if (this.selection.length === 0) {
        this.$modal.msgWarning('请至少选择一条维表')
        return
      }
      const ids = this.selection.map(d => d.dimensionId).join(',')
      this.$confirm('确认删除选中的 ' + this.selection.length + ' 个维表吗？', '提示', { type: 'warning' }).then(() => {
        return delDimension(ids)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.getList()
      }).catch(() => {})
    },
    /** 详情抽屉 */
    handleDetail(row) {
      this.drawerVisible = true
      this.detailLoading = true
      this.detail = {}
      this.detailFieldChecks = null
      this.detailCheckError = ''
      this.libraryList = []
      this.valuesList = []
      this.valuesTotal = 0
      this.valuesQuery = { pageNum: 1, pageSize: 10 }
      getDimension(row.dimensionId).then(response => {
        const data = response.data || {}
        this.detail = data
        this.detailFieldChecks = data.fieldChecks
        this.detailCheckError = data.checkError || ''
        this.detailLoading = false
      }).catch(() => { this.detailLoading = false })
      this.getLibraryList(row.dimensionId)
      this.getValuesList(row.dimensionId)
    },
    /** 已关联标签库 */
    getLibraryList(dimensionId) {
      this.libraryLoading = true
      listLinkedLibraries(dimensionId || this.detail.dimensionId).then(response => {
        this.libraryList = response.data || []
        this.libraryLoading = false
      }).catch(() => { this.libraryLoading = false })
    },
    /** 物理码值分页预览 */
    getValuesList(dimensionId) {
      this.valuesLoading = true
      listDimensionValues(dimensionId || this.detail.dimensionId, this.valuesQuery).then(response => {
        this.valuesList = response.rows
        this.valuesTotal = response.total
        this.valuesLoading = false
      }).catch(() => { this.valuesLoading = false })
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

.drawer-body {
  padding: 0 20px 20px;
}

.drawer-section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 20px 0 10px;
}

.drawer-section-title:first-child {
  margin-top: 0;
}

.field-check-list {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.field-check-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid #ebeef5;
  font-size: 12px;
}

.field-check-item:last-child {
  border-bottom: none;
}

.field-check-name {
  font-family: monospace;
}

.field-check-ok {
  color: #67c23a;
}

.field-check-miss {
  color: #f56c6c;
}

.field-check-alert {
  margin-top: 8px;
}
</style>
