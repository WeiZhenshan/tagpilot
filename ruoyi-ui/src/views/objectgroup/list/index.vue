<template>
  <div class="app-container">
    <!-- 工具栏 -->
    <el-row class="toolbar" type="flex" justify="space-between" align="middle">
      <el-button type="primary" icon="el-icon-plus" @click="handleAdd" v-hasPermi="['objectgroup:group:add']">新建对象群</el-button>
      <div class="toolbar-right">
        <el-input v-model="queryParams.groupName" placeholder="按名称模糊搜索" clearable size="small" style="width: 220px;"
          prefix-icon="el-icon-search" @change="handleQuery" @clear="handleQuery" />
      </div>
    </el-row>

    <el-table :data="groupList" v-loading="loading" size="small">
      <el-table-column prop="groupName" label="对象群名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="userCount" label="用户数" width="100" align="center">
        <template #default="scope">{{ scope.row.userCount || 0 }}</template>
      </el-table-column>
      <el-table-column width="110" align="center">
        <template #default="scope">
          <el-button type="text" size="mini" icon="el-icon-refresh" @click="handleRefreshCount(scope.row)"
            v-hasPermi="['objectgroup:group:run']">刷新用户数</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="groupDesc" label="对象群描述" min-width="160" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.groupDesc || '-' }}</template>
      </el-table-column>
      <el-table-column prop="tagNames" label="使用标签" min-width="180" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.tagNames || '-' }}</template>
      </el-table-column>
      <el-table-column prop="createTime" label="创建时间" width="160" align="center" />
      <el-table-column prop="createBy" label="创建人" width="100" align="center" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="scope">
          <el-button type="text" size="mini" icon="el-icon-edit" @click="handleEdit(scope.row)" v-hasPermi="['objectgroup:group:edit']">编辑</el-button>
          <el-button type="text" size="mini" icon="el-icon-delete" @click="handleDelete(scope.row)" v-hasPermi="['objectgroup:group:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" :page-sizes="[10, 20, 30, 40]" :page.sync="queryParams.pageNum"
      :limit.sync="queryParams.pageSize" @pagination="getList" />
  </div>
</template>

<script>
import { listGroup, delGroup, runGroup } from '@/api/objectgroup/group'

export default {
  name: 'ObjectGroupList',
  data() {
    return {
      loading: true,
      total: 0,
      groupList: [],
      queryParams: {
        pageNum: 1,
        pageSize: 10,
        groupName: ''
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      this.loading = true
      listGroup(this.queryParams).then(response => {
        this.groupList = response.rows
        this.total = response.total
        this.loading = false
      }).catch(() => { this.loading = false })
    },
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
    },
    handleAdd() {
      this.$router.push({ path: '/objectgroup/group-edit/index', query: { mode: 'add' } })
    },
    handleEdit(row) {
      this.$router.push({ path: '/objectgroup/group-edit/index', query: { groupId: row.groupId } })
    },
    handleDelete(row) {
      this.$confirm('确认删除对象群"' + row.groupName + '"？', '警告', { type: 'warning' }).then(() => {
        return delGroup(row.groupId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.getList()
      }).catch(() => {})
    },
    handleRefreshCount(row) {
      runGroup({ groupId: row.groupId }).then(response => {
        row.userCount = response.data.count
        const warning = response.data.warning
        if (warning) {
          this.$modal.msgWarning('已刷新，当前用户数 ' + row.userCount + '；' + warning)
        } else {
          this.$modal.msgSuccess('已刷新，当前用户数 ' + row.userCount)
        }
      }).catch(() => {})
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
</style>
