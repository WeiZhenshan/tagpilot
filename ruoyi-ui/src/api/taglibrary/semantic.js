import request from '@/utils/request'

export function listSemanticTags(libraryId) {
  return request({ url: '/taglibrary/semantic/tag/list', method: 'get', params: { libraryId } })
}

export function publishSnapshot(libraryId, coverageNote) {
  return request({ url: '/taglibrary/semantic/snapshot/publish', method: 'post', params: { libraryId, coverageNote } })
}

export function eligibleTags(libraryId, snapshotId) {
  return request({ url: '/taglibrary/semantic/eligible-tags', method: 'get', params: { libraryId, snapshotId } })
}

export function activeSnapshot(libraryId) {
  return request({ url: '/taglibrary/semantic/snapshot/active', method: 'get', params: { libraryId } })
}

export function activateBuild(buildId) {
  return request({ url: `/taglibrary/semantic/index-build/${buildId}/activate`, method: 'post' })
}

export function listTerms(query) {
  return request({ url: '/taglibrary/semantic/term/list', method: 'get', params: query })
}

export function saveTerm(data) {
  return request({ url: '/taglibrary/semantic/term', method: 'put', data })
}

export function generateConfusable(libraryId) {
  return request({ url: '/taglibrary/semantic/confusable/generate', method: 'post', params: { libraryId } })
}

export function listConfusable(tagId) {
  return request({ url: `/taglibrary/semantic/confusable/${tagId}`, method: 'get' })
}

export function semanticList(resource, params) {
  return request({ url: `/taglibrary/semantic/${resource}/list`, method: 'get', params })
}
export function semanticDetail(resource, id) {
  return request({ url: `/taglibrary/semantic/${resource}/${encodeURIComponent(id)}`, method: 'get' })
}
export function semanticCodeSource(tagId) {
  return request({ url: `/taglibrary/semantic/code-value/${encodeURIComponent(tagId)}/source`, method: 'get' })
}
export function saveSemantic(resource, data) {
  return request({ url: `/taglibrary/semantic/${resource}`, method: 'put', data })
}
export function reviewSemantic(resource, id, sourceRef, code) {
  const target = code === undefined ? encodeURIComponent(id) : `${id}/${encodeURIComponent(code)}`
  return request({ url: `/taglibrary/semantic/${resource}/${target}/review`, method: 'post', data: { sourceRef } })
}
export function bootstrapExport(data) {
  return request({ url: '/taglibrary/semantic/bootstrap/export', method: 'post', data, timeout: 120000 })
}
export function bootstrapImport(data) {
  return request({ url: '/taglibrary/semantic/bootstrap/import', method: 'post', data, timeout: 120000 })
}
export function listSnapshots(params) { return semanticList('snapshot', params) }
export function listBuilds(snapshotId) { return semanticList('index-build', { snapshotId }) }
export function startBuild(snapshotId, storeType) {
  return request({ url: '/taglibrary/semantic/index-build/start', method: 'post', params: { snapshotId, storeType }, timeout: 660000 })
}
export function registerBuild(data) { return request({ url: '/taglibrary/semantic/index-build', method: 'post', data }) }
export function updateBuildStatus(buildId, status, evalSummary) {
  return request({ url: `/taglibrary/semantic/index-build/${buildId}/status`, method: 'put', params: { status, evalSummary } })
}
export function buildStats(buildId) { return request({ url: `/taglibrary/semantic/index-build/${buildId}/stats`, method: 'get' }) }
export function downloadSnapshot(snapshotId) {
  return request({ url: `/taglibrary/semantic/snapshot/${snapshotId}/download`, method: 'get', responseType: 'blob' })
}
export function retrieveSemantic(data) { return request({ url: '/taglibrary/semantic/retrieve', method: 'post', data }) }
export function submitFeedback(data) { return request({ url: '/taglibrary/semantic/feedback', method: 'post', data }) }

export function snapshotQuality(libraryId) { return request({ url: '/taglibrary/semantic/snapshot/quality', method: 'get', params: { libraryId }, timeout: 120000 }) }
export function profileTag(tagId) { return semanticDetail('profile', tagId) }
export function aggregateProfile(tagId) { return request({ url: `/taglibrary/semantic/profile/${tagId}/aggregate`, method: 'post', timeout: 120000 }) }
