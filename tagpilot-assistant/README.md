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

- [开发计划](../docs/development/Agent-V2开发计划.md)
- [接口、持久化与验证说明](../docs/development/Agent-V2实施说明.md)
- [本模块视觉规则](DESIGN.md)
- [assistant-ui ExternalStoreRuntime 官方文档](https://www.assistant-ui.com/docs/runtimes/custom/external-store)
