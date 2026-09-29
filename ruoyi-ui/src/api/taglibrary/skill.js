import request from '@/utils/request'

// 技能列表（代理 Python 技能引擎，按登录用户权限收敛）
export function listSkill(query) {
  return request({ url: '/taglibrary/skill/list', method: 'get', params: query })
}

// 技能详情（Manifest 关键契约 + 版本 + 生命周期）
export function getSkill(skillId, version) {
  return request({ url: `/taglibrary/skill/${skillId}`, method: 'get', params: { version } })
}

// 技能版本列表
export function listSkillVersions(skillId) {
  return request({ url: `/taglibrary/skill/${skillId}/versions`, method: 'get' })
}

// 生命周期状态流转：publish / offline / deprecate / draft
export function changeSkillStatus(skillId, data) {
  return request({ url: `/taglibrary/skill/${skillId}/status`, method: 'post', data })
}

// 试运行（后端解析客群成员后调用技能引擎，聚合计算较慢）
export function runSkill(skillId, data) {
  return request({ url: `/taglibrary/skill/${skillId}/run`, method: 'post', data, timeout: 180000 })
}

// 运行历史（本地 tl_skill_run 分页查询）
export function listSkillRuns(query) {
  return request({ url: '/taglibrary/skill/runs', method: 'get', params: query })
}
