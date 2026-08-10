import request from '@/utils/request'

// ==================== 标签元数据变更审批 ====================

// 查询元数据变更待审批列表
export function metaAuditList(query) {
  return request({
    url: '/taglibrary/tag/mapping/auditList',
    method: 'get',
    params: query
  })
}

// 查询元数据变更详情（变更前后 + 标签当前值）
export function metaAuditDetail(changeId) {
  return request({
    url: '/taglibrary/tag/mapping/' + changeId,
    method: 'get'
  })
}

// 元数据变更审批（批量通过/驳回，原子）
export function auditMetaChange(data) {
  return request({
    url: '/taglibrary/tag/mapping/audit',
    method: 'post',
    data: data
  })
}
