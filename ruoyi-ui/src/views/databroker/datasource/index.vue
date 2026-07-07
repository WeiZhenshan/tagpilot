<template>
  <div class="app-container datasource-page">
    <div class="datasource-layout">
      <!-- Left: Tree Panel -->
      <aside class="datasource-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">
            <span class="sidebar-title-icon"><i class="el-icon-connection" /></span>
            <div class="sidebar-title-text">
              <span>数据连接</span>
              <small>目录与数据源管理</small>
            </div>
          </div>
        </div>
        <div class="sidebar-search">
          <el-input v-model="filterText" placeholder="输入名称过滤" size="small" clearable prefix-icon="el-icon-search" />
        </div>
        <div class="sidebar-tree" @contextmenu.prevent="onContextMenu($event, null, 'root')">
          <el-tree :data="treeData" :props="treeProps" node-key="id" :filter-node-method="filterNode"
            :expand-on-click-node="false" highlight-current ref="tree" draggable
            :allow-drag="allowDrag" :allow-drop="allowDrop"
            @node-click="handleNodeClick" @node-contextmenu="onNodeContextMenu" @node-drop="handleNodeDrop">
            <span class="custom-tree-node" slot-scope="{ node, data }">
              <span class="drag-handle"><i class="el-icon-rank" /></span>
              <i :class="data.nodeType === 'catalog' ? 'el-icon-folder' : 'el-icon-coin'" />
              <span class="node-label" :title="node.label">{{ node.label }}</span>
            </span>
          </el-tree>
          <!-- Context Menu -->
          <ul v-show="contextMenu.visible" :style="{ left: contextMenu.left + 'px', top: contextMenu.top + 'px' }" class="contextmenu">
            <li v-if="contextMenu.nodeType === 'root'" @click="handleAddCatalog(null)" v-hasPermi="['databroker:catalog:add']">
              <i class="el-icon-folder-add" /> 新增根目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleAddCatalog(contextMenu.node.catalogId)" v-hasPermi="['databroker:catalog:add']">
              <i class="el-icon-folder-add" /> 新增子目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleAddWithCatalog(contextMenu.node.catalogId)" v-hasPermi="['databroker:datasource:add']">
              <i class="el-icon-plus" /> 新增数据源
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleEditCatalogById(contextMenu.node.catalogId)" v-hasPermi="['databroker:catalog:edit']">
              <i class="el-icon-edit" /> 编辑目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleDeleteCatalogById(contextMenu.node.catalogId)" v-hasPermi="['databroker:catalog:remove']">
              <i class="el-icon-delete" /> 删除目录
            </li>
            <li v-if="contextMenu.nodeType === 'datasource'" @click="handleEditDs(contextMenu.node.datasourceId)" v-hasPermi="['databroker:datasource:edit']">
              <i class="el-icon-edit" /> 编辑
            </li>
            <li v-if="contextMenu.nodeType === 'datasource'" @click="handleDeleteDs(contextMenu.node.datasourceId)" v-hasPermi="['databroker:datasource:remove']">
              <i class="el-icon-delete" /> 删除
            </li>
            <li v-if="contextMenu.nodeType === 'datasource'" @click="handleTestDs(contextMenu.node.datasourceId)" v-hasPermi="['databroker:datasource:test']">
              <i class="el-icon-link" /> 测试连接
            </li>
            <li v-if="contextMenu.nodeType === 'datasource'" @click="handleSyncDs(contextMenu.node.datasourceId)" v-hasPermi="['databroker:datasource:sync']">
              <i class="el-icon-refresh" /> 同步元数据
            </li>
          </ul>
        </div>
      </aside>

      <!-- Right: Detail Area -->
      <section class="datasource-content">
        <div v-if="!selectedNode" class="empty-state">
          <i class="el-icon-info" />
          <p>请从左侧选择一个目录或数据源</p>
        </div>

        <!-- 选中目录：目录信息卡片 -->
        <div v-else-if="selectedNode.nodeType === 'catalog'">
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon"><i class="el-icon-folder" /></span>
              <div class="detail-title-main">
                <div class="detail-name">
                  <span>{{ selectedNode.label }}</span>
                  <el-tag type="info" size="mini">目录</el-tag>
                </div>
                <span class="detail-meta">可在此目录下继续创建子目录或数据源</span>
              </div>
            </div>
            <div class="detail-actions">
              <el-button size="mini" type="success" icon="el-icon-folder-add" @click="handleAddCatalog(selectedNode.catalogId)"
                v-hasPermi="['databroker:catalog:add']">新增子目录</el-button>
              <el-button size="mini" type="primary" icon="el-icon-edit" @click="handleEditCatalog"
                v-hasPermi="['databroker:catalog:edit']">编辑目录</el-button>
              <el-button size="mini" type="danger" icon="el-icon-delete" @click="handleDeleteCatalog"
                v-hasPermi="['databroker:catalog:remove']">删除目录</el-button>
            </div>
          </div>
          <div class="catalog-tip">
            <p>提示：在目录下可继续创建子目录或数据源。删除目录前需先移除其下的所有子目录与数据源。</p>
          </div>
        </div>

        <div v-else>
          <!-- Info Bar -->
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon"><i class="el-icon-coin" /></span>
              <div class="detail-title-main">
                <div class="detail-name">
                  <span>{{ datasource.sourceName }}</span>
                  <el-tag v-if="datasource.sourceType" size="mini">{{ datasource.sourceType }}</el-tag>
                </div>
                <span class="detail-meta">
                  创建人：{{ datasource.createBy || '-' }} / 创建时间：{{ datasource.createTime || '-' }} / 使用量：{{ datasource.usageCount || 0 }}
                </span>
              </div>
            </div>
            <div class="detail-actions">
              <el-button size="mini" type="primary" icon="el-icon-edit" @click="handleEdit"
                v-hasPermi="['databroker:datasource:edit']">编辑</el-button>
            </div>
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
              <div class="detail-form-actions">
                <el-button size="small" type="primary" icon="el-icon-link" :loading="testLoading" @click="handleTestFromDetail"
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
      </section>
    </div>

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
        <el-button size="small" type="primary" icon="el-icon-link" :loading="testLoading" @click="handleTestFromDialog">测试连接</el-button>
        <el-button size="small" type="primary" @click="submitForm">保存</el-button>
      </div>
    </el-dialog>

    <!-- Catalog Add/Edit Dialog -->
    <el-dialog :title="catalogDialogTitle" :visible.sync="catalogDialogVisible" width="600px" append-to-body @close="resetCatalogForm">
      <el-form ref="catalogForm" :model="catalogForm" :rules="catalogRules" label-width="100px" size="small">
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="上级目录" prop="parentId">
              <treeselect v-model="catalogForm.parentId" :options="catalogOptions" :normalizer="catalogNormalizer"
                :show-count="true" placeholder="选择上级目录" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="目录名称" prop="catalogName">
              <el-input v-model="catalogForm.catalogName" placeholder="请输入目录名称" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示顺序" prop="orderNum">
              <el-input-number v-model="catalogForm.orderNum" :min="0" controls-position="right" style="width:100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="状态">
              <el-radio-group v-model="catalogForm.status">
                <el-radio label="0">正常</el-radio>
                <el-radio label="1">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="catalogForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="catalogDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitCatalogForm">保存</el-button>
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
import Treeselect from '@riophae/vue-treeselect'
import '@riophae/vue-treeselect/dist/vue-treeselect.css'
import { treeDataSource, getDataSource, addDataSource, updateDataSource, delDataSource,
  testDataSource, syncDataSource, listTables, listColumns, updateTableCnName, listLogs,
  moveDataSource } from '@/api/databroker/datasource'
import { listCatalog, getCatalog, addCatalog, updateCatalog, delCatalog, moveCatalog } from '@/api/databroker/catalog'

export default {
  name: 'DatabrokerDataSource',
  components: { Treeselect },
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
      testLoading: false,
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

      // Catalog dialog
      catalogDialogTitle: '',
      catalogDialogVisible: false,
      catalogOptions: [],
      catalogForm: { catalogId: null, parentId: 0, catalogName: '', orderNum: 0, status: '0', remark: '' },
      catalogRules: {
        catalogName: [{ required: true, message: '请输入目录名称', trigger: 'blur' }]
      },

      // Context menu
      contextMenu: { visible: false, left: 0, top: 0, node: null, nodeType: '' },

      // Columns dialog
      columnsVisible: false,
      columns: []
    }
  },
  watch: {
    filterText(val) { this.$refs.tree.filter(val) },
    'contextMenu.visible'(value) {
      if (value) {
        document.body.addEventListener('click', this.closeContextMenu)
      } else {
        document.body.removeEventListener('click', this.closeContextMenu)
      }
    }
  },
  created() {
    this.loadTree()
  },
  methods: {
    loadTree() {
      // Save expanded keys before reload
      const expandedKeys = []
      const tree = this.$refs.tree
      if (tree && tree.store) {
        tree.store.nodesMap.forEach((node, key) => {
          if (node.expanded) expandedKeys.push(key)
        })
      }

      treeDataSource().then(res => {
        this.treeData = res.data
        this.loadCatalogsFromTree()
        // Restore expanded keys after DOM update
        this.$nextTick(() => {
          if (this.$refs.tree) {
            expandedKeys.forEach(key => {
              const node = this.$refs.tree.getNode(key)
              if (node) node.expand()
            })
          }
        })
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
    /** Treeselect 节点规范化 */
    catalogNormalizer(node) {
      if (node.children && !node.children.length) {
        delete node.children
      }
      return {
        id: node.catalogId,
        label: node.catalogName,
        children: node.children
      }
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

    // ===== Context Menu =====
    onNodeContextMenu(event, data) {
      this.contextMenu = {
        visible: true,
        left: event.clientX,
        top: event.clientY,
        node: data,
        nodeType: data.nodeType
      }
    },
    onContextMenu(event, _data, nodeType) {
      this.contextMenu = {
        visible: true,
        left: event.clientX,
        top: event.clientY,
        node: null,
        nodeType: nodeType
      }
    },
    closeContextMenu() {
      this.contextMenu.visible = false
    },
    handleAddWithCatalog(catalogId) {
      this.closeContextMenu()
      this.dialogTitle = '新增数据源'
      this.resetForm()
      this.form.catalogId = catalogId
      this.dialogVisible = true
    },
    handleEditDs(datasourceId) {
      this.closeContextMenu()
      getDataSource(datasourceId).then(res => {
        const d = res.data
        this.form = {
          datasourceId: d.datasourceId,
          catalogId: d.catalogId,
          sourceName: d.sourceName,
          sourceType: d.sourceType,
          host: d.host,
          port: d.port,
          databaseName: d.databaseName,
          username: d.username,
          password: '******',
          usePool: d.usePool || '0',
          useSsl: d.useSsl || '0',
          jdbcParams: d.jdbcParams || '{}',
          remark: d.remark || ''
        }
        this.dialogTitle = '修改数据源'
        this.dialogVisible = true
      })
    },
    handleDeleteDs(datasourceId) {
      this.closeContextMenu()
      const node = this.contextMenu.node
      this.$modal.confirm('确认删除数据源"' + (node ? node.label : '') + '"？').then(() => {
        return delDataSource(datasourceId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.selectedNode = null
        this.datasource = {}
        this.loadTree()
      }).catch(() => {})
    },
    handleTestDs(datasourceId) {
      this.closeContextMenu()
      this.testLoading = true
      getDataSource(datasourceId).then(res => {
        return testDataSource(res.data)
      }).then(res => {
        this.$modal.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
      }).finally(() => { this.testLoading = false })
    },
    handleSyncDs(datasourceId) {
      this.closeContextMenu()
      this.$confirm('确认同步元数据？', '提示', { type: 'warning' }).then(() => {
        syncDataSource(datasourceId).then(res => {
          const d = res.data
          this.$modal.msgSuccess('同步成功：表' + d.tableCount + '个，视图' + d.viewCount + '个，字段' + d.columnCount + '个')
          if (this.datasource.datasourceId === datasourceId) {
            getDataSource(datasourceId).then(r => { this.datasource = r.data })
            this.loadTableStats()
            this.loadTables()
          }
        })
      }).catch(() => {})
    },
    handleEditCatalogById(catalogId) {
      this.closeContextMenu()
      getCatalog(catalogId).then(res => {
        const d = res.data
        this.catalogDialogTitle = '修改目录'
        this.catalogForm = {
          catalogId: d.catalogId,
          parentId: d.parentId != null ? d.parentId : 0,
          catalogName: d.catalogName,
          orderNum: d.orderNum != null ? d.orderNum : 0,
          status: d.status || '0',
          remark: d.remark || ''
        }
        this.loadCatalogOptionsExclude(catalogId)
        this.catalogDialogVisible = true
      })
    },
    handleDeleteCatalogById(catalogId) {
      this.closeContextMenu()
      const node = this.contextMenu.node
      this.$modal.confirm('确认删除目录"' + (node ? node.label : '') + '"？删除前需确保目录为空。').then(() => {
        return delCatalog(catalogId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.selectedNode = null
        this.loadTree()
      }).catch(() => {})
    },

    // ===== Drag & Drop =====
    allowDrag(node) {
      // All nodes are draggable
      return true
    },
    allowDrop(draggingNode, dropNode, type) {
      const dragData = draggingNode.data
      const dropData = dropNode.data

      // Datasource can only be dropped inside a catalog (inner) or sorted among siblings
      if (dragData.nodeType === 'datasource') {
        if (type === 'inner') {
          // Drop inside a catalog
          return dropData.nodeType === 'catalog'
        }
        // prev/next: only among same-parent datasources
        return dropData.nodeType === 'datasource' && draggingNode.parent.id === dropNode.parent.id
      }

      // Catalog can only be dropped inside another catalog (inner) or sorted among siblings
      if (dragData.nodeType === 'catalog') {
        if (type === 'inner') {
          // Drop inside a catalog
          return dropData.nodeType === 'catalog'
        }
        // prev/next: only among same-parent catalogs
        return dropData.nodeType === 'catalog' && draggingNode.parent.id === dropNode.parent.id
      }

      return false
    },
    handleNodeDrop(draggingNode, dropNode, dropType) {
      const dragData = draggingNode.data
      const dropData = dropNode.data
      const parentNode = dropType === 'inner' ? dropNode : dropNode.parent

      // Compute new order based on drop position
      const siblings = parentNode.childNodes || []
      let newOrder = 0
      if (dropType === 'prev') {
        newOrder = Math.max(0, (dropData.orderNum || 0) - 1)
      } else if (dropType === 'next') {
        newOrder = (dropData.orderNum || 0) + 1
      } else {
        // inner: append to end
        newOrder = siblings.length
      }

      if (dragData.nodeType === 'catalog') {
        const newParentId = (parentNode && parentNode.data && parentNode.data.nodeType === 'catalog')
          ? parentNode.data.catalogId : 0
        moveCatalog({
          catalogId: dragData.catalogId,
          parentId: newParentId,
          orderNum: newOrder
        }).then(() => {
          this.$modal.msgSuccess('排序已更新')
          this.loadTree()
        }).catch(() => {
          this.loadTree() // revert on failure
        })
      } else if (dragData.nodeType === 'datasource') {
        const newCatalogId = (parentNode && parentNode.data && parentNode.data.nodeType === 'catalog')
          ? parentNode.data.catalogId : dragData.catalogId
        moveDataSource(dragData.datasourceId, {
          catalogId: newCatalogId,
          orderNum: newOrder
        }).then(() => {
          this.$modal.msgSuccess('排序已更新')
          this.loadTree()
        }).catch(() => {
          this.loadTree()
        })
      }
    },

    handleAdd() {
      this.dialogTitle = '新增数据源'
      this.resetForm()
      this.dialogVisible = true
    },
    // ===== Catalog =====
    handleAddCatalog(parentId) {
      this.catalogDialogTitle = '新增目录'
      this.resetCatalogForm()
      this.catalogForm.parentId = parentId != null ? parentId : 0
      this.loadCatalogOptionsExclude(null)
      this.catalogDialogVisible = true
    },
    handleEditCatalog() {
      if (!this.selectedNode || this.selectedNode.nodeType !== 'catalog') return
      const catalogId = this.selectedNode.catalogId
      getCatalog(catalogId).then(res => {
        const d = res.data
        this.catalogDialogTitle = '修改目录'
        this.catalogForm = {
          catalogId: d.catalogId,
          parentId: d.parentId != null ? d.parentId : 0,
          catalogName: d.catalogName,
          orderNum: d.orderNum != null ? d.orderNum : 0,
          status: d.status || '0',
          remark: d.remark || ''
        }
        // 排除自身及子孙，防止把自己设为自己的父级
        this.loadCatalogOptionsExclude(catalogId)
        this.catalogDialogVisible = true
      })
    },
    resetCatalogForm() {
      this.catalogForm = { catalogId: null, parentId: 0, catalogName: '', orderNum: 0, status: '0', remark: '' }
      this.$nextTick(() => { if (this.$refs.catalogForm) this.$refs.catalogForm.clearValidate() })
    },
    submitCatalogForm() {
      this.$refs.catalogForm.validate(valid => {
        if (!valid) return
        if (this.catalogForm.catalogId) {
          updateCatalog(this.catalogForm).then(() => {
            this.$modal.msgSuccess('修改成功')
            this.catalogDialogVisible = false
            this.loadTree()
          })
        } else {
          addCatalog(this.catalogForm).then(() => {
            this.$modal.msgSuccess('新增成功')
            this.catalogDialogVisible = false
            this.loadTree()
          })
        }
      })
    },
    handleDeleteCatalog() {
      if (!this.selectedNode || this.selectedNode.nodeType !== 'catalog') return
      const catalogId = this.selectedNode.catalogId
      this.$modal.confirm('确认删除目录"' + this.selectedNode.label + '"？删除前需确保目录为空。').then(() => {
        return delCatalog(catalogId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.selectedNode = null
        this.loadTree()
      }).catch(() => {})
    },
    /** 加载上级目录选项树；excludeId 不为空时排除该节点及其子孙（编辑场景防自引用） */
    loadCatalogOptionsExclude(excludeId) {
      listCatalog().then(res => {
        let list = res.data || []
        if (excludeId != null) {
          // 通过 ancestors 排除自身及子孙
          list = list.filter(d => {
            if (d.catalogId === excludeId) return false
            const anc = (d.ancestors || '').split(',')
            return anc.indexOf(String(excludeId)) === -1
          })
        }
        const tree = this.handleTree(list, 'catalogId')
        this.catalogOptions = [{ catalogId: 0, catalogName: '主目录', children: tree }]
      })
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
          updateDataSource(this.form).then(() => { this.$modal.msgSuccess('修改成功'); this.dialogVisible = false; this.loadTree() })
        } else {
          addDataSource(this.form).then(() => { this.$modal.msgSuccess('新增成功'); this.dialogVisible = false; this.loadTree() })
        }
      })
    },
    handleTestFromDialog() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        this.testLoading = true
        testDataSource(this.form).then(res => {
          this.$modal.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
        }).finally(() => { this.testLoading = false })
      })
    },
    handleTestFromDetail() {
      this.testLoading = true
      testDataSource(this.datasource).then(res => {
        this.$modal.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
      }).finally(() => { this.testLoading = false })
    },
    handleSync() {
      this.$confirm('确认同步元数据？', '提示', { type: 'warning' }).then(() => {
        syncDataSource(this.datasource.datasourceId).then(res => {
          const d = res.data
          this.$modal.msgSuccess('同步成功：表' + d.tableCount + '个，视图' + d.viewCount + '个，字段' + d.columnCount + '个')
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
      if (!row.cnName || row.cnName.length > 60) { this.$modal.msgError('中文名最长60字符'); return }
      updateTableCnName(row.tableId, { cnName: row.cnName }).then(() => { this.$modal.msgSuccess('中文名已更新') })
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
.datasource-page {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 120px);
}

.datasource-layout {
  display: flex;
  align-items: stretch;
  gap: 16px;
  min-height: calc(100vh - 152px);
}

.datasource-sidebar,
.datasource-content {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.datasource-sidebar {
  flex: 0 0 300px;
  min-width: 280px;
  max-width: 340px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 14px 14px 12px;
  border-bottom: 1px solid #ebeef5;
}

.sidebar-title {
  display: flex;
  align-items: center;
  min-width: 0;
}

.sidebar-title-icon {
  width: 34px;
  height: 34px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 6px;
  color: #409eff;
  background: #ecf5ff;
  font-size: 18px;
}

.sidebar-title-text {
  min-width: 0;
  line-height: 1.4;
}

.sidebar-title-text span {
  display: block;
  color: #303133;
  font-size: 15px;
  font-weight: 600;
}

.sidebar-title-text small {
  display: block;
  color: #606266;
  font-size: 12px;
}

.sidebar-search {
  flex-shrink: 0;
  padding: 12px 12px 8px;
}

::v-deep .sidebar-search .el-input__inner::placeholder {
  color: #606266;
}

.sidebar-tree {
  flex: 1;
  min-height: 420px;
  padding: 0 8px 12px;
  overflow: auto;
}

.sidebar-tree::-webkit-scrollbar {
  width: 6px;
}

.sidebar-tree::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 4px;
}

::v-deep .sidebar-tree .el-tree-node__content {
  height: 32px;
  border-radius: 4px;
}

::v-deep .sidebar-tree .el-tree-node__content:hover {
  background: #f0f7ff;
}

::v-deep .sidebar-tree .el-tree-node.is-current > .el-tree-node__content {
  background: #e6f0fd;
  color: #409eff;
  font-weight: 600;
}

.custom-tree-node {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  font-size: 13px;
}

.custom-tree-node .drag-handle {
  margin-right: 4px;
  color: #c0c4cc;
  font-size: 14px;
  cursor: grab;
  flex-shrink: 0;
}

.custom-tree-node .drag-handle:active {
  cursor: grabbing;
}

.custom-tree-node i {
  margin-right: 6px;
  color: #409eff;
  flex-shrink: 0;
}

.node-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.datasource-content {
  flex: 1;
  min-width: 0;
  padding: 16px;
  overflow: auto;
}

.empty-state {
  min-height: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #606266;
  text-align: center;
}

.empty-state i {
  margin-bottom: 14px;
  font-size: 48px;
  color: #c0c4cc;
}

.empty-state p {
  margin: 0;
  font-size: 15px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #f7f9fc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.detail-title {
  display: flex;
  align-items: flex-start;
  min-width: 0;
}

.detail-icon {
  width: 34px;
  height: 34px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 6px;
  color: #409eff;
  background: #ecf5ff;
  font-size: 20px;
}

.detail-title-main {
  min-width: 0;
}

.detail-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
}

.detail-name > span:first-child {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-meta {
  display: block;
  margin-top: 4px;
  color: #606266;
  font-size: 12px;
  line-height: 18px;
  word-break: break-all;
}

.detail-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.detail-actions .el-button + .el-button,
.detail-form-actions .el-button + .el-button {
  margin-left: 0;
}

.catalog-tip {
  margin-top: 16px;
  padding: 12px 14px;
  color: #606266;
  font-size: 13px;
  line-height: 1.8;
  background: #f8fafc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.catalog-tip p {
  margin: 0;
}

.detail-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-right: 20px;
  flex-wrap: wrap;
}

.table-stats {
  padding: 8px 0;
}

/* Context Menu */
.contextmenu {
  margin: 0;
  background: #fff;
  z-index: 3000;
  position: fixed;
  list-style-type: none;
  padding: 5px 0;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 400;
  color: #333;
  box-shadow: 2px 2px 3px 0 rgba(0, 0, 0, .3);
  min-width: 140px;
}

.contextmenu li {
  margin: 0;
  padding: 7px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}

.contextmenu li:hover {
  background: #eee;
}

.contextmenu li i {
  color: #909399;
  width: 14px;
}

@media (max-width: 992px) {
  .datasource-layout {
    flex-direction: column;
    min-height: auto;
  }

  .datasource-sidebar {
    flex: none;
    width: 100%;
    min-width: 0;
    max-width: none;
  }

  .sidebar-tree {
    min-height: 280px;
    max-height: 360px;
  }

  .datasource-content {
    min-height: 480px;
  }
}

@media (max-width: 640px) {
  .datasource-page {
    padding: 10px;
  }

  .detail-header {
    padding: 12px;
    flex-direction: column;
  }

  .detail-title,
  .detail-actions {
    width: 100%;
  }

  .detail-actions,
  .detail-form-actions {
    justify-content: flex-start;
  }

  .detail-form-actions {
    padding-right: 0;
  }
}
</style>
