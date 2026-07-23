<template>
  <div class="app-container">
    <el-row :gutter="12">
      <!-- 左侧：标签库 + 树 -->
      <el-col :span="6">
        <el-select v-model="currentLibraryId" placeholder="请选择标签库" size="small" style="width: 100%; margin-bottom: 8px;" @change="handleLibraryChange">
          <el-option v-for="lib in libraryOptions" :key="lib.libraryId" :label="lib.libraryName" :value="lib.libraryId" />
        </el-select>
        <el-input v-model="searchText" placeholder="搜索标签/目录" clearable size="small" prefix-icon="el-icon-search" style="margin-bottom: 8px;" />
        <el-tabs v-model="activeTab" @tab-click="loadTree">
          <el-tab-pane label="上线标签" name="online" />
          <el-tab-pane label="下线标签" name="offline" />
        </el-tabs>
        <!-- 树操作按钮区 -->
        <div class="tree-toolbar">
          <el-button type="text" size="mini" icon="el-icon-folder-add" @click="openDirDialog('add')" v-hasPermi="['taglibrary:dir:add']">新建目录</el-button>
          <el-button type="text" size="mini" icon="el-icon-edit" :disabled="!isDirSelected" @click="openDirDialog('edit')" v-hasPermi="['taglibrary:dir:edit']">重命名</el-button>
          <el-button type="text" size="mini" icon="el-icon-delete" :disabled="!isDirSelected" @click="handleDeleteDir" v-hasPermi="['taglibrary:dir:remove']">删除目录</el-button>
          <el-button type="text" size="mini" icon="el-icon-position" :disabled="!isTagSelected" @click="openMoveDialog" v-hasPermi="['taglibrary:tag:move']">移动目录</el-button>
          <el-button v-if="isTagSelected && (selectedNode.status === '0' || selectedNode.status === '3')" type="text" size="mini" icon="el-icon-upload2"
            @click="handleSubmitTag" v-hasPermi="['taglibrary:tag:submit']">提交审批</el-button>
          <el-button v-if="isTagSelected && selectedNode.status === '2'" type="text" size="mini" icon="el-icon-download"
            @click="handleOfflineTag" v-hasPermi="['taglibrary:tag:offline']">下线</el-button>
        </div>
        <el-tree ref="tree" :data="treeData" node-key="id" :props="treeProps" highlight-current v-loading="treeLoading"
          :default-expanded-keys="defaultExpandedKeys" :filter-node-method="filterNode" @node-click="handleNodeClick">
          <span class="custom-tree-node" slot-scope="{ data }">
            <span v-if="data.tagType" class="tag-dot" :style="{background: tagTypeColor(data.tagType)}"></span>
            <span>{{ data.label }}</span>
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
            <el-button style="float: right; padding: 3px 0;" type="text" @click="openTagEdit" v-hasPermi="['taglibrary:tag:edit']">编辑</el-button>
          </div>
          <el-row :gutter="16">
            <el-col :span="16">
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
                <el-descriptions-item label="源数据表">{{ currentLibrary.sourceTable || '/' }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
            <el-col :span="8">
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

    <!-- 移动标签到目录弹窗 -->
    <el-dialog title="移动标签到目录" :visible.sync="moveOpen" width="450px" append-to-body>
      <el-form label-width="80px" size="small">
        <el-form-item label="目标目录">
          <el-select v-model="moveDirId" placeholder="请选择目标目录" style="width: 100%;">
            <el-option v-for="d in dirOptions" :key="d.dirId" :label="d.dirName" :value="d.dirId" />
          </el-select>
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="moveOpen = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitMove">确定</el-button>
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
  </div>
</template>

<script>
import { listLibrary } from '@/api/taglibrary/library'
import { listDir, addDir, updateDir, delDir } from '@/api/taglibrary/dir'
import { tagTree, getTag, updateTag, moveTag, submitTag, offlineTag } from '@/api/taglibrary/tag'

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
      // 移动目录弹窗
      moveOpen: false,
      moveDirId: undefined,
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
      ]
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
      this.searchText = ''
      this.loadTree()
      this.loadDirOptions()
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
    /** 节点点击：标签节点加载详情 */
    handleNodeClick(data) {
      this.selectedNode = data
      if (String(data.id).indexOf('tag-') === 0) {
        this.loadTagDetail(this.parseNodeId(data.id))
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
    /** 打开目录弹窗（add 新建 / edit 重命名） */
    openDirDialog(mode) {
      if (mode === 'add') {
        this.dirTitle = '新建目录'
        this.dirForm = {
          dirId: undefined,
          libraryId: this.currentLibraryId,
          parentId: this.isDirSelected ? Number(this.parseNodeId(this.selectedNode.id)) : 0,
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
    /** 打开移动目录弹窗 */
    openMoveDialog() {
      this.moveDirId = this.tagDetail.dirId || undefined
      this.moveOpen = true
    },
    /** 提交移动 */
    submitMove() {
      if (!this.moveDirId) {
        this.$modal.msgWarning('请选择目标目录')
        return
      }
      const tagId = Number(this.parseNodeId(this.selectedNode.id))
      moveTag({ tagIds: [tagId], dirId: this.moveDirId }).then(() => {
        this.$modal.msgSuccess('移动成功')
        this.moveOpen = false
        this.loadTree()
        this.loadTagDetail(tagId)
      })
    },
    /** 提交审批 */
    handleSubmitTag() {
      const tagId = Number(this.parseNodeId(this.selectedNode.id))
      this.$confirm('提交后将进入审批流，确认提交审批？', '提示', { type: 'warning' }).then(() => {
        return submitTag({ ids: [tagId] })
      }).then(() => {
        this.$modal.msgSuccess('已提交审批')
        this.loadTree()
        this.loadTagDetail(tagId)
      }).catch(() => {})
    },
    /** 下线标签 */
    handleOfflineTag() {
      const tagId = Number(this.parseNodeId(this.selectedNode.id))
      this.$confirm('确认下线标签"' + this.selectedNode.label + '"？', '提示', { type: 'warning' }).then(() => {
        return offlineTag({ ids: [tagId] })
      }).then(() => {
        this.$modal.msgSuccess('已下线')
        this.loadTree()
        this.loadTagDetail(tagId)
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
.tree-toolbar {
  margin-bottom: 8px;
  line-height: 1.6;
}

.custom-tree-node {
  display: flex;
  align-items: center;
}

.tag-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.node-count {
  margin-left: 4px;
  font-size: 12px;
  color: #909399;
}

.legend {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #606266;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  margin-right: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 16px 0 12px;
}

.el-col > .section-title:first-child {
  margin-top: 0;
}
</style>
