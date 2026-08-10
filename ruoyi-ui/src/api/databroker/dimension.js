import request from '@/utils/request'

/**
 * 分页查询维表列表
 * @param {Object} query 查询参数 { pageNum, pageSize, dimensionName, dimensionCode, datasourceId, status }
 */
export function listDimension(query) {
  return request({
    url: '/databroker/dimension/list',
    method: 'get',
    params: query
  })
}

/**
 * 查询维表详情（data 含 dimension 实体各字段 + fieldChecks 标准字段校验结果，连接失败时 fieldChecks 为 null 且带 checkError）
 * @param {Number|String} dimensionId 维表ID
 */
export function getDimension(dimensionId) {
  return request({
    url: '/databroker/dimension/' + dimensionId,
    method: 'get'
  })
}

/**
 * 登记维表
 * @param {Object} data { dimensionName, dimensionCode, datasourceId, sourceTableId, remark }
 */
export function addDimension(data) {
  return request({
    url: '/databroker/dimension',
    method: 'post',
    data: data
  })
}

/**
 * 修改维表（后端仅接受 dimensionName、remark 两个字段的修改）
 * @param {Object} data { dimensionId, dimensionName, remark }
 */
export function updateDimension(data) {
  return request({
    url: '/databroker/dimension',
    method: 'put',
    data: data
  })
}

/**
 * 批量删除维表（任意维表被标签库关联则整体失败）
 * @param {String} dimensionIds 维表ID串，多个以逗号分隔
 */
export function delDimension(dimensionIds) {
  return request({
    url: '/databroker/dimension/' + dimensionIds,
    method: 'delete'
  })
}

/**
 * 修改维表状态
 * @param {Number|String} dimensionId 维表ID
 * @param {String} status 状态（'0'启用 '1'停用）
 */
export function changeDimensionStatus(dimensionId, status) {
  return request({
    url: '/databroker/dimension/' + dimensionId + '/status',
    method: 'put',
    data: { status: status }
  })
}

/**
 * 数据连接下拉选项
 * @returns data: [{ datasourceId, sourceName }]
 */
export function datasourceOptions() {
  return request({
    url: '/databroker/dimension/options/datasources',
    method: 'get'
  })
}

/**
 * 指定数据连接下的物理表下拉选项
 * @param {Number|String} datasourceId 数据连接ID
 * @returns data: [{ tableId, objectName, cnName, objectType }]
 */
export function tableOptions(datasourceId) {
  return request({
    url: '/databroker/dimension/options/tables',
    method: 'get',
    params: { datasourceId: datasourceId }
  })
}

/**
 * 六个标准字段校验结果
 * @param {Number|String} sourceTableId 物理表ID
 * @returns data: [{ columnName, exists }]
 */
export function fieldChecks(sourceTableId) {
  return request({
    url: '/databroker/dimension/options/fields',
    method: 'get',
    params: { sourceTableId: sourceTableId }
  })
}

/**
 * 维表物理码值分页预览
 * @param {Number|String} dimensionId 维表ID
 * @param {Object} query { pageNum, pageSize }
 * @returns rows: [{ tagNameEn, tagCode, tagNameCn, codeDefinition, codeSort, lastUpdateTime }]
 */
export function listDimensionValues(dimensionId, query) {
  return request({
    url: '/databroker/dimension/' + dimensionId + '/values',
    method: 'get',
    params: query
  })
}

/**
 * 维表已关联的标签库列表（标签库模块接口）
 * @param {Number|String} dimensionId 维表ID
 * @returns data: [{ libraryId, libraryName, status }]
 */
export function listLinkedLibraries(dimensionId) {
  return request({
    url: '/taglibrary/library/dimension/' + dimensionId + '/libraries',
    method: 'get'
  })
}
