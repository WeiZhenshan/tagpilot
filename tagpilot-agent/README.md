# TagPilot Agent 编排层

Claude Agent SDK 单 Agent 循环，经 Anthropic 协议调用 DeepSeek。五个领域工具负责检索、详情、能力、校验与终态提交；纯 Python Guard 约束来源、数值、时间、冻结条件和需求覆盖。Java 继续拥有身份、当前标签资格、发布版本、编译、统计和建群权限。本服务不生成 SQL，不查询客户明细，不自动执行圈选。

```bash
uv sync --project tagpilot-agent --extra dev
export TAG_RUNTIME_TOKEN='<与 Java / tagpilot-semantic 相同>'
export ANTHROPIC_BASE_URL='https://api.deepseek.com/anthropic'
export ANTHROPIC_MODEL='deepseek-flash'
export ANTHROPIC_API_KEY='<模型密钥>'
./bin/tagpilot-agent.sh
```

启动脚本可读取根目录未入 Git 的 `.tag-llm-config`。仅将官方 `TAG_LLM_BASE_URL=https://api.deepseek.com` 映射到 Anthropic 端点；第三方网关必须显式设置 `ANTHROPIC_BASE_URL`。原 OpenAI 协议 URL 不能直接用于 SDK。

| 配置 | 默认值 / 含义 |
|---|---|
| `TAG_AGENT_RUNTIME` | `claude_sdk`；本地重构已删除旧图，不能通过环境变量切回 LangGraph |
| `TAG_AGENT_HOST / TAG_AGENT_PORT` | `127.0.0.1:8092` |
| `TAG_SEMANTIC_URL` | `http://127.0.0.1:8091` |
| `TAG_AGENT_DB` | 启动脚本使用 `<项目根>/tagpilot-agent/out/workbench.sqlite`；直接运行 API 默认 `./data/agent/workbench.sqlite` |
| `TAG_AGENT_STORAGE_KEY` | 默认服务令牌；更换令牌时应显式保留原加密密钥，否则历史记录不可读 |
| `TAG_AGENT_MAX_CONCURRENCY / TAG_AGENT_PER_USER_MAX` | `2 / 2`；开发默认值，未经过生产容量评测 |
| `TAG_AGENT_QUEUE_MAX / TAG_AGENT_QUEUE_TIMEOUT` | `24 / 20` 秒；满队列返回 429 |
| `TAG_AGENT_MAX_TURNS / TAG_AGENT_MAX_TOOLS` | `10 / 16` |
| `TAG_AGENT_MAX_DEEP / TAG_AGENT_MAX_DETAILS` | `4 / 6`；详情限额也覆盖 Guard 自动读取 |
| `TAG_AGENT_SOFT_TIMEOUT / TAG_AGENT_HARD_TIMEOUT` | `40 / 90` 秒 |
| `TAG_AGENT_MAX_RSS_MB / TAG_AGENT_MAX_BUDGET_USD` | `600 / 1`；SDK 成本估值不等于 DeepSeek 实际账单 |

`runtime/` 管理准入、取消、子进程、加密事件库；`agent/` 提供稳定提示、上下文和 outcome；`tools/` 是唯一 MCP 工具集合；`retrieval/` 管理版本与资格隔离的 WorkingSet/LRU；`domain/` 定义严格输入；`guards/` 是不依赖 SDK 的确定性校验。根目录旧纯函数模块保留薄导入入口。

每次发送、resume、repair 都冷建 SDK 会话。禁用内置工具、外部 MCP、用户设置、文件检查点与会话持久化；临时配置目录退出即清理。`submit_result` 接受后通过 PostToolUse 与 interrupt 结束，不再等待模型生成结尾。手工编辑直接进入 Guard。

SQLite 仍限定单个服务进程，文件锁阻止多进程共用。运行中的草案写入加密运行库，启动后未完成运行标为 INTERRUPTED，可从保存的原话、问答、上一版方案冷恢复。旧 `.checkpoints` 不再读取或生成；本次未删除用户已有历史文件。旧版本存储兼容入口保留，但旧数据实库升级演练尚未执行。应备份运行库及密钥，部署前完成升级演练。

浏览器只访问 Java；下列业务内部接口要求服务令牌：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 无认证探活 |
| POST | `/agent/v2/runs` | Java 注入 owner/thread/版本/资格；相同 ID 与原始内容幂等 |
| GET | `/agent/v2/runs/{id}?owner_id=…&after=…` | 状态、当前结果和增量事件 |
| POST | `/agent/v2/runs/{id}/resume` | 恢复 WAITING/FAILED/INTERRUPTED；资格只能收紧 |
| POST | `/agent/v2/runs/{id}/repair` | Java 结构化诊断回灌，最多两次，权限/版本错误不修复 |
| POST | `/agent/v2/runs/{id}/cancel` | 取消并保留草案 |
| DELETE | `/agent/v2/threads/{thread_id}?owner_id=…` | 删除该所有者的运行记录 |

终态工具返回 `READY / NEEDS_USER_INPUT / CAPABILITY_GAP / PARTIAL`，映射为兼容的 `result.plan/questions/interrupt_id` 和新增 `result.outcome`。`schema_version=3`，新诊断统一使用 `diagnostics`。历史 UI 仍兼容读取 `validation_errors`。

本次只做金标流程冒烟。实施范围、证据、后续完整评测入口及回滚边界见 [SDK 重构实施记录](../docs/development/Agent-SDK重构实施记录.md)。
