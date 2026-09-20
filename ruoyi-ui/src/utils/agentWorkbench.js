export var AGENT_WORKBENCH_PATH = '/agent'
export var AGENT_WORKBENCH_DEFAULT_FROM = '/taglibrary/list'
export var AGENT_WORKBENCH_BACK_MESSAGE = 'tagpilot-agent:back'

function isSafeInternalPath(path) {
  return typeof path === 'string' && path.charAt(0) === '/' && path.indexOf('//') !== 0 && path.indexOf('://') === -1
}

export function agentWorkbenchLocation(options) {
  var source = options || {}
  var query = { from: isSafeInternalPath(source.from) ? source.from : AGENT_WORKBENCH_DEFAULT_FROM }
  if (source.libraryId != null && source.libraryId !== '') {
    query.libraryId = source.libraryId
  }
  if (source.libraryName) {
    query.libraryName = source.libraryName
  }
  return { path: AGENT_WORKBENCH_PATH, query: query }
}

export function parseAgentBackPath(payload) {
  var from = payload && payload.from
  return isSafeInternalPath(from) ? from : AGENT_WORKBENCH_DEFAULT_FROM
}
