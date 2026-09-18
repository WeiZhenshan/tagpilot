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
