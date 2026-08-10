import request from '@/utils/request'

// ==================== 对象群 ====================

// 查询对象群列表
export function listGroup(query) {
  return request({
    url: '/objectgroup/group/list',
    method: 'get',
    params: query
  })
}

// 查询对象群详情
export function getGroup(groupId) {
  return request({
    url: '/objectgroup/group/' + groupId,
    method: 'get'
  })
}

// 新增对象群
export function addGroup(data) {
  return request({
    url: '/objectgroup/group',
    method: 'post',
    data: data
  })
}

// 修改对象群
export function updateGroup(data) {
  return request({
    url: '/objectgroup/group',
    method: 'put',
    data: data
  })
}

// 删除对象群
export function delGroup(groupIds) {
  return request({
    url: '/objectgroup/group/' + groupIds,
    method: 'delete'
  })
}

// 生成规则 SQL（预览弹窗）
export function previewSql(data) {
  return request({
    url: '/objectgroup/group/sql',
    method: 'post',
    data: data
  })
}

// 运行规则（COUNT，刷新用户数）
export function runGroup(data) {
  return request({
    url: '/objectgroup/group/run',
    method: 'post',
    data: data
  })
}

// 样例预览（客户号 + 预览列）
export function previewGroup(data) {
  return request({
    url: '/objectgroup/group/preview',
    method: 'post',
    data: data
  })
}

// 导入关联文件解析（txt/csv 单列）
export function importParse(data) {
  return request({
    url: '/objectgroup/group/import/parse',
    method: 'post',
    data: data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// ==================== 码值 ====================

// 查询码值选项（新链路：维表合并，按 code_sort/tag_code 排序）
export function getCodeOptions(query) {
  return request({
    url: '/objectgroup/group/code-options',
    method: 'get',
    params: query
  })
}

// 查询码值列表
export function listCodeValue(query) {
  return request({
    url: '/objectgroup/group/codevalue/list',
    method: 'get',
    params: query
  })
}

// 码值同步（宽表 DISTINCT）
export function syncCodeValue(data) {
  return request({
    url: '/objectgroup/group/codevalue/sync',
    method: 'post',
    data: data
  })
}

// 新增码值
export function addCodeValue(data) {
  return request({
    url: '/objectgroup/group/codevalue',
    method: 'post',
    data: data
  })
}

// 修改码值
export function updateCodeValue(data) {
  return request({
    url: '/objectgroup/group/codevalue',
    method: 'put',
    data: data
  })
}

// 删除码值
export function delCodeValue(valueIds) {
  return request({
    url: '/objectgroup/group/codevalue/' + valueIds,
    method: 'delete'
  })
}
