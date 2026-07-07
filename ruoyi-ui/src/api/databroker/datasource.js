import request from '@/utils/request'

// 目录 + 数据源树
export function treeDataSource() {
  return request({
    url: '/databroker/datasource/tree',
    method: 'get'
  })
}

// 查询数据源详情
export function getDataSource(id) {
  return request({
    url: '/databroker/datasource/' + id,
    method: 'get'
  })
}

// 新增数据源
export function addDataSource(data) {
  return request({
    url: '/databroker/datasource',
    method: 'post',
    data: data
  })
}

// 修改数据源
export function updateDataSource(data) {
  return request({
    url: '/databroker/datasource',
    method: 'put',
    data: data
  })
}

// 删除数据源
export function delDataSource(ids) {
  return request({
    url: '/databroker/datasource/' + ids,
    method: 'delete'
  })
}

// 测试连接
export function testDataSource(data) {
  return request({
    url: '/databroker/datasource/test',
    method: 'post',
    data: data
  })
}

// 同步元数据
export function syncDataSource(id) {
  return request({
    url: '/databroker/datasource/' + id + '/sync',
    method: 'post'
  })
}

// 表信息列表
export function listTables(id, query) {
  return request({
    url: '/databroker/datasource/' + id + '/tables',
    method: 'get',
    params: query
  })
}

// 字段信息
export function listColumns(tableId) {
  return request({
    url: '/databroker/datasource/table/' + tableId + '/columns',
    method: 'get'
  })
}

// 修改中文名
export function updateTableCnName(tableId, data) {
  return request({
    url: '/databroker/datasource/table/' + tableId + '/cnName',
    method: 'put',
    data: data
  })
}

// 移动/排序数据源（拖拽排序用）
export function moveDataSource(id, data) {
  return request({
    url: '/databroker/datasource/' + id + '/move',
    method: 'put',
    data: data
  })
}

// 操作记录
export function listLogs(id, query) {
  return request({
    url: '/databroker/datasource/' + id + '/logs',
    method: 'get',
    params: query
  })
}
