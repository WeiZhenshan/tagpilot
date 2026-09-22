# TagPilot Agent 编排层

Java 负责身份、当前标签资格和业务执行；本服务负责需求拆解、逐条件证据检索、受约束绑定、校验修复及澄清恢复。V2 使用 LangGraph 持久化检查点和加密运行事件，不生成 SQL，不直接统计或创建客群。

```bash
uv sync --project tagpilot-agent --extra dev
export TAG_RUNTIME_TOKEN='<与 Java / tagpilot-semantic 相同>'
export TAG_SEMANTIC_URL='http://127.0.0.1:8091'
export TAG_AGENT_DB="$PWD/tagpilot-agent/out/workbench.sqlite"
./bin/tagpilot-agent.sh
```

V2 必须配置真实模型；没有配置时明确报错。根目录 `.tag-llm-config` 可提供 `TAG_LLM_BASE_URL`（不带 `/v1`）、`TAG_LLM_MODEL`、`TAG_LLM_API_KEY`，环境变量优先。该本地文件禁止提交。

| 配置 | 含义 |
|---|---|
| TAG_AGENT_DB | SQLite 运行库路径；启动脚本默认 `<项目根>/tagpilot-agent/out/workbench.sqlite`（直接运行 API 时缺省 `./data/agent/workbench.sqlite`）；同目录另有 `.checkpoints` 和锁文件 |
| TAG_AGENT_STORAGE_KEY | 持久加密密钥，缺省使用服务令牌；数据保留期间必须保持稳定，换令牌时应显式保持原存储密钥 |
| TAG_AGENT_HOST / TAG_AGENT_PORT | 默认 `127.0.0.1:8092` |
| TAG_SEMANTIC_URL | 默认 `http://127.0.0.1:8091` |

SQLite 版本限定单服务进程，文件锁阻止多个进程共用库；进程内最多4个工作线程。重启把未完成运行置为 INTERRUPTED，用户可从检查点继续。部署必须保留两份数据库及对应密钥，不能把它们放进每次覆盖的构建目录。多实例部署需另行实现共享任务领取与数据库检查点。

内部接口均需服务令牌；浏览器只访问 Java：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 探活，无认证 |
| POST | `/agent/v2/runs` | 服务端注入 owner/thread/发布版本/资格；相同 ID 相同内容幂等 |
| GET | `/agent/v2/runs/{id}?owner_id=…&after=…` | 状态及增量事件 |
| POST | `/agent/v2/runs/{id}/resume` | 恢复中断/失败；重新收紧标签资格 |
| POST | `/agent/v2/runs/{id}/cancel` | 停止，保留已产出的证据 |

详细契约、迁移、边界和验证见 [Agent V2 实施说明](../docs/development/Agent-V2实施说明.md)。
