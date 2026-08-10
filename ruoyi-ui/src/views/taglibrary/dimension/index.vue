<template>
  <div class="app-container">
    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <div class="toolbar-left">
        <el-button type="primary" size="small" icon="el-icon-check" :loading="saving" @click="handleSave" v-hasPermi="['taglibrary:library:dimension:set']">设置默认</el-button>
        <span class="library-title">标签库：{{ libraryName || '-' }}</span>
      </div>
      <div class="toolbar-right">
        <el-input v-model="queryParams.dimensionName" placeholder="维表名称" clearable size="small" style="width: 180px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
      </div>
    </el-row>

    <el-alert type="info" :closable="false" class="tip-alert">
      <template slot="title">
        已选 {{ selectedDimensionIds.length }} 张维表。与标签库数据源不同源或已停用的维表不可选择。
      </template>
    </el-alert>

    <el-table :data="dimensionList" v-loading="loading" size="small">
      <el-table-column label="选择" width="70" align="center">
        <template #default="scope">
          <el-tooltip v-if="!scope.row.selectable" :content="scope.row.disabledReason || '不可选择'" placement="top">
            <el-checkbox :value="isSelected(scope.row)" disabled />
          </el-tooltip>
          <el-checkbox v-else :value="isSelected(scope.row)" :disabled="!canSet" @change="val => toggleRow(scope.row, val)" />
        </template>
      </el-table-column>
      <el-table-column prop="dimensionName" label="维表名称" min-width="150" show-overflow-tooltip />
      <el-table-column prop="datasourceName" label="数据连接" min-width="120" show-overflow-tooltip />
      <el-table-column prop="sourceTableName" label="表名" min-width="130" show-overflow-tooltip />
      <el-table-column label="当前状态" width="90" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.status === '0' ? 'success' : 'info'" size="mini">{{ scope.row.status === '0' ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createBy" label="创建人" width="100" align="center" />
      <el-table-column prop="createTime" label="创建时间" width="160" align="center" />
    </el-table>

    <pagination v-show="total > 0" :total="total" :page.sync="queryParams.pageNum" :limit.sync="queryParams.pageSize" @pagination="getList" />
  </div>
</template>

<script>
import { dimensionCandidates, selectedDimensions, saveDimensions } from '@/api/taglibrary/dimension'
import { checkPermi } from '@/utils/permission'

export default {
  name: 'LibraryDimension',
  data() {
    return {
      // 遮罩层
      loading: true,
      // 保存中
      saving: false,
      // 总条数
      total: 0,
      // 标签库信息（路由 query 传入）
      libraryId: undefined,
      libraryName: '',
      // 维表候选列表
      dimensionList: [],
      // 跨分页维护的已选维表ID集合
      selectedDimensionIds: [],
      // 查询参数
      queryParams: {
        pageNum: 1,
        pageSize: 10,
        dimensionName: ''
      }
    }
  },
  computed: {
    /** 是否有"设置默认"权限（无权限时全部只读） */
    canSet() {
      return checkPermi(['taglibrary:library:dimension:set'])
    }
  },
  created() {
    this.libraryId = this.$route.query.libraryId
    this.libraryName = this.$route.query.libraryName || ''
    this.init()
  },
  methods: {
    /** 初始化：先取全部已选ID，再加载当前页候选 */
    init() {
      if (!this.libraryId) {
        this.$modal.msgWarning('缺少标签库参数')
        this.loading = false
        return
      }
      selectedDimensions(this.libraryId).then(response => {
        this.selectedDimensionIds = response.data || []
      }).finally(() => {
        this.getList()
      })
    },
    /** 查询维表候选分页列表 */
    getList() {
      this.loading = true
      dimensionCandidates(this.libraryId, this.queryParams).then(response => {
        this.dimensionList = response.rows
        this.total = response.total
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    /** 搜索 */
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
    },
    /** 是否已选 */
    isSelected(row) {
      return this.selectedDimensionIds.indexOf(row.dimensionId) !== -1
    },
    /** 勾选/取消勾选（跨分页维护） */
    toggleRow(row, checked) {
      const idx = this.selectedDimensionIds.indexOf(row.dimensionId)
      if (checked && idx === -1) {
        this.selectedDimensionIds.push(row.dimensionId)
      } else if (!checked && idx !== -1) {
        this.selectedDimensionIds.splice(idx, 1)
      }
    },
    /** 覆盖保存默认维表 */
    handleSave() {
      this.$confirm('将按当前勾选覆盖设置默认码表，未勾选的已关联维表会被清除，确认保存？', '提示', { type: 'warning' }).then(() => {
        this.saving = true
        return saveDimensions(this.libraryId, this.selectedDimensionIds)
      }).then(() => {
        this.$modal.msgSuccess('设置成功')
        this.saving = false
        this.init()
      }).catch(() => {
        this.saving = false
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

.library-title {
  margin-left: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.tip-alert {
  margin-bottom: 12px;
}
</style>
