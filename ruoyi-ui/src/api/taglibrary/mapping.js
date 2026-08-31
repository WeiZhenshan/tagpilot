import request from '@/utils/request'

// 分页查询批量映射标签列表
export function mappingList(query) {
  return request({
    url: '/taglibrary/tag/mapping/list',
    method: 'get',
    params: query
  })
}

// 进入批量映射：增量同步标签库关联数据集的字段为标签（服务端尽力而为，失败不阻塞）
export function syncMappingFields(libraryId) {
  return request({
    url: '/taglibrary/tag/mapping/sync/' + libraryId,
    method: 'post'
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
