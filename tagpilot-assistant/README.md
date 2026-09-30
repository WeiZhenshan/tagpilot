# TagPilot 圈选工作台

React + assistant-ui `ExternalStoreRuntime`，使用 Java 保存的用户会话作为消息和业务状态来源。白灰三栏提供历史、对话/真实行动记录、版本化条件树；Ask、停止/恢复、人数统计、客户样例和确认创建均接入服务端。

默认 `5174`，若依 `/agent` 通过同域 `/agent-ui/` iframe 加载。JWT 读取 `Admin-Token` cookie，不进入 URL。主题从父页面同步，返回客群编辑页时保留 schemaVersion 3 的精确运算符。

```bash
cd tagpilot-assistant
npm ci
npm run dev
npm test
npm run build
# 首次浏览器测试需要 npx playwright install chromium；或指定本机 Chrome 路径
npm run test:e2e
```

`PLAYWRIGHT_CHROMIUM_EXECUTABLE` 可指定 Chrome 可执行文件。E2E 使用明确的合成接口夹具验证界面，不作为模型正确率证据。生产构建放入 `ruoyi-ui/dist/agent-ui/`；Java 后端与 Python 服务须使用同一套发布版本。

左栏「会话 / 标签」支持当前库可用标签搜索、目录三态多选，每轮最多 5 项；已在当前方案（包括计算表达式）中的标签不可重复选择。确认时可填写补充说明并直接发起梳理，也可加入输入框作为 chip 后补充文字。发送成功清空本轮上下文，失败保留选择；历史消息回显所选标签。运行中、等待回答和归档状态仍可浏览，须完成当前操作或恢复会话后发送。

客群列表「智能体编辑」回跳 `/agent?groupId=…`，载入客群保存的 `audiencePlan`。条件须按最新发布版本重新核验，确认后更新原客群；手工规则客群继续使用原编辑器。完整接口、权限和验证边界见 [标签上下文与客群编辑实施说明](../docs/development/标签上下文与客群编辑实施说明.md)。

- [开发计划](../docs/development/Agent-V2开发计划.md)
- [接口、持久化与验证说明](../docs/development/Agent-V2实施说明.md)
- [本模块视觉规则](DESIGN.md)
- [assistant-ui ExternalStoreRuntime 官方文档](https://www.assistant-ui.com/docs/runtimes/custom/external-store)
