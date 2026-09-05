import request from '@/utils/request'

// 分页查询批量映射标签列表（含发布/审核/来源状态，支持 status/sourceStatus/keyword/includeMissing 过滤）
export function mappingList(query) {
  return request({
    url: '/taglibrary/tag/mapping/list',
    method: 'get',
    params: query
  })
}

// 同步标签库关联数据集当前在线版本字段并对账，返回版本信息与对账统计；业务失败返回真实失败原因
export function syncMappingFields(libraryId) {
  return request({
    url: '/taglibrary/tag/mapping/sync/' + libraryId,
    method: 'post'
  })
}

// 批量保存映射草稿（原子事务，items 各带 baseVersion/revision，响应回填 changeId/revision）
export function saveMappingDraft(items) {
  return request({
    url: '/taglibrary/tag/mapping/draft',
    method: 'put',
    data: { items }
  })
}

// 提交映射草稿审核
export function submitMapping(changeIds) {
  return request({
    url: '/taglibrary/tag/mapping/submit',
    method: 'post',
    data: { changeIds }
  })
}

// 撤回本人待审核申请为草稿
export function withdrawMapping(changeIds) {
  return request({
    url: '/taglibrary/tag/mapping/withdraw',
    method: 'post',
    data: { changeIds }
  })
}
