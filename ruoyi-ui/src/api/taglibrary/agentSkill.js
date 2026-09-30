import request from '@/utils/request'
const root = '/taglibrary/agent/skills'
export const listAgentSkills = () => request({ url: root, method: 'get' })
export const saveAgentSkill = data => request({ url: root, method: 'post', data })
export const publishAgentSkill = (name, row_version) => request({ url: `${root}/${encodeURIComponent(name)}/publish`, method: 'post', data: { row_version } })
export const retireAgentSkill = (name, row_version) => request({ url: `${root}/${encodeURIComponent(name)}/retire`, method: 'post', data: { row_version } })
