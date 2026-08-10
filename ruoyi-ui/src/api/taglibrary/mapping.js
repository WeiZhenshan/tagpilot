import request from '@/utils/request'

// 分页查询批量映射标签列表
export function mappingList(query) {
  return request({
    url: '/taglibrary/tag/mapping/list',
    method: 'get',
    params: query
  })
}

// 批量保存映射草稿（原子事务）
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
