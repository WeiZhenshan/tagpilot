# TagPilot Agent 编排层

Java 计算当前资格后，把自然语言查询交给本服务。本服务只调用 `tagpilot-semantic` 的 `/retrieve`，在候选上跑 LangGraph（retrieve → select → validate_dsl → finalize），返回待确认 DSL。`auto_execute=false`，不会圈客。

默认端口 `8092`。服务间令牌与语义引擎、Java 必须相同。

## 安装

```bash
uv sync --project tagpilot-agent --extra dev
```

## 本地启动

先启动语义引擎（8091），再启动本服务：

```bash
export TAG_RUNTIME_TOKEN='<与 Java / tagpilot-semantic 相同>'
export TAG_SEMANTIC_URL='http://127.0.0.1:8091'
./bin/tagpilot-agent.sh
```

可选 LLM 选择器（未配置时走精确证据离线模式）：

| 环境变量 | 用途 |
|---|---|
| `TAG_LLM_BASE_URL` | OpenAI-compatible 服务基地址 |
| `TAG_LLM_MODEL` | 已批准模型名 |
| `TAG_LLM_API_KEY` | 仅环境注入 |

本机也可在仓库根目录放置 `.tag-llm-config`（已加入 `.gitignore`）。

## HTTP

均需 `Authorization: Bearer $TAG_RUNTIME_TOKEN`（`/health` 除外）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 探活 |
| POST | `/agent/query` | LangGraph 受控选择 |

Java 配置 `tag.agent-url`（环境变量 `TAG_AGENT_URL`，默认 `http://127.0.0.1:8092`）。
