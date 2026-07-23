import request from '@/utils/request'

// 查询标签目录列表
export function listDir(libraryId) {
  return request({
    url: '/taglibrary/dir/list',
    method: 'get',
    params: { libraryId }
  })
}

// 新增标签目录
export function addDir(data) {
  return request({
    url: '/taglibrary/dir',
    method: 'post',
    data: data
  })
}

// 修改标签目录
export function updateDir(data) {
  return request({
    url: '/taglibrary/dir',
    method: 'put',
    data: data
  })
}

// 删除标签目录
export function delDir(dirId) {
  return request({
    url: '/taglibrary/dir/' + dirId,
    method: 'delete'
  })
}
