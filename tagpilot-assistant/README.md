# TagPilot 智能体工作台

独立 React 应用，用 Assistant UI `LocalRuntime` 对接现有 Java `POST /taglibrary/semantic/retrieve`。不改 `tagpilot-agent` 选择图。

默认开发端口 `5174`，由若依 `/agent` 全屏 iframe 同域加载（路径前缀 `/agent-ui/`）。JWT 读取若依 `Admin-Token` cookie，禁止写入 URL。

```bash
cd tagpilot-assistant
npm install
npm run dev
npm test
```

若依开发代理把 `/agent-ui` 指到本服务。生产构建产物拷入 `ruoyi-ui/dist/agent-ui/`。
