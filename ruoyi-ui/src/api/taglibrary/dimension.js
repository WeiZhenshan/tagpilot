import request from '@/utils/request'

// 分页查询可关联的维表候选列表
export function dimensionCandidates(libraryId, query) {
  return request({
    url: '/taglibrary/library/' + libraryId + '/dimensions/candidates',
    method: 'get',
    params: query
  })
}

// 查询标签库已关联的全部维表ID（跨分页回显用）
export function selectedDimensions(libraryId) {
  return request({
    url: '/taglibrary/library/' + libraryId + '/dimensions/selected',
    method: 'get'
  })
}

// 覆盖保存标签库的默认维表（空数组清空）
export function saveDimensions(libraryId, dimensionIds) {
  return request({
    url: '/taglibrary/library/' + libraryId + '/dimensions',
    method: 'put',
    data: { dimensionIds }
  })
}
