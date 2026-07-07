import request from '@/utils/request'

// 目录列表（扁平，前端 handleTree 构建树）
export function listCatalog(query) {
  return request({
    url: '/databroker/catalog/list',
    method: 'get',
    params: query
  })
}

// 目录详情
export function getCatalog(catalogId) {
  return request({
    url: '/databroker/catalog/' + catalogId,
    method: 'get'
  })
}

// 新增目录
export function addCatalog(data) {
  return request({
    url: '/databroker/catalog',
    method: 'post',
    data: data
  })
}

// 修改目录
export function updateCatalog(data) {
  return request({
    url: '/databroker/catalog',
    method: 'put',
    data: data
  })
}

// 删除目录
export function delCatalog(catalogId) {
  return request({
    url: '/databroker/catalog/' + catalogId,
    method: 'delete'
  })
}
