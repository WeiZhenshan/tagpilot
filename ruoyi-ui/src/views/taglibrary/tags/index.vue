<template>
  <div class="app-container">
    <el-row :gutter="12">
      <!-- 左侧：标签库 + 树 -->
      <el-col :span="6">
        <el-select v-model="currentLibraryId" placeholder="请选择标签库" size="small" style="width: 100%; margin-bottom: 8px;" @change="handleLibraryChange">
          <el-option v-for="lib in libraryOptions" :key="lib.libraryId" :label="lib.libraryName" :value="lib.libraryId" />
        </el-select>
        <el-input v-model="searchText" placeholder="搜索标签/目录" clearable size="small" prefix-icon="el-icon-search" style="margin-bottom: 8px;" />
        <el-tabs v-model="activeTab" @tab-click="handleTabChange">
          <el-tab-pane label="上线标签" name="online" />
          <el-tab-pane label="未上线标签" name="offline" />
        </el-tabs>
        <!-- 树操作按钮区：上线 Tab 批量下线，未上线 Tab 批量提交审批 -->
        <div class="tree-toolbar">
          <el-button v-if="activeTab === 'offline'" type="text" size="mini" icon="el-icon-upload2" :disabled="checkedTagIds.length === 0"
            @click="handleSubmitTags()" v-hasPermi="['taglibrary:tag:submit']">提交审批<span v-if="checkedTagIds.length > 0">（{{ checkedTagIds.length }}）</span></el-button>
          <el-button v-if="activeTab === 'online'" type="text" size="mini" icon="el-icon-download" :disabled="checkedTagIds.length === 0"
            @click="handleOfflineTags()" v-hasPermi="['taglibrary:tag:offline']">下线<span v-if="checkedTagIds.length > 0">（{{ checkedTagIds.length }}）</span></el-button>
        </div>
        <el-tree ref="tree" :data="treeData" node-key="id" :props="treeProps" highlight-current v-loading="treeLoading"
          :default-expanded-keys="defaultExpandedKeys" :filter-node-method="filterNode" @node-click="handleNodeClick"
          @node-contextmenu="handleNodeContextMenu">
          <span class="custom-tree-node" slot-scope="{ data }">
            <el-checkbox v-if="isTagNode(data)" :value="isTagChecked(data)" @change="val => toggleCheck(data, val)" @click.native.stop />
            <span v-if="data.tagType" class="tag-dot" :style="{background: tagTypeColor(data.tagType)}"></span>
            <span>{{ data.label }}</span>
            <span v-if="isTagNode(data) && activeTab === 'offline'" class="tag-status" :class="'tag-status-' + data.status">{{ statusLabel(data.status) }}</span>
            <span v-if="data.count !== undefined" class="node-count">[{{ data.count }}]</span>
          </span>
        </el-tree>
        <el-empty v-if="!treeLoading && treeData.length === 0" description="暂无标签" :image-size="60" />
        <!-- 图例 -->
        <div class="legend">
          <span v-for="item in legendList" :key="item.name" class="legend-item">
            <span class="tag-dot" :style="{background: item.color}"></span>{{ item.name }}
          </span>
        </div>
      </el-col>

      <!-- 右侧：标签详情 -->
      <el-col :span="18">
        <el-card v-if="tagDetail.tagId" shadow="never">
          <div slot="header">标签详情
            <el-tooltip v-if="tagDetail.createWay === '同步'" content="同步标签的名称/类型/目录/口径请通过批量映射维护" placement="top">
              <span style="float: right; padding: 3px 0;">
                <el-button type="text" disabled>编辑</el-button>
              </span>
            </el-tooltip>
            <el-button v-else style="float: right; padding: 3px 0;" type="text" @click="openTagEdit" v-hasPermi="['taglibrary:tag:edit']">编辑</el-button>
          </div>
          <el-row :gutter="16">
            <el-col :span="18">
              <div class="section-title">▎基础信息</div>
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="标签名称">{{ tagDetail.tagName || '/' }}</el-descriptions-item>
                <el-descriptions-item label="数值类型">{{ tagDetail.dataType || '/' }}</el-descriptions-item>
                <el-descriptions-item label="标签类型">
                  <dict-tag :options="dict.type.tag_type" :value="tagDetail.tagType" />
                </el-descriptions-item>
                <el-descriptions-item label="有效日期">{{ tagDetail.validPeriod || '/' }}</el-descriptions-item>
                <el-descriptions-item label="更新周期">
                  <dict-tag :options="dict.type.tag_update_cycle" :value="tagDetail.updateCycle" />
                </el-descriptions-item>
                <el-descriptions-item label="创建方式">{{ tagDetail.createWay || '/' }}</el-descriptions-item>
              </el-descriptions>
              <div class="section-title">▎口径信息</div>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="业务口径">{{ tagDetail.businessCaliber || '/' }}</el-descriptions-item>
                <el-descriptions-item label="技术口径">{{ tagDetail.techCaliber || '/' }}</el-descriptions-item>
              </el-descriptions>
              <div class="section-title">▎技术信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="字段配置">{{ tagDetail.fieldName || '/' }}</el-descriptions-item>
                <el-descriptions-item label="关联数据集">{{ currentLibrary.datasetName || '/' }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
            <el-col :span="6">
              <div class="section-title">▎版本信息</div>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="所属子库">{{ currentLibrary.libraryName || '/' }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ tagDetail.createTime || '/' }}</el-descriptions-item>
                <el-descriptions-item label="创建人">{{ tagDetail.createBy || '/' }}</el-descriptions-item>
                <el-descriptions-item label="版本">V{{ tagDetail.version || 1 }}</el-descriptions-item>
                <el-descriptions-item label="最近修改人">{{ tagDetail.updateBy || '/' }}</el-descriptions-item>
                <el-descriptions-item label="最近修改时间">{{ tagDetail.updateTime || '/' }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
        </el-card>
        <el-empty v-else description="请选择左侧标签" />
      </el-col>
    </el-row>

    <!-- 新建/重命名目录弹窗 -->
    <el-dialog :title="dirTitle" :visible.sync="dirOpen" width="450px" append-to-body>
      <el-form ref="dirForm" :model="dirForm" :rules="dirRules" label-width="80px" size="small">
        <el-form-item label="目录名称" prop="dirName">
          <el-input v-model="dirForm.dirName" placeholder="请输入目录名称" maxlength="64" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="dirOpen = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitDirForm">确定</el-button>
      </div>
    </el-dialog>

    <!-- 编辑标签弹窗 -->
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

    <!-- 树节点右键菜单 -->
    <ul v-show="contextMenuVisible" class="context-menu" :style="{left: contextMenuX + 'px', top: contextMenuY + 'px'}">
      <li v-if="isDirNode(contextMenuNode)" @click="handleContextCommand('add')">新建目录</li>
      <li v-if="isDirNode(contextMenuNode)" @click="handleContextCommand('rename')">重命名</li>
      <li v-if="isDirNode(contextMenuNode)" @click="handleContextCommand('delete')">删除目录</li>
      <li v-if="isTagNode(contextMenuNode) && activeTab === 'offline'" @click="handleContextCommand('submit')">提交审批</li>
      <li v-if="isTagNode(contextMenuNode) && activeTab === 'online'" @click="handleContextCommand('offline')">下线</li>
    </ul>
  </div>
</template>

<script>
import { listLibrary } from '@/api/taglibrary/library'
import { listDir, addDir, updateDir, delDir } from '@/api/taglibrary/dir'
import { tagTree, getTag, updateTag, submitTag, offlineTag } from '@/api/taglibrary/tag'

export default {
  name: 'TagLibraryTags',
  dicts: ['tag_type', 'tag_update_cycle'],
  data() {
    return {
      // 标签库下拉
      libraryOptions: [],
      currentLibraryId: undefined,
      // 树搜索关键字
      searchText: '',
      // 当前页签 online 上线 / offline 下线
      activeTab: 'online',
      // 树数据
      treeData: [],
      treeLoading: false,
      treeProps: { label: 'label', children: 'children' },
      defaultExpandedKeys: [],
      // 当前选中树节点
      selectedNode: null,
      // 已勾选标签节点（多选提交审批）
      checkedTagIds: [],
      // 右键菜单
      contextMenuVisible: false,
      contextMenuX: 0,
      contextMenuY: 0,
      contextMenuNode: null,
      // 标签详情
      tagDetail: {},
      // 目录下拉选项
      dirOptions: [],
      // 目录弹窗
      dirOpen: false,
      dirTitle: '',
      dirForm: {},
      dirRules: {
        dirName: [{ required: true, message: '目录名称不能为空', trigger: 'blur' }]
      },
      // 标签编辑弹窗
      tagEditVisible: false,
      tagForm: {},
      tagRules: {
        tagName: [{ required: true, message: '标签名不能为空', trigger: 'blur' }],
        dirId: [{ required: true, message: '所属目录不能为空', trigger: 'change' }],
        tagType: [{ required: true, message: '标签类型不能为空', trigger: 'change' }]
      },
      // 标签类型颜色图例
      legendList: [
        { name: '选项型', color: '#67C23A' },
        { name: '布尔型', color: '#E6A23C' },
        { name: '数值型', color: '#409EFF' },
        { name: '文本型', color: '#909399' },
        { name: '日期型', color: '#F56C6C' }
      ],
      // 状态文案
      statusMap: {
        '0': '草稿',
        '1': '待审批',
        '2': '已上线',
        '3': '已下线'
      }
    }
  },
  computed: {
    /** 当前标签库对象 */
    currentLibrary() {
      return this.libraryOptions.find(lib => lib.libraryId === this.currentLibraryId) || {}
    },
    /** 是否选中目录节点 */
    isDirSelected() {
      return this.selectedNode && String(this.selectedNode.id).indexOf('dir-') === 0
    },
    /** 是否选中标签节点 */
    isTagSelected() {
      return this.selectedNode && String(this.selectedNode.id).indexOf('tag-') === 0
    }
  },
  watch: {
    searchText(val) {
      this.$refs.tree.filter(val)
    }
  },
  created() {
    this.loadLibraries()
    document.addEventListener('click', this.closeContextMenu)
  },
  beforeDestroy() {
    document.removeEventListener('click', this.closeContextMenu)
  },
  methods: {
    /** 加载标签库下拉，按 query.libraryId 预选，无则默认第一个 */
    loadLibraries() {
      listLibrary({ pageNum: 1, pageSize: 100 }).then(response => {
        this.libraryOptions = response.rows || []
        if (this.libraryOptions.length === 0) {
          return
        }
        const queryId = this.$route.query.libraryId
        const hit = this.libraryOptions.find(lib => String(lib.libraryId) === String(queryId))
        this.currentLibraryId = hit ? hit.libraryId : this.libraryOptions[0].libraryId
        this.loadTree()
        this.loadDirOptions()
      })
    },
    /** 切换标签库 */
    handleLibraryChange() {
      this.selectedNode = null
      this.tagDetail = {}
      this.checkedTagIds = []
      this.searchText = ''
      this.loadTree()
      this.loadDirOptions()
    },
    /** 切换上线/下线 Tab：清空勾选 */
    handleTabChange() {
      this.checkedTagIds = []
      this.loadTree()
    },
    /** 加载标签树 */
    loadTree() {
      if (!this.currentLibraryId) {
        return
      }
      this.treeLoading = true
      tagTree(this.currentLibraryId, this.activeTab).then(response => {
        this.treeData = response.data || []
        this.defaultExpandedKeys = this.treeData.length > 0 ? [this.treeData[0].id] : []
        this.treeLoading = false
      }).catch(() => { this.treeLoading = false })
    },
    /** 加载目录选项 */
    loadDirOptions() {
      if (!this.currentLibraryId) {
        return
      }
      listDir(this.currentLibraryId).then(response => {
        this.dirOptions = response.data || []
      })
    },
    /** 树节点过滤 */
    filterNode(value, data) {
      if (!value) return true
      return data.label.indexOf(value) !== -1
    },
    /** 解析节点 id（tag-1 / dir-2 / lib-3） */
    parseNodeId(id) {
      return String(id).split('-')[1]
    },
    /** 是否标签节点 */
    isTagNode(data) {
      return data && String(data.id).indexOf('tag-') === 0
    },
    /** 是否目录节点 */
    isDirNode(data) {
      return data && String(data.id).indexOf('dir-') === 0
    },
    /** 勾选状态 */
    isTagChecked(data) {
      return this.checkedTagIds.indexOf(data.id) !== -1
    },
    /** 切换勾选（online Tab 仅已上线可勾选；offline Tab 仅草稿/已下线可勾选） */
    toggleCheck(data, val) {
      const tagId = data.id
      if (val) {
        const expectOnline = this.activeTab === 'online'
        if (expectOnline ? data.status !== '2' : (data.status !== '0' && data.status !== '3')) {
          this.$modal.msgWarning(expectOnline ? '仅已上线标签可下线' : '仅草稿或已下线标签可提交审批')
          return
        }
        if (this.checkedTagIds.indexOf(tagId) === -1) {
          this.checkedTagIds.push(tagId)
        }
      } else {
        this.checkedTagIds = this.checkedTagIds.filter(id => id !== tagId)
      }
    },
    /** 节点点击：标签节点加载详情 */
    handleNodeClick(data) {
      this.selectedNode = data
      if (String(data.id).indexOf('tag-') === 0) {
        this.loadTagDetail(this.parseNodeId(data.id))
      }
    },
    /** 节点右键：记录坐标并展示菜单 */
    handleNodeContextMenu(event, data) {
      this.selectedNode = data
      this.contextMenuNode = data
      this.contextMenuX = event.clientX
      this.contextMenuY = event.clientY
      this.contextMenuVisible = true
    },
    /** 关闭右键菜单（点击页面任意处） */
    closeContextMenu() {
      this.contextMenuVisible = false
      this.contextMenuNode = null
    },
    /** 右键菜单命令分发 */
    handleContextCommand(cmd) {
      this.closeContextMenu()
      if (cmd === 'add') {
        this.openDirDialog('add')
      } else if (cmd === 'rename') {
        this.openDirDialog('edit')
      } else if (cmd === 'delete') {
        this.handleDeleteDir()
      } else if (cmd === 'submit') {
        const tagId = Number(this.parseNodeId(this.contextMenuNode.id))
        this.handleSubmitTags([this.contextMenuNode])
      } else if (cmd === 'offline') {
        this.handleOfflineTags([this.contextMenuNode])
      }
    },
    /** 加载标签详情 */
    loadTagDetail(tagId) {
      getTag(tagId).then(response => {
        this.tagDetail = response.data || {}
      })
    },
    /** 标签类型颜色 */
    tagTypeColor(tagType) {
      const item = this.legendList.find(l => l.name === tagType)
      return item ? item.color : '#909399'
    },
    /** 状态文案 */
    statusLabel(status) {
      return this.statusMap[status] || status || '-'
    },
    /** 打开目录弹窗（add 新建 / edit 重命名） */
    openDirDialog(mode) {
      if (mode === 'add') {
        this.dirTitle = '新建目录'
        this.dirForm = {
          dirId: undefined,
          libraryId: this.currentLibraryId,
          parentId: 0,
          dirName: undefined
        }
      } else {
        this.dirTitle = '重命名目录'
        this.dirForm = {
          dirId: Number(this.parseNodeId(this.selectedNode.id)),
          dirName: this.selectedNode.label
        }
      }
      this.dirOpen = true
      this.$nextTick(() => { if (this.$refs.dirForm) this.$refs.dirForm.clearValidate() })
    },
    /** 提交目录表单 */
    submitDirForm() {
      this.$refs.dirForm.validate(valid => {
        if (!valid) return
        const request = this.dirForm.dirId != null ? updateDir(this.dirForm) : addDir(this.dirForm)
        request.then(() => {
          this.$modal.msgSuccess(this.dirForm.dirId != null ? '重命名成功' : '新建成功')
          this.dirOpen = false
          this.loadTree()
          this.loadDirOptions()
        })
      })
    },
    /** 删除目录（目录非空时后端拒绝） */
    handleDeleteDir() {
      this.$confirm('确认删除目录"' + this.selectedNode.label + '"？', '警告', { type: 'warning' }).then(() => {
        return delDir(this.parseNodeId(this.selectedNode.id))
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.selectedNode = null
        this.loadTree()
        this.loadDirOptions()
      }).catch(() => {})
    },
    /** 提交审批（多选：勾选节点；单选：右键菜单传入节点） */
    handleSubmitTags(nodes) {
      const targets = nodes || this.checkedTagIds.map(id => this.findNodeById(id))
      if (targets.length === 0) {
        return
      }
      const ids = targets.map(n => Number(this.parseNodeId(n.id)))
      const names = targets.map(n => n.label).join('、')
      this.$confirm('提交后将进入审批流，确认提交审批"' + names + '"？', '提示', { type: 'warning' }).then(() => {
        return submitTag({ ids: ids })
      }).then(() => {
        this.$modal.msgSuccess('已提交审批')
        this.checkedTagIds = []
        this.loadTree()
        if (this.selectedNode && this.isTagNode(this.selectedNode)) {
          this.loadTagDetail(this.parseNodeId(this.selectedNode.id))
        }
      }).catch(() => {})
    },
    /** 根据树节点 id 查找节点（深度遍历） */
    findNodeById(id) {
      const walk = nodes => {
        for (const n of nodes || []) {
          if (n.id === id) return n
          const found = walk(n.children)
          if (found) return found
        }
        return null
      }
      return walk(this.treeData)
    },
    /** 批量下线（勾选节点或右键菜单传入节点） */
    handleOfflineTags(nodes) {
      const targets = nodes || this.checkedTagIds.map(id => this.findNodeById(id)).filter(Boolean)
      if (targets.length === 0) {
        return
      }
      const ids = targets.map(n => Number(this.parseNodeId(n.id)))
      const names = targets.map(n => n.label).join('、')
      this.$confirm('确认下线标签"' + names + '"？', '提示', { type: 'warning' }).then(() => {
        return offlineTag({ ids: ids })
      }).then(() => {
        this.$modal.msgSuccess('已下线')
        this.checkedTagIds = []
        this.loadTree()
        if (this.selectedNode && this.isTagNode(this.selectedNode)) {
          this.loadTagDetail(this.parseNodeId(this.selectedNode.id))
        }
      }).catch(() => {})
    },
    /** 打开编辑标签弹窗 */
    openTagEdit() {
      this.tagForm = {
        tagId: this.tagDetail.tagId,
        libraryId: this.tagDetail.libraryId,
        dirId: this.tagDetail.dirId,
        fieldName: this.tagDetail.fieldName,
        tagName: this.tagDetail.tagName,
        tagType: this.tagDetail.tagType,
        businessCaliber: this.tagDetail.businessCaliber,
        techCaliber: this.tagDetail.techCaliber,
        validPeriod: this.tagDetail.validPeriod,
        updateCycle: this.tagDetail.updateCycle
      }
      this.tagEditVisible = true
      this.$nextTick(() => { if (this.$refs.tagForm) this.$refs.tagForm.clearValidate() })
    },
    /** 提交标签编辑（版本号由后端 +1） */
    submitTagForm() {
      this.$refs.tagForm.validate(valid => {
        if (!valid) return
        updateTag(this.tagForm).then(() => {
          this.$modal.msgSuccess('修改成功')
          this.tagEditVisible = false
          this.loadTree()
          this.loadTagDetail(this.tagForm.tagId)
        })
      })
    }
  }
}
</script>

<style scoped>
/* 页面容器 */
.app-container {
  padding: 16px 20px;
}

/* 左右面板：统一卡片容器 */
.el-col-6,
.el-col-18 {
  background: #fff;
  border: 1px solid #e6ebf5;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.el-col-6 {
  padding: 14px 12px 12px;
}

.el-col-18 {
  padding: 0;
}

/* 标签库下拉与搜索 */
.el-col-6 .el-select,
.el-col-6 .el-input {
  margin-bottom: 8px;
}

/* Tab 栏 */
.el-col-6 .el-tabs {
  margin-bottom: 6px;
}

.el-col-6 .el-tabs__item {
  height: 36px;
  line-height: 36px;
  font-size: 13px;
}

/* 树工具栏按钮：包成有背景的按钮组 */
.tree-toolbar {
  display: flex;
  gap: 8px;
  margin: 8px 0 10px;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.tree-toolbar .el-button {
  flex: 1;
  padding: 7px 0;
  margin: 0;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
  font-size: 12px;
  border-radius: 4px;
}

.tree-toolbar .el-button:not(.is-disabled):hover {
  color: #409eff;
  border-color: #c6e2ff;
  background: #ecf5ff;
}

.tree-toolbar .el-button.is-disabled {
  color: #c0c4cc;
  border-color: #ebeef5;
  background: #f5f7fa;
}

/* 类型圆点：基础样式（树节点与图例共用） */
.tag-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 7px;
  flex-shrink: 0;
}

/* 树：节点统一行高与内边距，hover 状态 */
.el-tree {
  background: transparent;
}

.el-tree ::v-deep .el-tree-node__content {
  display: flex;
  align-items: center;
  height: 32px;
  padding: 0 8px;
  border-radius: 4px;
  transition: background-color 0.15s;
}

.el-tree ::v-deep .el-tree-node__content:hover {
  background-color: #f5f7fa;
}

.el-tree ::v-deep .el-tree-node.is-current > .el-tree-node__content {
  background-color: #ecf5ff;
  color: #409eff;
}

.el-tree ::v-deep .el-tree-node__expand-icon {
  padding: 4px;
  font-size: 12px;
}

/* 树节点自定义内容：flex 对齐，统一间距 */
.custom-tree-node {
  display: flex;
  align-items: center;
  flex: 1;
  font-size: 13px;
  line-height: 1;
}

.custom-tree-node .el-checkbox {
  margin-right: 8px;
  flex-shrink: 0;
}

.custom-tree-node .el-checkbox__input {
  margin-right: 0;
  line-height: 1;
}

.custom-tree-node .el-checkbox__inner {
  width: 14px;
  height: 14px;
}

.custom-tree-node .el-checkbox__inner::after {
  height: 7px;
  left: 4px;
  top: 1px;
}

.custom-tree-node > span:not(.tag-dot):not(.tag-status):not(.node-count) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.custom-tree-node .tag-status {
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  line-height: 15px;
  border-radius: 8px;
  flex-shrink: 0;
}

.custom-tree-node .node-count {
  margin-left: 4px;
  font-size: 12px;
  color: #909399;
}

/* 图例 */
.legend {
  display: flex;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #606266;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  margin-right: 12px;
  margin-bottom: 4px;
}

/* 右侧详情卡片：去掉默认卡片样式，融入面板 */
.el-card {
  border: none;
  box-shadow: none;
}

.el-card ::v-deep .el-card__header {
  padding: 14px 16px;
  border-bottom: 1px solid #ebeef5;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  background: #fafbfc;
}

.el-card ::v-deep .el-card__header .el-button {
  padding: 0;
  font-size: 13px;
}

.el-card ::v-deep .el-card__body {
  padding: 16px;
}

/* section-title：左侧竖线 + 标题 + 分割线 */
.section-title {
  display: flex;
  align-items: center;
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  line-height: 1;
}

.section-title::before {
  content: '';
  width: 3px;
  height: 14px;
  background: #409eff;
  border-radius: 2px;
  margin-right: 8px;
  flex-shrink: 0;
}

.section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #ebeef5;
  margin-left: 12px;
}

.el-card__body .section-title:first-child {
  margin-top: 0;
}

.el-card ::v-deep .section-title + .el-descriptions {
  margin-bottom: 18px;
}

/* 描述列表 */
.el-card ::v-deep .el-descriptions {
  font-size: 13px;
}

.el-card ::v-deep .el-descriptions-item__label {
  color: #909399;
}

.el-card ::v-deep .el-descriptions-item__content {
  color: #303133;
}

/* 右键菜单 */
.context-menu {
  position: fixed;
  z-index: 3000;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.context-menu li {
  padding: 7px 16px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
}

.context-menu li:hover {
  background: #f5f7fa;
  color: #409eff;
}

/* 状态角标 */
.tag-status-0 {
  background: #909399;
}

.tag-status-1 {
  background: #e6a23c;
}

.tag-status-3 {
  background: #f56c6c;
}
</style>
