import request from '@/utils/request'
const root = '/taglibrary/insight'
export const insightCatalog = library => request({ url: `${root}/${library}/catalog`, method: 'get' })
export const saveInsightVersion = (library, data) => request({ url: `${root}/${library}/versions`, method: 'post', data })
export const reviewInsightVersion = (library, id, version) => request({ url: `${root}/${library}/${encodeURIComponent(id)}/${encodeURIComponent(version)}/review`, method: 'post' })
export const publishInsightVersion = (library, id, version) => request({ url: `${root}/${library}/${encodeURIComponent(id)}/${encodeURIComponent(version)}/publish`, method: 'post' })
export const retireInsight = (library, id) => request({ url: `${root}/${library}/${encodeURIComponent(id)}/retire`, method: 'post' })
export const insightAudit = library => request({ url: `${root}/${library}/audit`, method: 'get' })

export const trialInsight = (library, id, version) => request({ url: `/taglibrary/insight/${library}/${id}/${version}/trial`, method: 'post' })
