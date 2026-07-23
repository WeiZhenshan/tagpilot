<template>
  <div class="app-container dataset-page">
    <div class="dataset-layout">
      <!-- Left: Tree Panel -->
      <aside class="dataset-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">
            <span class="sidebar-title-icon"><i class="el-icon-files" /></span>
            <div class="sidebar-title-text">
              <span>数据集</span>
              <small>目录与数据集管理</small>
            </div>
          </div>
        </div>
        <div class="sidebar-search">
          <el-input v-model="filterText" placeholder="输入名称过滤" size="small" clearable prefix-icon="el-icon-search" />
        </div>
        <div class="tree-guide" :class="{ 'is-dragging': dragState.active }">
          <i :class="dragState.active ? 'el-icon-position' : 'el-icon-info'" />
          <span>{{ dragState.active ? '放到目录中可移动层级，放到节点上下可调整顺序' : '拖动节点可调整层级或同级顺序' }}</span>
        </div>
        <div class="sidebar-tree" :class="{ 'is-dragging': dragState.active }"
          @contextmenu.prevent="onContextMenu($event, null, 'root')">
          <el-tree :data="treeData" :props="treeProps" node-key="id" :filter-node-method="filterNode"
            :expand-on-click-node="false" highlight-current ref="tree" draggable
            :allow-drag="allowDrag" :allow-drop="allowDrop"
            @node-click="handleNodeClick" @node-contextmenu="onNodeContextMenu"
            @node-drag-start="handleNodeDragStart" @node-drag-end="handleNodeDragEnd"
            @node-drop="handleNodeDrop">
            <template #default="{ node, data }">
              <span class="custom-tree-node">
                <span class="drag-handle"><i class="el-icon-sort" /></span>
                <i :class="data.nodeType === 'catalog' ? 'el-icon-folder' : 'el-icon-document'" />
                <span class="node-label" :title="node.label">{{ node.label }}</span>
              </span>
            </template>
          </el-tree>
          <!-- Context Menu -->
          <ul v-show="contextMenu.visible" :style="{ left: contextMenu.left + 'px', top: contextMenu.top + 'px' }" class="contextmenu">
            <li v-if="contextMenu.nodeType === 'root'" @click="handleAddCatalog(null)" v-hasPermi="['databroker:dataset:catalog:add']">
              <i class="el-icon-folder-add" /> 新增根目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleAddCatalog(contextMenu.node.catalogId)" v-hasPermi="['databroker:dataset:catalog:add']">
              <i class="el-icon-folder-add" /> 新增子目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleAddDataset(contextMenu.node.catalogId)" v-hasPermi="['databroker:dataset:add']">
              <i class="el-icon-plus" /> 新增数据集
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleEditCatalogById(contextMenu.node.catalogId)" v-hasPermi="['databroker:dataset:catalog:edit']">
              <i class="el-icon-edit" /> 编辑目录
            </li>
            <li v-if="contextMenu.nodeType === 'catalog'" @click="handleDeleteCatalogById(contextMenu.node.catalogId)" v-hasPermi="['databroker:dataset:catalog:remove']">
              <i class="el-icon-delete" /> 删除目录
            </li>
            <li v-if="contextMenu.nodeType === 'dataset'" @click="handleEditDatasetById(contextMenu.node.datasetId)" v-hasPermi="['databroker:dataset:edit']">
              <i class="el-icon-edit" /> 编辑
            </li>
            <li v-if="contextMenu.nodeType === 'dataset'" @click="handleDeleteDataset(contextMenu.node.datasetId)" v-hasPermi="['databroker:dataset:remove']">
              <i class="el-icon-delete" /> 删除
            </li>
          </ul>
        </div>
      </aside>

      <!-- Right: Detail Area -->
      <section class="dataset-content">
        <div v-if="!selectedNode" class="empty-state">
          <i class="el-icon-info" />
          <p>请从左侧选择一个目录或数据集</p>
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
                <span class="detail-meta">可在此目录下继续创建子目录或数据集</span>
              </div>
            </div>
            <div class="detail-actions">
              <el-button size="mini" type="success" icon="el-icon-folder-add" @click="handleAddCatalog(selectedNode.catalogId)"
                v-hasPermi="['databroker:dataset:catalog:add']">新增子目录</el-button>
              <el-button size="mini" type="primary" icon="el-icon-edit" @click="handleEditCatalog"
                v-hasPermi="['databroker:dataset:catalog:edit']">编辑目录</el-button>
              <el-button size="mini" type="danger" icon="el-icon-delete" @click="handleDeleteCatalog"
                v-hasPermi="['databroker:dataset:catalog:remove']">删除目录</el-button>
            </div>
          </div>
          <div class="catalog-tip">
            <p>提示：在目录下可继续创建子目录或数据集。删除目录前需先移除其下的所有子目录与数据集。</p>
          </div>
        </div>

        <div v-else>
          <!-- Info Bar -->
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon"><i class="el-icon-document" /></span>
              <div class="detail-title-main">
                <div class="detail-name">
                  <span>{{ dataset.datasetName }}</span>
                  <el-tag size="mini" type="info">{{ dataset.datasetCode }}</el-tag>
                  <el-tag v-if="defaultVersionLabel" size="mini" type="success">默认 {{ defaultVersionLabel }}</el-tag>
                  <el-tag :type="dataset.status === '0' ? 'success' : 'danger'" size="mini">
                    {{ dataset.status === '0' ? '正常' : '停用' }}
                  </el-tag>
                </div>
                <span class="detail-meta">
                  数据源：{{ dataset.datasourceName || '-' }} / 负责人：{{ dataset.ownerName || '-' }} / 创建时间：{{ dataset.createTime || '-' }}
                </span>
              </div>
            </div>
            <div class="detail-actions">
              <el-button size="mini" type="danger" icon="el-icon-delete" @click="handleDeleteDataset(dataset.datasetId)"
                v-hasPermi="['databroker:dataset:remove']">删除</el-button>
            </div>
          </div>

          <!-- Tabs -->
          <el-tabs v-model="activeTab" style="margin-top:12px;">
            <!-- 基本信息 Tab -->
            <el-tab-pane label="基本信息" name="basic">
              <el-form ref="basicForm" :model="basicForm" :rules="basicRules" label-width="120px" size="small">
                <el-row :gutter="20">
                  <el-col :span="12">
                    <el-form-item label="数据集编码">
                      <el-input v-model="basicForm.datasetCode" disabled />
                    </el-form-item>
                    <el-form-item label="数据集名称" prop="datasetName">
                      <el-input v-model="basicForm.datasetName" placeholder="请输入" maxlength="100" />
                    </el-form-item>
                    <el-form-item label="负责人">
                      <el-input v-model="basicForm.ownerName" placeholder="请输入" maxlength="50" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="目录" prop="catalogId">
                      <el-select v-model="basicForm.catalogId" placeholder="选择目录" style="width:100%;">
                        <el-option v-for="cat in catalogList" :key="cat.catalogId" :label="cat.catalogName" :value="cat.catalogId" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="数据源">
                      <el-input :value="dataset.datasourceName" disabled />
                    </el-form-item>
                    <el-form-item label="状态">
                      <el-radio-group v-model="basicForm.status">
                        <el-radio label="0">正常</el-radio>
                        <el-radio label="1">停用</el-radio>
                      </el-radio-group>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="备注">
                  <el-input v-model="basicForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
                </el-form-item>
              </el-form>
              <div class="detail-form-actions">
                <el-button size="small" type="primary" icon="el-icon-check" :loading="basicSaving" @click="submitBasicForm"
                  v-hasPermi="['databroker:dataset:edit']">保存</el-button>
              </div>
            </el-tab-pane>

            <!-- 字段定义 Tab -->
            <el-tab-pane label="字段定义" name="fields">
              <el-form :inline="true" size="small">
                <el-form-item label="版本">
                  <el-select v-model="fieldVersionId" placeholder="选择版本" style="width:240px;" @change="handleFieldVersionChange">
                    <el-option v-for="v in versionList" :key="v.versionId"
                      :label="'V' + v.versionNo + ' ' + (v.versionName || '') + '（' + versionStatusText(v.versionStatus) + '）'"
                      :value="v.versionId" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="isDraftVersion" label="版本名称">
                  <el-input v-model="fieldVersionName" placeholder="草稿版本名称" maxlength="100" style="width:200px;" />
                </el-form-item>
              </el-form>
              <el-alert v-if="currentVersion && !isDraftVersion" type="warning" :closable="false" show-icon
                :title="'当前版本为' + versionStatusText(currentVersion.versionStatus) + '状态，字段定义只读；如需修改请复制为新版本'" style="margin-bottom:10px;" />
              <el-empty v-if="!currentVersion" description="暂无版本，请先在版本管理中创建" :image-size="80" />
              <template v-else>
                <el-form :inline="true" size="small">
                  <el-form-item label="宽表">
                    <el-select v-model="fieldTableId" placeholder="搜索并选择宽表" style="width:320px;"
                      filterable remote clearable :remote-method="searchTables" :loading="tableSearchLoading"
                      :disabled="!isDraftVersion" @change="handleTableChange">
                      <el-option v-for="t in tableOptions" :key="t.tableId"
                        :label="t.objectName + (t.cnName ? '（' + t.cnName + '）' : '')" :value="t.tableId" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="关键字">
                    <el-input v-model="fieldKeyword" placeholder="过滤字段名/注释" clearable style="width:200px;" />
                  </el-form-item>
                </el-form>
                <el-table :data="filteredFieldRows" v-loading="fieldLoading" size="small" max-height="480" row-key="columnId">
                  <el-table-column width="50" align="center">
                    <template #header>
                      <el-checkbox :value="isAllFilteredChecked" :indeterminate="isFilteredIndeterminate"
                        :disabled="!isDraftVersion" @change="toggleCheckAll" />
                    </template>
                    <template #default="scope">
                      <el-checkbox v-model="scope.row.checked" :disabled="!isDraftVersion" />
                    </template>
                  </el-table-column>
                  <el-table-column label="顺序" width="60" align="center">
                    <template #default="scope">
                      <span v-if="scope.row.checked">{{ checkedOrder(scope.row) }}</span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="columnName" label="字段名" min-width="160" show-overflow-tooltip />
                  <el-table-column prop="columnType" label="类型" width="140" show-overflow-tooltip />
                  <el-table-column prop="columnComment" label="注释" min-width="140" show-overflow-tooltip>
                    <template #default="scope">{{ scope.row.columnComment || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="别名" min-width="150">
                    <template #default="scope">
                      <el-input v-model="scope.row.alias" size="mini" placeholder="输出列名" maxlength="60" :disabled="!isDraftVersion" />
                    </template>
                  </el-table-column>
                  <el-table-column label="启用" width="70" align="center">
                    <template #default="scope">
                      <el-switch v-model="scope.row.enabled" :disabled="!isDraftVersion || !scope.row.checked" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="110" align="center">
                    <template #default="scope">
                      <el-button type="text" size="mini" icon="el-icon-top" :disabled="!isDraftVersion"
                        @click="moveField(scope.$index, -1)">上移</el-button>
                      <el-button type="text" size="mini" icon="el-icon-bottom" :disabled="!isDraftVersion"
                        @click="moveField(scope.$index, 1)">下移</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-if="saveResult.healthStatus" style="margin-top:10px;">
                  <el-alert :type="saveResult.healthStatus === 'VALID' ? 'success' : 'error'" :closable="false" show-icon>
                    <template #title>
                      校验结果：<el-tag :type="saveResult.healthStatus === 'VALID' ? 'success' : 'danger'" size="mini">
                        {{ saveResult.healthStatus === 'VALID' ? 'VALID' : 'INVALID' }}
                      </el-tag>
                      <span v-if="saveResult.validationMessage" style="margin-left:8px;">{{ saveResult.validationMessage }}</span>
                    </template>
                  </el-alert>
                </div>
                <div class="detail-form-actions" style="margin-top:12px;">
                  <el-button v-if="isDraftVersion" size="small" type="primary" icon="el-icon-check" :loading="fieldSaving"
                    @click="handleSaveDraft" v-hasPermi="['databroker:dataset:edit']">保存草稿</el-button>
                </div>
              </template>
            </el-tab-pane>

            <!-- 版本管理 Tab -->
            <el-tab-pane label="版本管理" name="versions">
              <el-table :data="versionList" v-loading="versionLoading" size="small">
                <el-table-column label="版本号" width="90" align="center">
                  <template #default="scope">
                    V{{ scope.row.versionNo }}
                    <el-tag v-if="scope.row.isDefault === '1' || scope.row.isDefault === true" type="success" size="mini">默认</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="versionName" label="版本名称" min-width="140" show-overflow-tooltip>
                  <template #default="scope">{{ scope.row.versionName || '-' }}</template>
                </el-table-column>
                <el-table-column label="状态" width="90" align="center">
                  <template #default="scope">
                    <el-tag :type="versionStatusTagType(scope.row.versionStatus)" size="mini">
                      {{ versionStatusText(scope.row.versionStatus) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="健康" width="90" align="center">
                  <template #default="scope">
                    <el-tag v-if="scope.row.healthStatus" :type="scope.row.healthStatus === 'VALID' ? 'success' : 'danger'" size="mini">
                      {{ scope.row.healthStatus }}
                    </el-tag>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="publishBy" label="发布人" width="100">
                  <template #default="scope">{{ scope.row.publishBy || '-' }}</template>
                </el-table-column>
                <el-table-column prop="publishTime" label="发布时间" width="160">
                  <template #default="scope">{{ scope.row.publishTime || '-' }}</template>
                </el-table-column>
                <el-table-column prop="releaseNote" label="发布说明" min-width="160" show-overflow-tooltip>
                  <template #default="scope">{{ scope.row.releaseNote || '-' }}</template>
                </el-table-column>
                <el-table-column label="操作" width="250" align="center" fixed="right">
                  <template #default="scope">
                    <el-button type="text" size="mini" icon="el-icon-view" @click="handleViewVersion(scope.row)"
                      v-hasPermi="['databroker:dataset:query']">查看</el-button>
                    <el-button type="text" size="mini" icon="el-icon-document-copy" @click="handleCopyVersion(scope.row)"
                      v-hasPermi="['databroker:dataset:edit']">复制为新版本</el-button>
                    <el-button v-if="scope.row.versionStatus === 'DRAFT'" type="text" size="mini" icon="el-icon-s-promotion"
                      @click="handleOpenPublish(scope.row)" v-hasPermi="['databroker:dataset:publish']">发布</el-button>
                    <el-button v-if="scope.row.versionStatus === 'ONLINE'" type="text" size="mini" icon="el-icon-remove-outline"
                      @click="handleOfflineVersion(scope.row)" v-hasPermi="['databroker:dataset:offline']">下线</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 数据预览 Tab -->
            <el-tab-pane label="数据预览" name="preview">
              <el-form :inline="true" size="small">
                <el-form-item label="版本">
                  <el-select v-model="previewVersionId" placeholder="选择版本" style="width:260px;">
                    <el-option v-for="v in versionList" :key="v.versionId"
                      :label="'V' + v.versionNo + ' ' + (v.versionName || '') + '（' + versionStatusText(v.versionStatus) + '）'"
                      :value="v.versionId" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" icon="el-icon-video-play" :loading="previewLoading" :disabled="!previewVersionId"
                    @click="handlePreview" v-hasPermi="['databroker:dataset:preview']">执行预览</el-button>
                </el-form-item>
              </el-form>
              <el-empty v-if="!versionList.length" description="暂无版本，请先在字段定义中保存并发布" :image-size="80" />
              <template v-else>
                <div v-if="previewRan" style="margin-bottom:8px;color:#606266;font-size:12px;">
                  预览最多返回 100 行，共 {{ previewRows.length }} 行
                </div>
                <el-table v-if="previewRan" :data="previewRows" v-loading="previewLoading" size="small" border max-height="480">
                  <el-table-column v-for="col in previewColumns" :key="col.name" :prop="col.name"
                    :label="col.name + (col.dataType ? '（' + col.dataType + '）' : '')" min-width="140" show-overflow-tooltip>
                    <template #default="scope">{{ scope.row[col.name] }}</template>
                  </el-table-column>
                </el-table>
                <el-empty v-else description="选择版本后点击执行预览" :image-size="80" />
              </template>
            </el-tab-pane>

            <!-- 操作记录 Tab -->
            <el-tab-pane label="操作记录" name="logs">
              <el-form :model="logQuery" :inline="true" size="small">
                <el-form-item label="操作类型">
                  <el-select v-model="logQuery.operType" placeholder="全部" clearable style="width:140px;">
                    <el-option label="新增" value="INSERT" /><el-option label="修改" value="UPDATE" />
                    <el-option label="删除" value="DELETE" /><el-option label="保存草稿" value="SAVE_DRAFT" />
                    <el-option label="发布" value="PUBLISH" /><el-option label="下线" value="OFFLINE" />
                    <el-option label="预览" value="PREVIEW" /><el-option label="复制版本" value="COPY" />
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
                <el-table-column prop="operType" label="操作类型" width="100">
                  <template #default="scope">{{ operTypeMap[scope.row.operType] || scope.row.operType }}</template>
                </el-table-column>
                <el-table-column prop="operatorName" label="操作人" width="100" />
                <el-table-column prop="result" label="结果" width="70">
                  <template #default="scope">
                    <el-tag :type="scope.row.result === '1' ? 'success' : 'danger'" size="mini">
                      {{ scope.row.result === '1' ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
                <el-table-column label="详情" width="70">
                  <template #default="scope">
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

    <!-- Add Dataset Dialog -->
    <el-dialog :title="datasetDialogTitle" :visible.sync="datasetDialogVisible" width="600px" append-to-body @close="resetDatasetForm">
      <el-form ref="datasetForm" :model="datasetForm" :rules="datasetRules" label-width="100px" size="small">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="目录" prop="catalogId">
              <el-select v-model="datasetForm.catalogId" placeholder="选择目录" style="width:100%;">
                <el-option v-for="cat in catalogList" :key="cat.catalogId" :label="cat.catalogName" :value="cat.catalogId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据集编码" prop="datasetCode">
              <el-input v-model="datasetForm.datasetCode" placeholder="请输入编码" maxlength="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数据集名称" prop="datasetName">
              <el-input v-model="datasetForm.datasetName" placeholder="请输入名称" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源" prop="datasourceId">
              <el-select v-model="datasetForm.datasourceId" placeholder="选择数据源（创建后不可改）" style="width:100%;" filterable>
                <el-option v-for="ds in datasourceOptions" :key="ds.datasourceId" :label="ds.sourceName" :value="ds.datasourceId" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="datasetForm.ownerName" placeholder="请输入" maxlength="50" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="datasetForm.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="datasetDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitDatasetForm">保存</el-button>
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

    <!-- Publish Dialog -->
    <el-dialog title="发布版本" :visible.sync="publishDialogVisible" width="500px" append-to-body @close="resetPublishForm">
      <el-form ref="publishForm" :model="publishForm" label-width="100px" size="small">
        <el-form-item label="版本">
          <span>V{{ publishForm.versionNo }}（草稿）</span>
        </el-form-item>
        <el-form-item label="版本名称">
          <el-input v-model="publishForm.versionName" placeholder="请输入版本名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="发布说明">
          <el-input v-model="publishForm.releaseNote" type="textarea" :rows="3" placeholder="请输入发布说明" maxlength="500" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-checkbox v-model="publishForm.setDefault">发布后设为默认版本</el-checkbox>
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="publishDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="publishLoading" @click="submitPublish">发布</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import Treeselect from '@riophae/vue-treeselect'
import '@riophae/vue-treeselect/dist/vue-treeselect.css'
import hasPermi from '@/directive/permission/hasPermi'
import { treeDataset, getDataset, addDataset, updateDataset, delDataset, moveDataset,
  listVersions, getVersion, saveVersion, copyVersion, publishVersion, offlineVersion,
  previewDataset, listLogs, listTables, listColumns,
  listCatalog, getCatalog, addCatalog, updateCatalog, delCatalog, moveCatalog } from '@/api/databroker/dataset'
import { treeDataSource } from '@/api/databroker/datasource'

export default {
  name: 'DatabrokerDataset',
  components: { Treeselect },
  directives: { hasPermi },
  data() {
    return {
      filterText: '',
      treeData: [],
      treeProps: { children: 'children', label: 'label' },
      selectedNode: null,
      dataset: {},
      activeTab: 'basic',

      // Basic info form
      basicForm: { datasetId: null, datasetCode: '', datasetName: '', ownerName: '', catalogId: null, status: '0', remark: '' },
      basicRules: {
        datasetName: [{ required: true, message: '请输入数据集名称', trigger: 'blur' }],
        catalogId: [{ required: true, message: '请选择目录', trigger: 'change' }]
      },
      basicSaving: false,
      catalogList: [],

      // Versions
      versionList: [],
      versionLoading: false,

      // Fields tab
      fieldVersionId: null,
      fieldVersionName: '',
      fieldTableId: null,
      tableOptions: [],
      tableSearchLoading: false,
      fieldKeyword: '',
      fieldRows: [],
      fieldLoading: false,
      fieldSaving: false,
      saveResult: { healthStatus: '', validationMessage: '' },

      // Preview tab
      previewVersionId: null,
      previewLoading: false,
      previewRan: false,
      previewColumns: [],
      previewRows: [],

      // Logs
      logQuery: { pageNum: 1, pageSize: 10, operType: '', result: '' },
      logList: [],
      logLoading: false,
      logTotal: 0,
      operTypeMap: { INSERT: '新增', UPDATE: '修改', DELETE: '删除', SAVE_DRAFT: '保存草稿', PUBLISH: '发布', OFFLINE: '下线', PREVIEW: '预览', COPY: '复制版本' },

      // Dataset add dialog
      datasetDialogTitle: '',
      datasetDialogVisible: false,
      datasetForm: { catalogId: null, datasetCode: '', datasetName: '', datasourceId: null, ownerName: '', remark: '' },
      datasetRules: {
        catalogId: [{ required: true, message: '请选择目录', trigger: 'change' }],
        datasetCode: [{ required: true, message: '请输入数据集编码', trigger: 'blur' }],
        datasetName: [{ required: true, message: '请输入数据集名称', trigger: 'blur' }],
        datasourceId: [{ required: true, message: '请选择数据源', trigger: 'change' }]
      },
      datasourceOptions: [],

      // Catalog dialog
      catalogDialogTitle: '',
      catalogDialogVisible: false,
      catalogOptions: [],
      catalogForm: { catalogId: null, parentId: 0, catalogName: '', orderNum: 0, status: '0', remark: '' },
      catalogRules: {
        catalogName: [{ required: true, message: '请输入目录名称', trigger: 'blur' }]
      },

      // Publish dialog
      publishDialogVisible: false,
      publishLoading: false,
      publishForm: { versionId: null, versionNo: null, versionName: '', releaseNote: '', setDefault: false },

      // Context menu
      contextMenu: { visible: false, left: 0, top: 0, node: null, nodeType: '' },
      dragState: { active: false }
    }
  },
  computed: {
    currentVersion() {
      return this.versionList.find(v => v.versionId === this.fieldVersionId) || null
    },
    isDraftVersion() {
      return this.currentVersion != null && this.currentVersion.versionStatus === 'DRAFT'
    },
    filteredFieldRows() {
      const kw = (this.fieldKeyword || '').trim().toLowerCase()
      if (!kw) return this.fieldRows
      return this.fieldRows.filter(r =>
        (r.columnName || '').toLowerCase().indexOf(kw) !== -1 ||
        (r.columnComment || '').toLowerCase().indexOf(kw) !== -1)
    },
    isAllFilteredChecked() {
      const rows = this.filteredFieldRows
      return rows.length > 0 && rows.every(r => r.checked)
    },
    isFilteredIndeterminate() {
      const rows = this.filteredFieldRows
      const checked = rows.filter(r => r.checked).length
      return checked > 0 && checked < rows.length
    },
    defaultVersionLabel() {
      const v = this.versionList.find(x => x.isDefault === '1' || x.isDefault === true)
      if (v) return 'V' + v.versionNo
      if (this.dataset.defaultVersionId) {
        const d = this.versionList.find(x => x.versionId === this.dataset.defaultVersionId)
        return d ? 'V' + d.versionNo : ''
      }
      return ''
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
    this.loadDatasourceOptions()
  },
  methods: {
    loadTree() {
      // Save expanded keys before reload
      const expandedKeys = []
      const tree = this.$refs.tree
      const currentKey = tree ? tree.getCurrentKey() : null
      if (tree && tree.store) {
        Object.keys(tree.store.nodesMap || {}).forEach(key => {
          const node = tree.store.nodesMap[key]
          if (node.expanded) expandedKeys.push(key)
        })
      }

      return treeDataset().then(res => {
        this.treeData = res.data
        this.loadCatalogsFromTree()
        // Restore expanded keys after DOM update
        this.$nextTick(() => {
          if (this.$refs.tree) {
            expandedKeys.forEach(key => {
              const node = this.$refs.tree.getNode(key)
              if (node) node.expand()
            })
            if (currentKey) this.$refs.tree.setCurrentKey(currentKey)
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
    /** 数据源下拉选项：取数据源管理树中的数据源叶子节点 */
    loadDatasourceOptions() {
      treeDataSource().then(res => {
        const list = []
        const walk = (nodes) => {
          (nodes || []).forEach(n => {
            if (n.nodeType === 'datasource') list.push({ datasourceId: n.datasourceId, sourceName: n.label })
            if (n.children) walk(n.children)
          })
        }
        walk(res.data || [])
        this.datasourceOptions = list
      })
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
      if (data.nodeType === 'dataset') {
        this.loadDataset(data.datasetId)
      }
    },
    loadDataset(datasetId) {
      getDataset(datasetId).then(res => {
        const d = res.data
        this.dataset = d
        this.basicForm = {
          datasetId: d.datasetId,
          datasetCode: d.datasetCode,
          datasetName: d.datasetName,
          ownerName: d.ownerName || '',
          catalogId: d.catalogId,
          status: d.status || '0',
          remark: d.remark || ''
        }
        this.$nextTick(() => { if (this.$refs.basicForm) this.$refs.basicForm.clearValidate() })
        this.resetFieldState()
        this.resetPreviewState()
        this.loadLogs()
        this.loadVersions()
      })
    },
    resetFieldState() {
      this.fieldVersionId = null
      this.fieldVersionName = ''
      this.fieldTableId = null
      this.tableOptions = []
      this.fieldKeyword = ''
      this.fieldRows = []
      this.saveResult = { healthStatus: '', validationMessage: '' }
    },
    resetPreviewState() {
      this.previewVersionId = null
      this.previewRan = false
      this.previewColumns = []
      this.previewRows = []
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
    handleAddDataset(catalogId) {
      this.closeContextMenu()
      this.datasetDialogTitle = '新增数据集'
      this.resetDatasetForm()
      this.datasetForm.catalogId = catalogId
      this.datasetDialogVisible = true
    },
    handleEditDatasetById(datasetId) {
      this.closeContextMenu()
      const node = this.findTreeNode(n => n.nodeType === 'dataset' && n.datasetId === datasetId)
      if (node) {
        this.selectedNode = node
        if (this.$refs.tree) this.$refs.tree.setCurrentKey(node.id)
        this.activeTab = 'basic'
        this.loadDataset(datasetId)
      }
    },
    handleDeleteDataset(datasetId) {
      this.closeContextMenu()
      const node = this.contextMenu.node || this.selectedNode
      this.$modal.confirm('确认删除数据集"' + (node ? node.label : this.dataset.datasetName) + '"？').then(() => {
        return delDataset(datasetId)
      }).then(() => {
        this.$modal.msgSuccess('删除成功')
        this.selectedNode = null
        this.dataset = {}
        this.loadTree()
      }).catch(() => {})
    },
    findTreeNode(predicate) {
      let found = null
      const walk = (nodes) => {
        (nodes || []).forEach(n => {
          if (found) return
          if (predicate(n)) { found = n; return }
          if (n.children) walk(n.children)
        })
      }
      walk(this.treeData)
      return found
    },

    // ===== Drag & Drop =====
    allowDrag() {
      // All nodes are draggable
      return true
    },
    allowDrop(draggingNode, dropNode, type) {
      const dragData = draggingNode.data
      const dropData = dropNode.data

      // Dataset can only be dropped inside a catalog (inner) or sorted among siblings
      if (dragData.nodeType === 'dataset') {
        if (type === 'inner') {
          return dropData.nodeType === 'catalog'
        }
        return dropData.nodeType === 'dataset' && draggingNode.parent.id === dropNode.parent.id
      }

      // Catalog can only be dropped inside another catalog (inner) or sorted among siblings
      if (dragData.nodeType === 'catalog') {
        if (type === 'inner') {
          return dropData.nodeType === 'catalog'
        }
        return dropData.nodeType === 'catalog' && draggingNode.parent.id === dropNode.parent.id
      }

      return false
    },
    handleNodeDragStart() {
      this.dragState.active = true
      this.closeContextMenu()
    },
    handleNodeDragEnd() {
      this.dragState.active = false
    },
    handleNodeDrop(draggingNode, dropNode, dropType) {
      const dragData = draggingNode.data
      const parentNode = dropType === 'inner' ? dropNode : dropNode.parent
      const siblings = (parentNode.childNodes || []).filter(node => node.data.nodeType === dragData.nodeType)
      const parentCatalogId = parentNode.data && parentNode.data.nodeType === 'catalog'
        ? parentNode.data.catalogId : 0
      const requests = siblings.map((node, index) => {
        const orderNum = (index + 1) * 10
        if (node.data.nodeType === 'catalog') {
          return moveCatalog({ catalogId: node.data.catalogId, parentId: parentCatalogId, orderNum })
        }
        return moveDataset(node.data.datasetId, { catalogId: parentCatalogId, orderNum })
      })

      Promise.all(requests).then(() => {
        if (dropType === 'inner') parentNode.expand()
        this.$refs.tree.setCurrentKey(dragData.id)
        this.$modal.msgSuccess(dropType === 'inner' ? '已移动到目标目录' : '顺序已更新')
        this.loadTree()
      }, () => {
        this.$modal.msgError('调整失败，已恢复原有结构')
        this.loadTree()
      })
    },

    // ===== Dataset Dialog =====
    resetDatasetForm() {
      this.datasetForm = { catalogId: null, datasetCode: '', datasetName: '', datasourceId: null, ownerName: '', remark: '' }
      this.$nextTick(() => { if (this.$refs.datasetForm) this.$refs.datasetForm.clearValidate() })
    },
    submitDatasetForm() {
      this.$refs.datasetForm.validate(valid => {
        if (!valid) return
        addDataset(this.datasetForm).then(res => {
          this.$modal.msgSuccess('新增成功')
          this.datasetDialogVisible = false
          const newId = res.data && (res.data.datasetId || res.data)
          this.loadTree().then(() => {
            if (newId) {
              const node = this.findTreeNode(n => n.nodeType === 'dataset' && n.datasetId === newId)
              if (node) {
                this.selectedNode = node
                this.$nextTick(() => { if (this.$refs.tree) this.$refs.tree.setCurrentKey(node.id) })
                // 创建成功后切到字段定义，引导选表选字段
                this.activeTab = 'fields'
                this.loadDataset(newId)
              }
            }
          })
        })
      })
    },

    // ===== Basic Info =====
    submitBasicForm() {
      this.$refs.basicForm.validate(valid => {
        if (!valid) return
        this.basicSaving = true
        updateDataset({
          datasetId: this.basicForm.datasetId,
          catalogId: this.basicForm.catalogId,
          datasetName: this.basicForm.datasetName,
          ownerName: this.basicForm.ownerName,
          status: this.basicForm.status,
          remark: this.basicForm.remark
        }).then(() => {
          this.$modal.msgSuccess('保存成功')
          this.loadDataset(this.basicForm.datasetId)
          this.loadTree()
        }).finally(() => { this.basicSaving = false })
      })
    },

    // ===== Versions =====
    loadVersions() {
      this.versionLoading = true
      return listVersions(this.dataset.datasetId).then(res => {
        this.versionList = res.data || res.rows || []
        this.versionLoading = false
        // 字段定义默认选中 DRAFT，其次默认版本，再次第一个
        if (!this.versionList.find(v => v.versionId === this.fieldVersionId)) {
          const draft = this.versionList.find(v => v.versionStatus === 'DRAFT')
          const dft = this.versionList.find(v => v.isDefault === '1' || v.isDefault === true)
          const target = draft || dft || this.versionList[0]
          this.fieldVersionId = target ? target.versionId : null
        }
        if (this.fieldVersionId) {
          this.handleFieldVersionChange(this.fieldVersionId)
        }
        // 数据预览默认选中默认在线版本
        if (!this.versionList.find(v => v.versionId === this.previewVersionId)) {
          const online = this.versionList.filter(v => v.versionStatus === 'ONLINE')
          const dftOnline = online.find(v => v.isDefault === '1' || v.isDefault === true)
          const target = dftOnline || online[0] || this.versionList[0]
          this.previewVersionId = target ? target.versionId : null
        }
      }).catch(() => { this.versionLoading = false })
    },
    versionStatusText(status) {
      return { DRAFT: '草稿', ONLINE: '已发布', OFFLINE: '已下线' }[status] || status
    },
    versionStatusTagType(status) {
      return { DRAFT: 'info', ONLINE: 'success', OFFLINE: 'warning' }[status] || 'info'
    },
    handleViewVersion(row) {
      this.activeTab = 'fields'
      this.fieldVersionId = row.versionId
      this.handleFieldVersionChange(row.versionId)
    },
    handleCopyVersion(row) {
      this.$modal.confirm('确认基于 V' + row.versionNo + ' 复制为新草稿版本？').then(() => {
        return copyVersion(this.dataset.datasetId, { sourceVersionId: row.versionId })
      }).then(() => {
        this.$modal.msgSuccess('已复制为新草稿版本')
        this.fieldVersionId = null
        this.loadVersions().then(() => {
          this.activeTab = 'fields'
        })
      }).catch(() => {})
    },
    handleOpenPublish(row) {
      this.publishForm = {
        versionId: row.versionId,
        versionNo: row.versionNo,
        versionName: row.versionName || '',
        releaseNote: '',
        setDefault: false
      }
      this.publishDialogVisible = true
    },
    resetPublishForm() {
      this.publishForm = { versionId: null, versionNo: null, versionName: '', releaseNote: '', setDefault: false }
    },
    submitPublish() {
      this.publishLoading = true
      publishVersion(this.publishForm.versionId, {
        versionName: this.publishForm.versionName,
        releaseNote: this.publishForm.releaseNote,
        setDefault: this.publishForm.setDefault
      }).then(() => {
        this.$modal.msgSuccess('发布成功')
        this.publishDialogVisible = false
        this.loadVersions()
        this.loadDataset(this.dataset.datasetId)
      }).finally(() => { this.publishLoading = false })
    },
    handleOfflineVersion(row) {
      this.$modal.confirm('确认下线版本 V' + row.versionNo + '？若为默认版本将取消默认。').then(() => {
        return offlineVersion(row.versionId)
      }).then(() => {
        this.$modal.msgSuccess('已下线')
        this.loadVersions()
        this.loadDataset(this.dataset.datasetId)
      }).catch(() => {})
    },

    // ===== Fields Tab =====
    handleFieldVersionChange(versionId) {
      const version = this.versionList.find(v => v.versionId === versionId)
      if (!version) return
      this.fieldVersionName = version.versionName || ''
      this.saveResult = { healthStatus: version.healthStatus || '', validationMessage: version.validationMessage || '' }
      this.fieldLoading = true
      getVersion(versionId).then(res => {
        const d = res.data || {}
        let def = {}
        if (d.definitionJson) {
          try { def = JSON.parse(d.definitionJson) } catch (e) { def = {} }
        }
        const tableId = def.tableId || d.tableId || null
        let fields = def.fields || []
        // 兼容后端直接返回字段明细（dp_dataset_field）
        if (!fields.length && Array.isArray(d.fields)) {
          fields = d.fields.map(f => ({
            columnId: f.sourceColumnId != null ? f.sourceColumnId : f.columnId,
            alias: f.fieldAlias != null ? f.fieldAlias : f.alias,
            enabled: f.enabled === '1' || f.enabled === true,
            orderNum: f.orderNum
          }))
        }
        this.applyVersionDefinition(tableId, fields)
      }).catch(() => { this.fieldLoading = false })
    },
    /** 回填版本定义：宽表 + 字段勾选/别名/启停/顺序 */
    applyVersionDefinition(tableId, fields) {
      this.fieldTableId = tableId
      if (!tableId) {
        this.fieldRows = []
        this.fieldLoading = false
        if (this.isDraftVersion) this.searchTables('')
        return
      }
      // 确保宽表下拉中有当前表的选项
      listTables(this.dataset.datasourceId, { pageNum: 1, pageSize: 999 }).then(res => {
        const rows = res.rows || []
        this.tableOptions = rows
        const found = rows.find(t => t.tableId === tableId)
        if (!found) {
          this.tableOptions = [{ tableId: tableId, objectName: '表#' + tableId, cnName: '' }].concat(rows)
        }
      })
      listColumns(tableId).then(res => {
        this.buildFieldRows(res.data || [], fields)
        this.fieldLoading = false
      }).catch(() => { this.fieldLoading = false })
    },
    /** 组装字段行：已勾选字段按 orderNum 升序在前，未勾选按原始顺序在后 */
    buildFieldRows(columns, selectedFields) {
      const selectedMap = {}
      ;(selectedFields || []).forEach(f => { selectedMap[f.columnId] = f })
      const checked = []
      const unchecked = []
      columns.forEach(c => {
        const columnId = c.columnId != null ? c.columnId : c.id
        const sel = selectedMap[columnId]
        const row = {
          columnId: columnId,
          columnName: c.columnName,
          columnType: c.columnType,
          columnComment: c.columnComment || '',
          alias: sel ? (sel.alias || c.columnName) : c.columnName,
          enabled: sel ? (sel.enabled === true || sel.enabled === '1') : true,
          checked: !!sel,
          orderNum: sel ? (sel.orderNum || 0) : 0
        }
        if (sel) checked.push(row)
        else unchecked.push(row)
      })
      checked.sort((a, b) => a.orderNum - b.orderNum)
      this.fieldRows = checked.concat(unchecked)
    },
    searchTables(keyword) {
      if (!this.dataset.datasourceId) return
      this.tableSearchLoading = true
      listTables(this.dataset.datasourceId, { pageNum: 1, pageSize: 50, objectName: keyword || '' }).then(res => {
        this.tableOptions = res.rows || []
        this.tableSearchLoading = false
      }).catch(() => { this.tableSearchLoading = false })
    },
    handleTableChange(tableId) {
      this.fieldKeyword = ''
      this.fieldRows = []
      if (!tableId) return
      this.fieldLoading = true
      listColumns(tableId).then(res => {
        this.buildFieldRows(res.data || [], [])
        this.fieldLoading = false
      }).catch(() => { this.fieldLoading = false })
    },
    toggleCheckAll(val) {
      const rows = this.filteredFieldRows
      rows.forEach(r => { r.checked = val })
    },
    checkedOrder(row) {
      const checked = this.fieldRows.filter(r => r.checked)
      const idx = checked.findIndex(r => r.columnId === row.columnId)
      return idx >= 0 ? idx + 1 : '-'
    },
    moveField(filteredIndex, dir) {
      const row = this.filteredFieldRows[filteredIndex]
      if (!row) return
      const i = this.fieldRows.findIndex(r => r.columnId === row.columnId)
      const j = i + dir
      if (i < 0 || j < 0 || j >= this.fieldRows.length) return
      const arr = this.fieldRows.slice()
      const tmp = arr[i]
      arr.splice(i, 1)
      arr.splice(j, 0, tmp)
      this.fieldRows = arr
    },
    handleSaveDraft() {
      if (!this.fieldVersionId) {
        this.$modal.msgError('请先选择草稿版本')
        return
      }
      if (!this.fieldTableId) {
        this.$modal.msgError('请先选择宽表')
        return
      }
      const fields = this.fieldRows.filter(r => r.checked).map((r, index) => ({
        columnId: r.columnId,
        alias: r.alias || r.columnName,
        dataType: r.columnType,
        enabled: r.enabled,
        orderNum: index + 1
      }))
      this.fieldSaving = true
      saveVersion({
        versionId: this.fieldVersionId,
        versionName: this.fieldVersionName,
        tableId: this.fieldTableId,
        fields: fields
      }).then(res => {
        const d = res.data || {}
        this.saveResult = { healthStatus: d.healthStatus || '', validationMessage: d.validationMessage || '' }
        if (d.healthStatus === 'INVALID') {
          this.$modal.msgWarning('草稿已保存，但校验未通过')
        } else {
          this.$modal.msgSuccess('草稿保存成功')
        }
        // 刷新版本列表中的健康状态
        listVersions(this.dataset.datasetId).then(r => {
          this.versionList = r.data || r.rows || []
        })
      }).finally(() => { this.fieldSaving = false })
    },

    // ===== Preview Tab =====
    handlePreview() {
      if (!this.previewVersionId) return
      this.previewLoading = true
      previewDataset({ versionId: this.previewVersionId }).then(res => {
        const d = res.data || {}
        this.previewColumns = d.columns || []
        this.previewRows = d.rows || []
        this.previewRan = true
        this.previewLoading = false
      }).catch(() => { this.previewLoading = false })
    },

    // ===== Logs =====
    loadLogs() {
      this.logLoading = true
      listLogs(this.dataset.datasetId, this.logQuery).then(res => {
        this.logList = res.rows || []
        this.logTotal = res.total || 0
        this.logLoading = false
      }).catch(() => { this.logLoading = false })
    },
    showDetail(row) {
      let detail = row.detailJson
      try { detail = JSON.stringify(JSON.parse(detail), null, 2) } catch (e) {}
      this.$alert(detail, '操作详情', { confirmButtonText: '关闭', customClass: 'log-detail-dialog' })
    },

    // ===== Catalog =====
    handleAddCatalog(parentId) {
      this.closeContextMenu()
      this.catalogDialogTitle = '新增目录'
      this.resetCatalogForm()
      this.catalogForm.parentId = parentId != null ? parentId : 0
      this.loadCatalogOptionsExclude(null)
      this.catalogDialogVisible = true
    },
    handleEditCatalog() {
      if (!this.selectedNode || this.selectedNode.nodeType !== 'catalog') return
      this.handleEditCatalogById(this.selectedNode.catalogId)
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
      this.handleDeleteCatalogById(this.selectedNode.catalogId)
    },
    handleDeleteCatalogById(catalogId) {
      this.closeContextMenu()
      const node = this.contextMenu.node || this.selectedNode
      this.$modal.confirm('确认删除目录"' + (node ? node.label : '') + '"？删除前需确保目录为空。').then(() => {
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
    }
  }
}
</script>

<style scoped>
.dataset-page {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 120px);
}

.dataset-layout {
  display: flex;
  align-items: stretch;
  gap: 16px;
  min-height: calc(100vh - 152px);
}

.dataset-sidebar,
.dataset-content {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.dataset-sidebar {
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

.tree-guide {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0 12px 8px;
  padding: 7px 9px;
  border-radius: 4px;
  color: #606266;
  background: #f5f7fa;
  font-size: 12px;
  line-height: 18px;
  transition: color 0.18s ease, background 0.18s ease;
}

.tree-guide i {
  margin-top: 2px;
  flex-shrink: 0;
}

.tree-guide.is-dragging {
  color: #1f5f99;
  background: #ecf5ff;
}

/*noinspection CssUnusedSymbol*/
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

/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node__content {
  position: relative;
  height: 36px;
  border-radius: 4px;
  cursor: grab;
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node__content:hover {
  background: #f0f7ff;
}

/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node.is-current > .el-tree-node__content {
  background: #e6f0fd;
  color: #1677c8;
  font-weight: 600;
}

/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node__content:active {
  cursor: grabbing;
}

/* 用细线串联同一分支，强化父子层级但不挤占节点内容 */
/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node__children {
  position: relative;
}

/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node__children::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 8px;
  left: 9px;
  width: 1px;
  background: #e4e7ed;
}

/* ── Drag-over visual feedback ── */

/* 被拖拽的节点半透明 + 倾斜 */
/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node.is-dragging > .el-tree-node__content {
  opacity: 0.62;
  background: #f5f7fa;
  box-shadow: inset 0 0 0 1px #c0c4cc;
}

/* 可放入（inner）：蓝色描边 + 浅蓝底 */
/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node.is-drop-inner > .el-tree-node__content {
  background: #e6f7ff;
  box-shadow: inset 0 0 0 1px #409eff;
  border-radius: 4px;
}

/* 不可放入：浅红底 + 红色边框 */
/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree-node.is-drop-not-allow.is-drop-inner > .el-tree-node__content {
  background: #fff1f0;
  box-shadow: inset 0 0 0 1px #f56c6c;
}

/* Element UI 自带的 drop-indicator 细线加粗发光 */
/*noinspection CssUnusedSymbol*/
::v-deep .sidebar-tree .el-tree__drop-indicator {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #1890ff;
  border-radius: 1px;
  box-shadow: 0 0 0 1px rgba(24, 144, 255, 0.12);
}

.custom-tree-node {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  font-size: 13px;
  position: relative;
}

.custom-tree-node .drag-handle {
  margin-right: 4px;
  color: #c0c4cc;
  font-size: 14px;
  cursor: grab;
  flex-shrink: 0;
  visibility: hidden;
  opacity: 0;
  transition: color 0.18s ease, opacity 0.18s ease;
}

/* 仅在拖拽流程中显示排序手柄，静态状态保持隐藏且不改变文字对齐 */
.sidebar-tree.is-dragging .custom-tree-node .drag-handle {
  visibility: visible;
  opacity: 1;
  color: #409eff;
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

@media (prefers-reduced-motion: reduce) {
  .tree-guide,
  .custom-tree-node .drag-handle,
  ::v-deep .sidebar-tree .el-tree-node__content {
    transition: none;
  }
}

.dataset-content {
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

.detail-actions > * + *,
.detail-form-actions > * + * {
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
  .dataset-layout {
    flex-direction: column;
    min-height: auto;
  }

  .dataset-sidebar {
    flex: none;
    width: 100%;
    min-width: 0;
    max-width: none;
  }

  .sidebar-tree {
    min-height: 280px;
    max-height: 360px;
  }

  .dataset-content {
    min-height: 480px;
  }
}

@media (max-width: 640px) {
  .dataset-page {
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
