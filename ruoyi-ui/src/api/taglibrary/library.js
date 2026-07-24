import request from '@/utils/request'

// 查询标签库列表
export function listLibrary(query) {
  return request({
    url: '/taglibrary/library/list',
    method: 'get',
    params: query
  })
}

// 查询已上线数据集列表
export function listOnlineDatasets() {
  return request({
    url: '/taglibrary/library/datasets',
    method: 'get'
  })
}

// 查询标签库详情
export function getLibrary(id) {
  return request({
    url: '/taglibrary/library/' + id,
    method: 'get'
  })
}

// 新增标签库
export function addLibrary(data) {
  return request({
    url: '/taglibrary/library',
    method: 'post',
    data: data
  })
}

// 修改标签库
export function updateLibrary(data) {
  return request({
    url: '/taglibrary/library',
    method: 'put',
    data: data
  })
}

// 删除标签库
export function delLibrary(ids) {
  return request({
    url: '/taglibrary/library/' + ids,
    method: 'delete'
  })
}

// 同步标签库字段
export function syncLibrary(id) {
  return request({
    url: '/taglibrary/library/sync/' + id,
    method: 'post'
  })
}

// 提交标签库审批
export function submitLibrary(id) {
  return request({
    url: '/taglibrary/library/submit/' + id,
    method: 'post'
  })
}

// 审批标签库
export function auditLibrary(data) {
  return request({
    url: '/taglibrary/library/audit',
    method: 'post',
    data: data
  })
}

// 下线标签库
export function offlineLibrary(id) {
  return request({
    url: '/taglibrary/library/offline/' + id,
    method: 'post'
  })
}

// 查询审批记录
export function listAuditLogs(query) {
  return request({
    url: '/taglibrary/tag/auditLogs',
    method: 'get',
    params: query
  })
}
