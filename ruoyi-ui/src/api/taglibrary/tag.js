import request from '@/utils/request'

// 查询标签树（按页签分组）
export function tagTree(libraryId, tab) {
  return request({
    url: '/taglibrary/tag/tree',
    method: 'get',
    params: { libraryId, tab }
  })
}

// 查询标签列表
export function listTag(query) {
  return request({
    url: '/taglibrary/tag/list',
    method: 'get',
    params: query
  })
}

// 查询待审批标签列表（审批管理页）
export function listAuditTags(query) {
  return request({
    url: '/taglibrary/tag/auditList',
    method: 'get',
    params: query
  })
}

// 查询标签详情
export function getTag(tagId) {
  return request({
    url: '/taglibrary/tag/' + tagId,
    method: 'get'
  })
}

// 修改标签
export function updateTag(data) {
  return request({
    url: '/taglibrary/tag',
    method: 'put',
    data: data
  })
}

// 移动标签（拖拽排序用）
export function moveTag(data) {
  return request({
    url: '/taglibrary/tag/move',
    method: 'put',
    data: data
  })
}

// 提交标签审批
export function submitTag(data) {
  return request({
    url: '/taglibrary/tag/submit',
    method: 'post',
    data: data
  })
}

// 审批标签
export function auditTag(data) {
  return request({
    url: '/taglibrary/tag/audit',
    method: 'post',
    data: data
  })
}

// 下线标签
export function offlineTag(data) {
  return request({
    url: '/taglibrary/tag/offline',
    method: 'post',
    data: data
  })
}
