import request from '@/utils/request'

// ==================== 数据集 ====================

// 目录 + 数据集树
export function treeDataset() {
  return request({
    url: '/databroker/dataset/tree',
    method: 'get'
  })
}

// 查询数据集详情
export function getDataset(datasetId) {
  return request({
    url: '/databroker/dataset/' + datasetId,
    method: 'get'
  })
}

// 新增数据集
export function addDataset(data) {
  return request({
    url: '/databroker/dataset',
    method: 'post',
    data: data
  })
}

// 修改数据集
export function updateDataset(data) {
  return request({
    url: '/databroker/dataset',
    method: 'put',
    data: data
  })
}

// 删除数据集
export function delDataset(datasetIds) {
  return request({
    url: '/databroker/dataset/' + datasetIds,
    method: 'delete'
  })
}

// 移动/排序数据集（拖拽排序用）
export function moveDataset(id, data) {
  return request({
    url: '/databroker/dataset/' + id + '/move',
    method: 'put',
    data: data
  })
}

// 版本列表
export function listVersions(datasetId) {
  return request({
    url: '/databroker/dataset/' + datasetId + '/versions',
    method: 'get'
  })
}

// 版本详情（definitionJson + 字段明细）
export function getVersion(versionId) {
  return request({
    url: '/databroker/dataset/version/' + versionId,
    method: 'get'
  })
}

// 保存草稿（重写定义并校验）
export function saveVersion(data) {
  return request({
    url: '/databroker/dataset/version',
    method: 'put',
    data: data
  })
}

// 复制版本为新草稿
export function copyVersion(datasetId, data) {
  return request({
    url: '/databroker/dataset/' + datasetId + '/version/copy',
    method: 'post',
    data: data
  })
}

// 发布版本
export function publishVersion(versionId, data) {
  return request({
    url: '/databroker/dataset/version/' + versionId + '/publish',
    method: 'post',
    data: data
  })
}

// 下线版本
export function offlineVersion(versionId) {
  return request({
    url: '/databroker/dataset/version/' + versionId + '/offline',
    method: 'post'
  })
}

// 数据预览
export function previewDataset(data) {
  return request({
    url: '/databroker/dataset/preview',
    method: 'post',
    data: data
  })
}

// 操作记录
export function listLogs(datasetId, query) {
  return request({
    url: '/databroker/dataset/' + datasetId + '/logs',
    method: 'get',
    params: query
  })
}

// 宽表列表（数据集所属数据源下的表）
export function listTables(datasourceId, query) {
  return request({
    url: '/databroker/dataset/datasource/' + datasourceId + '/tables',
    method: 'get',
    params: query
  })
}

// 宽表字段列表
export function listColumns(tableId) {
  return request({
    url: '/databroker/dataset/table/' + tableId + '/columns',
    method: 'get'
  })
}

// ==================== 数据集目录 ====================

// 目录列表（扁平，前端 handleTree 构建树）
export function listCatalog(query) {
  return request({
    url: '/databroker/dataset/catalog/list',
    method: 'get',
    params: query
  })
}

// 目录详情
export function getCatalog(catalogId) {
  return request({
    url: '/databroker/dataset/catalog/' + catalogId,
    method: 'get'
  })
}

// 新增目录
export function addCatalog(data) {
  return request({
    url: '/databroker/dataset/catalog',
    method: 'post',
    data: data
  })
}

// 修改目录
export function updateCatalog(data) {
  return request({
    url: '/databroker/dataset/catalog',
    method: 'put',
    data: data
  })
}

// 删除目录
export function delCatalog(catalogId) {
  return request({
    url: '/databroker/dataset/catalog/' + catalogId,
    method: 'delete'
  })
}

// 移动/排序目录（拖拽排序用）
export function moveCatalog(data) {
  return request({
    url: '/databroker/dataset/catalog/move',
    method: 'put',
    data: data
  })
}
