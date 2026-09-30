import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../src/utils/agentWorkbench.js', import.meta.url), 'utf8')
const { parseAgentBackPath } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
assert.equal(parseAgentBackPath({ from: '/objectgroup/list' }), '/objectgroup/group')
assert.equal(parseAgentBackPath({ from: '/objectgroup/list?pageNum=2' }), '/objectgroup/group?pageNum=2')
assert.equal(parseAgentBackPath({ from: '/objectgroup/group' }), '/objectgroup/group')
assert.equal(parseAgentBackPath({ from: '/objectgroup/list-other' }), '/objectgroup/list-other')
assert.equal(parseAgentBackPath({ from: '//evil.example' }), '/taglibrary/list')
assert.equal(parseAgentBackPath({ from: 'https://evil.example' }), '/taglibrary/list')
console.log('工作台返回路由：6 项校验通过')
