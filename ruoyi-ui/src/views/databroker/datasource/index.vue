<template>
  <div class="app-container">
    <el-row :gutter="16">
      <!-- Left: Tree Panel -->
      <el-col :span="6">
        <div class="tree-panel">
          <div class="tree-header">
            <span><i class="el-icon-connection" /> 数据连接</span>
            <el-button type="primary" size="mini" icon="el-icon-plus" @click="handleAdd"
              v-hasPermi="['databroker:datasource:add']">新增</el-button>
          </div>
          <el-input v-model="filterText" placeholder="输入名称过滤" size="small" clearable style="margin: 8px 0;" />
          <el-tree :data="treeData" :props="treeProps" node-key="id" :filter-node-method="filterNode"
            :expand-on-click-node="false" highlight-current ref="tree" @node-click="handleNodeClick">
            <span class="custom-tree-node" slot-scope="{ node, data }">
              <i :class="data.nodeType === 'catalog' ? 'el-icon-folder' : 'el-icon-coin'" />
              <span>{{ node.label }}</span>
            </span>
          </el-tree>
        </div>
      </el-col>

      <!-- Right: Detail Area -->
      <el-col :span="18">
        <div v-if="!selectedNode || selectedNode.nodeType === 'catalog'" class="empty-state">
          <i class="el-icon-info" style="font-size:48px;color:#c0c4cc;" />
          <p>请从左侧选择一个数据源查看详情</p>
        </div>

        <div v-else>
          <!-- Info Bar -->
          <div class="info-bar">
            <span class="info-bar-icon"><i class="el-icon-coin" /></span>
            <span class="info-bar-title">{{ datasource.sourceName }}</span>
            <el-button size="mini" type="primary" icon="el-icon-edit" @click="handleEdit"
              v-hasPermi="['databroker:datasource:edit']" style="margin-left:12px;">编辑</el-button>
            <el-tag v-if="datasource.sourceType" style="margin-left:8px;">{{ datasource.sourceType }}</el-tag>
            <span style="margin-left:16px;color:#909399;font-size:12px;">
              创建人：{{ datasource.createBy }} | 创建时间：{{ datasource.createTime }} | 使用量：{{ datasource.usageCount || 0 }}
            </span>
          </div>

          <!-- Tabs -->
          <el-tabs v-model="activeTab" style="margin-top:12px;">
            <!-- Basic Info Tab -->
            <el-tab-pane label="基本信息" name="basic">
              <el-form :model="datasource" label-width="120px" size="small" disabled>
                <el-row :gutter="20">
                  <el-col :span="12">
                    <el-form-item label="数据连接名称">{{ datasource.sourceName }}</el-form-item>
                    <el-form-item label="主机">{{ datasource.host }}</el-form-item>
                    <el-form-item label="端口">{{ datasource.port }}</el-form-item>
                    <el-form-item label="数据库名称">{{ datasource.databaseName }}</el-form-item>
                    <el-form-item label="用户名">{{ datasource.username }}</el-form-item>
                    <el-form-item label="密码">******</el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="数据库版本">{{ datasource.dbVersion || '-' }}</el-form-item>
                    <el-form-item label="连接池">{{ datasource.usePool === '1' ? '是' : '否' }}</el-form-item>
                    <el-form-item label="SSL">{{ datasource.useSsl === '1' ? '是' : '否' }}</el-form-item>
                    <el-form-item label="最近同步">
                      {{ datasource.lastSyncTime || '-' }}
                      <el-tag v-if="datasource.lastSyncStatus === '1'" type="success" size="mini">成功</el-tag>
                      <el-tag v-else-if="datasource.lastSyncStatus === '2'" type="danger" size="mini">失败</el-tag>
                      <el-tag v-else type="info" size="mini">未同步</el-tag>
                    </el-form-item>
                    <el-form-item label="备注">{{ datasource.remark || '-' }}</el-form-item>
                  </el-col>
                </el-row>
              </el-form>
              <div style="text-align:right;padding-right:20px;">
                <el-button size="small" type="primary" icon="el-icon-link" @click="handleTestFromDetail"
                  v-hasPermi="['databroker:datasource:test']">测试连接</el-button>
                <el-button size="small" type="success" icon="el-icon-refresh" @click="handleSync"
                  v-hasPermi="['databroker:datasource:sync']">同步元数据</el-button>
              </div>
            </el-tab-pane>

            <!-- Tables Tab -->
            <el-tab-pane label="表信息" name="tables">
              <div class="table-stats">
                <el-tag type="primary">表：{{ tableStats.tableCount }}</el-tag>
                <el-tag type="success" style="margin-left:8px;">视图：{{ tableStats.viewCount }}</el-tag>
              </div>
              <el-form :model="tableQuery" :inline="true" size="small" style="margin-top:10px;">
                <el-form-item label="名称"><el-input v-model="tableQuery.objectName" placeholder="表/视图名称" clearable style="width:180px;" /></el-form-item>
                <el-form-item label="类型">
                  <el-select v-model="tableQuery.objectType" placeholder="全部" clearable style="width:120px;">
                    <el-option label="表" value="TABLE" /><el-option label="视图" value="VIEW" />
                  </el-select>
                </el-form-item>
                <el-form-item><el-button type="primary" icon="el-icon-search" @click="loadTables">查询</el-button></el-form-item>
              </el-form>
              <el-table :data="tableList" v-loading="tableLoading" size="small">
                <el-table-column prop="objectName" label="表/视图名称" min-width="180" />
                <el-table-column prop="objectType" label="类型" width="80">
                  <template slot-scope="scope">{{ scope.row.objectType === 'TABLE' ? '表' : '视图' }}</template>
                </el-table-column>
                <el-table-column prop="cnName" label="中文名" min-width="140">
                  <template slot-scope="scope">
                    <el-input v-model="scope.row.cnName" size="mini" placeholder="输入中文名" maxlength="60"
                      @blur="saveCnName(scope.row)" @keyup.enter.native="saveCnName(scope.row)" />
                  </template>
                </el-table-column>
                <el-table-column prop="columnCount" label="字段数" width="80" />
                <el-table-column prop="usageCount" label="使用量" width="80" />
                <el-table-column label="操作" width="100">
                  <template slot-scope="scope">
                    <el-button type="text" size="mini" @click="showColumns(scope.row)">字段信息</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <pagination v-show="tableTotal > 0" :total="tableTotal" :page.sync="tableQuery.pageNum" :limit.sync="tableQuery.pageSize" @pagination="loadTables" />
            </el-tab-pane>

            <!-- Logs Tab -->
            <el-tab-pane label="操作记录" name="logs">
              <el-form :model="logQuery" :inline="true" size="small">
                <el-form-item label="日志类型">
                  <el-select v-model="logQuery.logType" placeholder="全部" clearable style="width:140px;">
                    <el-option label="新增" value="INSERT" /><el-option label="修改" value="UPDATE" />
                    <el-option label="删除" value="DELETE" /><el-option label="测试连接" value="TEST" />
                    <el-option label="同步" value="SYNC" /><el-option label="中文名" value="CN_NAME" />
                  </el-select>
                </el-form-item>
                <el-form-item label="结果">
                  <el-select v-model="logQuery.result" placeholder="全部" clearable style="width:100px;">
                    <el-option label="成功" value="1" /><el-option label="失败" value="0" />
                  </el-select>
                </el-form-item>
                <el-form-item><el-button type="primary" icon="el-icon-search" @click="loadLogs">查询</el-button></el-form-item>
              </el-form>
              <el-table :data="logList" v-loading="logLoading" size="small">
                <el-table-column prop="operTime" label="日期" width="170" />
                <el-table-column prop="logType" label="日志类型" width="100">
                  <template slot-scope="scope">{{ logTypeMap[scope.row.logType] || scope.row.logType }}</template>
                </el-table-column>
                <el-table-column prop="operatorName" label="操作人" width="100" />
                <el-table-column prop="result" label="结果" width="70">
                  <template slot-scope="scope">
                    <el-tag :type="scope.row.result === '1' ? 'success' : 'danger'" size="mini">
                      {{ scope.row.result === '1' ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="message" label="消息" min-width="200" />
                <el-table-column label="详情" width="70">
                  <template slot-scope="scope">
                    <el-button v-if="scope.row.detailJson" type="text" size="mini" @click="showDetail(scope.row)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <pagination v-show="logTotal > 0" :total="logTotal" :page.sync="logQuery.pageNum" :limit.sync="logQuery.pageSize" @pagination="loadLogs" />
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>
    </el-row>

    <!-- Add/Edit Dialog -->
    <el-dialog :title="dialogTitle" :visible.sync="dialogVisible" width="650px" append-to-body @close="resetForm">
      <el-form ref="form" :model="form" :rules="rules" label-width="120px" size="small">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="目录" prop="catalogId">
              <el-select v-model="form.catalogId" placeholder="选择目录" style="width:100%;">
                <el-option v-for="cat in catalogList" :key="cat.catalogId" :label="cat.catalogName" :value="cat.catalogId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源名称" prop="sourceName">
              <el-input v-model="form.sourceName" placeholder="请输入" maxlength="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="主机" prop="host">
              <el-input v-model="form.host" placeholder="127.0.0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="form.port" :min="1" :max="65535" style="width:100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数据库名称" prop="databaseName">
              <el-input v-model="form.databaseName" placeholder="请输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" show-password placeholder="请输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源类型">
              <el-select v-model="form.sourceType" style="width:100%;">
                <el-option label="MySQL" value="MYSQL" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="连接池"><el-radio-group v-model="form.usePool"><el-radio label="0">否</el-radio><el-radio label="1">是</el-radio></el-radio-group></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="SSL"><el-radio-group v-model="form.useSsl"><el-radio label="0">否</el-radio><el-radio label="1">是</el-radio></el-radio-group></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="dialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" icon="el-icon-link" @click="handleTestFromDialog">测试连接</el-button>
        <el-button size="small" type="primary" @click="submitForm">保存</el-button>
      </div>
    </el-dialog>

    <!-- Columns Dialog -->
    <el-dialog :title="'字段信息：总列数（' + columns.length + '）'" :visible.sync="columnsVisible" width="900px" append-to-body>
      <el-table :data="columns" size="small" max-height="500">
        <el-table-column prop="ordinalPosition" label="序号" width="70" />
        <el-table-column prop="columnName" label="字段名" min-width="160" />
        <el-table-column prop="columnType" label="类型" width="160" />
        <el-table-column prop="columnComment" label="备注" min-width="160" />
        <el-table-column prop="isPk" label="主键" width="60">
          <template slot-scope="scope"><el-tag v-if="scope.row.isPk === '1'" type="danger" size="mini">是</el-tag><span v-else>-</span></template>
        </el-table-column>
        <el-table-column prop="isFk" label="外键" width="60">
          <template slot-scope="scope"><el-tag v-if="scope.row.isFk === '1'" type="warning" size="mini">是</el-tag><span v-else>-</span></template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script>
import { treeDataSource, getDataSource, addDataSource, updateDataSource, delDataSource,
  testDataSource, syncDataSource, listTables, listColumns, updateTableCnName, listLogs } from '@/api/databroker/datasource'

export default {
  name: 'DatabrokerDataSource',
  data() {
    return {
      filterText: '',
      treeData: [],
      treeProps: { children: 'children', label: 'label' },
      selectedNode: null,
      datasource: {},
      activeTab: 'basic',

      // Table
      tableQuery: { pageNum: 1, pageSize: 10, objectName: '', objectType: '' },
      tableList: [],
      tableLoading: false,
      tableTotal: 0,
      tableStats: { tableCount: 0, viewCount: 0 },

      // Logs
      logQuery: { pageNum: 1, pageSize: 10, logType: '', result: '' },
      logList: [],
      logLoading: false,
      logTotal: 0,
      logTypeMap: { INSERT: '新增', UPDATE: '修改', DELETE: '删除', TEST: '测试连接', SYNC: '同步', CN_NAME: '修改中文名' },

      // Dialog
      dialogTitle: '',
      dialogVisible: false,
      form: { catalogId: null, sourceName: '', sourceType: 'MYSQL', host: '', port: 3306, databaseName: '', username: '', password: '', usePool: '0', useSsl: '0', jdbcParams: '{}', remark: '' },
      rules: {
        catalogId: [{ required: true, message: '请选择目录', trigger: 'change' }],
        sourceName: [{ required: true, message: '请输入名称', trigger: 'blur' }],
        host: [{ required: true, message: '请输入主机', trigger: 'blur' }],
        port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
        databaseName: [{ required: true, message: '请输入数据库名称', trigger: 'blur' }],
        username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
        password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
      },
      catalogList: [],

      // Columns dialog
      columnsVisible: false,
      columns: []
    }
  },
  watch: {
    filterText(val) { this.$refs.tree.filter(val) }
  },
  created() {
    this.loadTree()
  },
  methods: {
    loadTree() {
      treeDataSource().then(res => {
        this.treeData = res.data
        this.loadCatalogsFromTree()
      })
    },
    loadCatalogsFromTree() {
      const cats = []
      const walk = (nodes) => {
        nodes.forEach(n => {
          if (n.nodeType === 'catalog') cats.push({ catalogId: n.catalogId, catalogName: n.label })
          if (n.children) walk(n.children)
        })
      }
      walk(this.treeData)
      this.catalogList = cats
    },
    filterNode(value, data) {
      if (!value) return true
      return data.label.indexOf(value) !== -1
    },
    handleNodeClick(data) {
      this.selectedNode = data
      if (data.nodeType === 'datasource') {
        this.activeTab = 'basic'
        getDataSource(data.datasourceId).then(res => {
          this.datasource = res.data
          this.loadTableStats()
          this.loadTables()
          this.loadLogs()
        })
      }
    },
    handleAdd() {
      this.dialogTitle = '新增数据源'
      this.resetForm()
      this.dialogVisible = true
    },
    handleEdit() {
      this.dialogTitle = '修改数据源'
      this.form = {
        datasourceId: this.datasource.datasourceId,
        catalogId: this.datasource.catalogId,
        sourceName: this.datasource.sourceName,
        sourceType: this.datasource.sourceType,
        host: this.datasource.host,
        port: this.datasource.port,
        databaseName: this.datasource.databaseName,
        username: this.datasource.username,
        password: '******',
        usePool: this.datasource.usePool || '0',
        useSsl: this.datasource.useSsl || '0',
        jdbcParams: this.datasource.jdbcParams || '{}',
        remark: this.datasource.remark || ''
      }
      this.dialogVisible = true
    },
    resetForm() {
      this.form = { catalogId: null, sourceName: '', sourceType: 'MYSQL', host: '', port: 3306, databaseName: '', username: '', password: '', usePool: '0', useSsl: '0', jdbcParams: '{}', remark: '' }
      this.$nextTick(() => { if (this.$refs.form) this.$refs.form.clearValidate() })
    },
    submitForm() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        if (this.form.datasourceId) {
          updateDataSource(this.form).then(() => { this.msgSuccess('修改成功'); this.dialogVisible = false; this.loadTree() })
        } else {
          addDataSource(this.form).then(() => { this.msgSuccess('新增成功'); this.dialogVisible = false; this.loadTree() })
        }
      })
    },
    handleTestFromDialog() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        testDataSource(this.form).then(res => {
          this.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
        })
      })
    },
    handleTestFromDetail() {
      const params = { ...this.datasource, password: '******' }
      testDataSource(params).then(res => {
        this.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
      })
    },
    handleSync() {
      this.$confirm('确认同步元数据？', '提示', { type: 'warning' }).then(() => {
        syncDataSource(this.datasource.datasourceId).then(res => {
          const d = res.data
          this.msgSuccess('同步成功：表' + d.tableCount + '个，视图' + d.viewCount + '个，字段' + d.columnCount + '个')
          getDataSource(this.datasource.datasourceId).then(r => { this.datasource = r.data })
          this.loadTableStats()
          this.loadTables()
        })
      })
    },

    // Tables
    loadTableStats() {
      listTables(this.datasource.datasourceId, { pageNum: 1, pageSize: 1 }).then(res => {
        // Count by type from all data
        listTables(this.datasource.datasourceId, { pageNum: 1, pageSize: 999 }).then(r => {
          const all = r.rows || []
          this.tableStats.tableCount = all.filter(t => t.objectType === 'TABLE').length
          this.tableStats.viewCount = all.filter(t => t.objectType === 'VIEW').length
        })
      })
    },
    loadTables() {
      this.tableLoading = true
      listTables(this.datasource.datasourceId, this.tableQuery).then(res => {
        this.tableList = res.rows || []
        this.tableTotal = res.total || 0
        this.tableLoading = false
      }).catch(() => { this.tableLoading = false })
    },
    saveCnName(row) {
      if (!row.cnName || row.cnName.length > 60) { this.msgError('中文名最长60字符'); return }
      updateTableCnName(row.tableId, { cnName: row.cnName }).then(() => { this.msgSuccess('中文名已更新') })
    },
    showColumns(row) {
      listColumns(row.tableId).then(res => {
        this.columns = res.data || []
        this.columnsVisible = true
      })
    },

    // Logs
    loadLogs() {
      this.logLoading = true
      listLogs(this.datasource.datasourceId, this.logQuery).then(res => {
        this.logList = res.rows || []
        this.logTotal = res.total || 0
        this.logLoading = false
      }).catch(() => { this.logLoading = false })
    },
    showDetail(row) {
      let detail = row.detailJson
      try { detail = JSON.stringify(JSON.parse(detail), null, 2) } catch (e) {}
      this.$alert(detail, '操作详情', { confirmButtonText: '关闭', customClass: 'log-detail-dialog' })
    }
  }
}
</script>

<style scoped>
.tree-panel {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  min-height: 500px;
  background: #fff;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
  font-weight: bold;
  font-size: 14px;
}
.tree-header i { margin-right: 4px; color: #409EFF; }
.custom-tree-node { flex: 1; display: flex; align-items: center; font-size: 13px; }
.custom-tree-node i { margin-right: 5px; color: #409EFF; }
.empty-state { text-align: center; padding: 120px 0; color: #909399; }
.info-bar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 8px;
}
.info-bar-icon { font-size: 24px; color: #409EFF; margin-right: 8px; }
.info-bar-title { font-size: 16px; font-weight: 600; }
.table-stats { padding: 8px 0; }
</style>
