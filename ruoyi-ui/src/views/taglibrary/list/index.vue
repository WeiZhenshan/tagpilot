<template>
  <div class="app-container">
    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <el-button type="primary" icon="el-icon-plus" @click="handleAdd" v-hasPermi="['taglibrary:library:add']">新建标签库</el-button>
      <div class="toolbar-right">
        <el-input v-model="queryParams.libraryName" placeholder="名称或编码" clearable size="small" style="width: 180px; margin-right: 8px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
        <el-select v-model="queryParams.tagObject" placeholder="标签对象" clearable size="small" style="width: 130px; margin-right: 8px;" @change="handleQuery">
          <el-option v-for="d in dict.type.tag_object" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-select v-model="queryParams.category" placeholder="分类" clearable size="small" style="width: 130px; margin-right: 8px;" @change="handleQuery">
          <el-option v-for="d in dict.type.tag_library_category" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-button-group>
          <el-button size="small" icon="el-icon-menu" :type="viewMode === 'card' ? 'primary' : 'default'" @click="viewMode = 'card'" />
          <el-button size="small" icon="el-icon-tickets" :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'" />
        </el-button-group>
      </div>
    </el-row>

    <!-- 卡片视图 -->
    <div v-show="viewMode === 'card'" v-loading="loading">
      <el-row :gutter="16">
        <el-col v-for="row in libraryList" :key="row.libraryId" :span="8">
          <el-card class="library-card" shadow="hover">
            <div class="card-line card-title">
              <span class="card-name" :title="row.libraryName">{{ row.libraryName }}</span>
              <el-tag :type="statusType(row.status)" size="mini">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <div class="card-line card-meta">
              <span>所属分类：{{ row.category || '-' }}</span>
              <span class="card-meta-divider">|</span>
              <span>标签对象：{{ row.tagObject || '-' }}</span>
            </div>
            <div class="card-line card-meta">
              <span>负责人：{{ row.ownerName || '-' }}</span>
              <span class="card-meta-divider">|</span>
              <span>更新时间：{{ row.updateTime || row.createTime || '-' }}</span>
            </div>
            <div class="card-line card-stats">
              <div class="stat-item">
                <div class="stat-num">{{ row.onlineCount || 0 }}</div>
                <div class="stat-label">上线</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ row.pendingCount || 0 }}</div>
                <div class="stat-label">待发布</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ row.offlineCount || 0 }}</div>
                <div class="stat-label">下线</div>
              </div>
            </div>
            <div class="card-line card-source">关联数据集：{{ row.datasetName || '-' }}</div>
            <div class="card-footer">
              <span>
                <el-button type="text" icon="el-icon-price-tag" @click="goTagManage(row)">标签管理</el-button>
                <el-button type="text" icon="el-icon-chat-dot-round" @click="goAgentWorkbench(row)" v-hasPermi="['taglibrary:semantic:list']">打开智能体</el-button>
              </span>
              <el-dropdown trigger="click" @command="cmd => handleMore(cmd, row)">
                <el-button type="text">更多<i class="el-icon-arrow-down el-icon--right" /></el-button>
                <el-dropdown-menu slot="dropdown">
                  <el-dropdown-item command="fields" icon="el-icon-set-up" v-hasPermi="['taglibrary:tag:list']">字段管理</el-dropdown-item>
                  <el-dropdown-item command="dimension" icon="el-icon-collection" v-hasPermi="['taglibrary:library:dimension:list']">设置默认码表</el-dropdown-item>
                  <el-dropdown-item command="mapping" icon="el-icon-connection" v-hasPermi="['taglibrary:tag:mapping:list']">批量映射</el-dropdown-item>
                  <el-dropdown-item command="edit" icon="el-icon-edit" v-hasPermi="['taglibrary:library:edit']">编辑标签库</el-dropdown-item>
                  <el-dropdown-item v-if="row.status==='0'||row.status==='3'" command="submit" icon="el-icon-upload2" v-hasPermi="['taglibrary:library:submit']">提交上线</el-dropdown-item>
                  <el-dropdown-item v-if="row.status==='2'" command="offline" icon="el-icon-download" v-hasPermi="['taglibrary:library:offline']">下线</el-dropdown-item>
                  <el-dropdown-item command="audit" icon="el-icon-s-check" v-hasPermi="['taglibrary:library:audit']">审批管理</el-dropdown-item>
                  <el-dropdown-item command="remove" icon="el-icon-delete" divided v-hasPermi="['taglibrary:library:remove']">删除标签库</el-dropdown-item>
                </el-dropdown-menu>
              </el-dropdown>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-empty v-if="!loading && libraryList.length === 0" description="暂无标签库" />
    </div>

    <!-- 列表视图 -->
    <el-table v-show="viewMode === 'list'" :data="libraryList" v-loading="loading" size="small">
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
      <el-table-column prop="datasetName" label="关联数据集" min-width="130" show-overflow-tooltip />
      <el-table-column prop="ownerName" label="负责人" width="90" align="center" />
      <el-table-column prop="updateTime" label="更新时间" width="160" align="center" />
      <el-table-column label="统计" width="180" align="center">
        <template #default="scope">
          上线 {{ scope.row.onlineCount || 0 }} / 待发布 {{ scope.row.pendingCount || 0 }} / 下线 {{ scope.row.offlineCount || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="scope">
          <el-button type="text" size="mini" icon="el-icon-price-tag" @click="goTagManage(scope.row)">标签管理</el-button>
          <el-button type="text" size="mini" icon="el-icon-chat-dot-round" @click="goAgentWorkbench(scope.row)" v-hasPermi="['taglibrary:semantic:list']">打开智能体</el-button>
          <el-button type="text" size="mini" icon="el-icon-edit" @click="handleUpdate(scope.row)" v-hasPermi="['taglibrary:library:edit']">编辑</el-button>
          <el-button type="text" size="mini" icon="el-icon-delete" @click="handleMore('remove', scope.row)" v-hasPermi="['taglibrary:library:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" :page.sync="queryParams.pageNum" :limit.sync="queryParams.pageSize" @pagination="getList" />

    <!-- 新建/编辑标签库弹窗 -->
    <el-dialog :title="title" :visible.sync="open" width="600px" append-to-body @close="resetForm">
      <el-form ref="form" :model="form" :rules="rules" label-width="100px" size="small">
        <el-form-item label="标签库名称" prop="libraryName">
          <el-input v-model="form.libraryName" placeholder="请输入标签库名称" maxlength="64" />
        </el-form-item>
        <el-form-item label="标签库编码" prop="libraryCode">
          <el-input v-model="form.libraryCode" placeholder="请输入标签库编码" maxlength="64" :disabled="!!form.libraryId" />
        </el-form-item>
        <el-form-item label="标签对象" prop="tagObject">
          <el-select v-model="form.tagObject" placeholder="请选择标签对象" style="width: 100%;">
            <el-option v-for="d in dict.type.tag_object" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属分类" prop="category">
          <el-select v-model="form.category" placeholder="请选择分类" clearable style="width: 100%;">
            <el-option v-for="d in dict.type.tag_library_category" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人" prop="ownerName">
          <el-input v-model="form.ownerName" placeholder="请输入负责人" maxlength="30" />
        </el-form-item>
        <el-form-item label="关联数据集" prop="datasetId">
          <el-select v-model="form.datasetId" placeholder="请选择关联数据集" filterable style="width: 100%;" :disabled="!!form.libraryId">
            <el-option v-for="item in datasetOptions" :key="item.datasetId" :label="item.datasetName + '（' + item.datasetCode + '）'" :value="item.datasetId" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" maxlength="500" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="open = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitForm">确定</el-button>
      </div>
    </el-dialog>

    <!-- 字段管理抽屉 -->
    <el-drawer :title="'字段管理：' + (currentLibrary.libraryName || '')" :visible.sync="drawerVisible" size="60%">
      <div class="drawer-body">
        <div class="drawer-toolbar">
          <el-button type="primary" size="small" icon="el-icon-refresh" @click="handleSyncFields" v-hasPermi="['taglibrary:library:sync']">同步字段</el-button>
        </div>
        <el-table :data="tagList" v-loading="tagLoading" size="small">
          <el-table-column prop="fieldName" label="字段名" min-width="130" show-overflow-tooltip />
          <el-table-column prop="tagName" label="标签名" min-width="130" show-overflow-tooltip />
          <el-table-column label="目录" width="110">
            <template #default="scope">{{ dirName(scope.row.dirId) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="90" align="center">
            <template #default="scope">
              <dict-tag :options="dict.type.tag_type" :value="scope.row.tagType" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="scope">
              <el-tag :type="statusType(scope.row.status)" size="mini">{{ statusLabel(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="scope">
              <el-button type="text" size="mini" @click="openTagEdit(scope.row)" v-hasPermi="['taglibrary:tag:edit']">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <pagination v-show="tagTotal > 0" :total="tagTotal" :page.sync="tagQuery.pageNum" :limit.sync="tagQuery.pageSize" @pagination="loadTagList" />
      </div>
    </el-drawer>

    <!-- 标签编辑弹窗 -->
    <el-dialog title="编辑标签" :visible.sync="tagEditVisible" width="600px" append-to-body>
      <el-form ref="tagForm" :model="tagForm" :rules="tagRules" label-width="100px" size="small">
        <el-form-item label="标签名" prop="tagName">
          <el-input v-model="tagForm.tagName" placeholder="请输入标签名" maxlength="128" />
        </el-form-item>
        <el-form-item label="所属目录" prop="dirId">
          <el-select v-model="tagForm.dirId" placeholder="请选择目录" style="width: 100%;">
            <el-option v-for="d in dirOptions" :key="d.dirId" :label="d.dirName" :value="d.dirId" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签类型" prop="tagType">
          <el-select v-model="tagForm.tagType" placeholder="请选择标签类型" style="width: 100%;">
            <el-option v-for="d in dict.type.tag_type" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务口径">
          <el-input v-model="tagForm.businessCaliber" type="textarea" :rows="2" placeholder="请输入业务口径" maxlength="500" />
        </el-form-item>
        <el-form-item label="技术口径">
          <el-input v-model="tagForm.techCaliber" type="textarea" :rows="2" placeholder="请输入技术口径" maxlength="500" />
        </el-form-item>
        <el-form-item label="有效日期">
          <el-input v-model="tagForm.validPeriod" placeholder="如：永久有效" maxlength="32" />
        </el-form-item>
        <el-form-item label="更新周期">
          <el-select v-model="tagForm.updateCycle" placeholder="请选择更新周期" style="width: 100%;">
            <el-option v-for="d in dict.type.tag_update_cycle" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="tagEditVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitTagForm">确定</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { listLibrary, listOnlineDatasets, getLibrary, addLibrary, updateLibrary, delLibrary,
  syncLibrary, submitLibrary, offlineLibrary } from '@/api/taglibrary/library'
import { listDir } from '@/api/taglibrary/dir'
import { listTag, updateTag } from '@/api/taglibrary/tag'
import { agentWorkbenchLocation } from '@/utils/agentWorkbench'

export default {
  name: 'TagLibraryList',
  dicts: ['tag_object', 'tag_library_category', 'tag_type', 'tag_update_cycle'],
  data() {
    return {
      // 遮罩层
      loading: true,
      // 总条数
      total: 0,
      // 标签库列表
      libraryList: [],
      // 视图模式：card 卡片 / list 列表
      viewMode: 'card',
      // 查询参数
      queryParams: {
        pageNum: 1,
        pageSize: 12,
        libraryName: '',
        category: '',
        tagObject: ''
      },
      // 状态映射（非字典，自建 map）
      statusMap: {
        '0': { label: '草稿', type: 'info' },
        '1': { label: '待审批', type: 'warning' },
        '2': { label: '已上线', type: 'success' },
        '3': { label: '已下线', type: 'danger' }
      },
      // 新建/编辑弹窗
      open: false,
      title: '',
      datasetOptions: [],
      form: {},
      rules: {
        libraryName: [{ required: true, message: '标签库名称不能为空', trigger: 'blur' }],
        libraryCode: [{ required: true, message: '标签库编码不能为空', trigger: 'blur' }],
        tagObject: [{ required: true, message: '标签对象不能为空', trigger: 'change' }],
        datasetId: [{ required: true, message: '关联数据集不能为空', trigger: 'change' }]
      },
      // 字段管理抽屉
      drawerVisible: false,
      currentLibrary: {},
      tagList: [],
      tagTotal: 0,
      tagLoading: false,
      tagQuery: { pageNum: 1, pageSize: 10, libraryId: null },
      dirOptions: [],
      // 标签编辑弹窗
      tagEditVisible: false,
      tagForm: {},
      tagRules: {
        tagName: [{ required: true, message: '标签名不能为空', trigger: 'blur' }],
        dirId: [{ required: true, message: '所属目录不能为空', trigger: 'change' }],
        tagType: [{ required: true, message: '标签类型不能为空', trigger: 'change' }]
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    /** 查询标签库列表 */
    getList() {
      this.loading = true
      listLibrary(this.queryParams).then(response => {
        this.libraryList = response.rows
        this.total = response.total
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    /** 搜索 */
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
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
    /** 表单重置 */
    resetForm() {
      this.form = {
        libraryId: undefined,
        libraryName: undefined,
        libraryCode: undefined,
        tagObject: undefined,
        category: undefined,
        ownerName: undefined,
        datasetId: undefined,
        remark: undefined
      }
      this.$nextTick(() => { if (this.$refs.form) this.$refs.form.clearValidate() })
    },
    /** 加载已上线数据集选项 */
    loadDatasetOptions() {
      listOnlineDatasets().then(response => {
        this.datasetOptions = response.data || []
      })
    },
    /** 新增标签库 */
    handleAdd() {
      this.resetForm()
      this.title = '新建标签库'
      this.loadDatasetOptions()
      this.open = true
    },
    /** 修改标签库 */
    handleUpdate(row) {
      this.resetForm()
      getLibrary(row.libraryId).then(response => {
        this.form = response.data
        this.title = '编辑标签库'
        this.loadDatasetOptions()
        this.open = true
      })
    },
    /** 提交表单 */
    submitForm() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        if (this.form.libraryId != null) {
          updateLibrary(this.form).then(() => {
            this.$modal.msgSuccess('修改成功')
            this.open = false
            this.getList()
          })
        } else {
          addLibrary(this.form).then(() => {
            this.$modal.msgSuccess('创建成功，字段已同步')
            this.open = false
            this.getList()
          })
        }
      })
    },
    /** 跳转标签管理页 */
    goTagManage(row) {
      this.$router.push({ path: '/taglibrary/tags', query: { libraryId: row.libraryId } })
    },
    goAgentWorkbench(row) {
      this.$router.push(agentWorkbenchLocation({
        libraryId: row.libraryId,
        libraryName: row.libraryName,
        from: '/taglibrary/list'
      }))
    },
    /** 卡片"更多"操作分发 */
    handleMore(cmd, row) {
      if (cmd === 'fields') {
        this.openFieldDrawer(row)
      } else if (cmd === 'dimension') {
        this.$router.push({ path: '/taglibrary/library-dimension/index', query: { libraryId: row.libraryId, libraryName: row.libraryName } })
      } else if (cmd === 'mapping') {
        this.$router.push({ path: '/taglibrary/tag-mapping/index', query: { libraryId: row.libraryId, libraryName: row.libraryName } })
      } else if (cmd === 'edit') {
        this.handleUpdate(row)
      } else if (cmd === 'submit') {
        this.$confirm('提交后将进入审批流，确认提交上线？').then(() => {
          return submitLibrary(row.libraryId)
        }).then(() => {
          this.$modal.msgSuccess('已提交审批')
          this.getList()
        }).catch(() => {})
      } else if (cmd === 'offline') {
        this.$confirm('确认下线该标签库？').then(() => {
          return offlineLibrary(row.libraryId)
        }).then(() => {
          this.$modal.msgSuccess('已下线')
          this.getList()
        }).catch(() => {})
      } else if (cmd === 'audit') {
        this.goAuditPage()
      } else if (cmd === 'remove') {
        this.$confirm('确认删除标签库"' + row.libraryName + '"？', '警告', { type: 'warning' }).then(() => {
          return delLibrary(row.libraryId)
        }).then(() => {
          this.$modal.msgSuccess('删除成功')
          this.getList()
        }).catch(() => {})
      }
    },
    /** 打开字段管理抽屉 */
    openFieldDrawer(row) {
      this.currentLibrary = row
      this.tagQuery.pageNum = 1
      this.tagQuery.libraryId = row.libraryId
      this.drawerVisible = true
      this.loadTagList()
      this.loadDirOptions()
    },
    /** 加载目录选项 */
    loadDirOptions() {
      listDir(this.currentLibrary.libraryId).then(response => {
        this.dirOptions = response.data || response.rows || []
      })
    },
    /** 目录名映射 */
    dirName(dirId) {
      const dir = this.dirOptions.find(d => d.dirId === dirId)
      return dir ? dir.dirName : '-'
    },
    /** 加载标签分页列表 */
    loadTagList() {
      this.tagLoading = true
      listTag(this.tagQuery).then(response => {
        this.tagList = response.rows
        this.tagTotal = response.total
        this.tagLoading = false
      }).catch(() => { this.tagLoading = false })
    },
    /** 同步字段 */
    handleSyncFields() {
      this.$confirm('确认从关联数据集同步字段？已存在的字段不会重复生成。', '提示', { type: 'warning' }).then(() => {
        return syncLibrary(this.currentLibrary.libraryId)
      }).then(response => {
        this.$modal.msgSuccess(response.msg || '同步完成')
        this.loadTagList()
        this.getList()
      }).catch(() => {})
    },
    /** 打开标签编辑弹窗 */
    openTagEdit(row) {
      this.tagForm = {
        tagId: row.tagId,
        libraryId: row.libraryId,
        dirId: row.dirId,
        fieldName: row.fieldName,
        tagName: row.tagName,
        tagType: row.tagType,
        businessCaliber: row.businessCaliber,
        techCaliber: row.techCaliber,
        validPeriod: row.validPeriod,
        updateCycle: row.updateCycle
      }
      this.tagEditVisible = true
      this.$nextTick(() => { if (this.$refs.tagForm) this.$refs.tagForm.clearValidate() })
    },
    /** 提交标签编辑 */
    submitTagForm() {
      this.$refs.tagForm.validate(valid => {
        if (!valid) return
        updateTag(this.tagForm).then(() => {
          this.$modal.msgSuccess('修改成功')
          this.tagEditVisible = false
          this.loadTagList()
        })
      })
    },
    /** 跳转审批管理页 */
    goAuditPage() {
      this.$router.push('/taglibrary/audit')
    }
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.library-card {
  margin-bottom: 16px;
}

.card-line {
  margin-bottom: 8px;
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  font-size: 12px;
  color: #606266;
}

.card-meta-divider {
  margin: 0 6px;
  color: #dcdfe6;
}

.card-stats {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-top: 1px solid #f2f6fc;
  border-bottom: 1px solid #f2f6fc;
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-num {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.card-source {
  font-size: 12px;
  color: #909399;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #ebeef5;
  padding-top: 8px;
  margin-bottom: 0;
}

.drawer-body {
  padding: 0 20px;
}

.drawer-toolbar {
  margin-bottom: 12px;
}
</style>
