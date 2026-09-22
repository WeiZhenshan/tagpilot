# 标签语义引擎与向量检索索引

Java 是快照、当前资格、激活状态和执行审计的权威端。本目录只消费不可变快照和 Java 传入的显式资格集合，运行 BGE、Milvus 和六通道检索。自然语言圈选工作台在独立后端 [`../tagpilot-agent`](../tagpilot-agent)。

2026-09-19 当前本地演示基线：

- 快照 `L107-20260919-002`：`ACTIVE`，969/969 业务标签、177 码值字段、1723 码值。
- 索引 `bge-m3-l107-20260919-002-r3`：BGE-M3 + bge-reranker-v2-m3，Milvus 3374 文档，行集对账通过。
- 600 题本地封存回归的点估计指标通过；它不是独立人工 Gold。

本文只描述本地演示与质量复验，不作生产部署或运维决策。

## 安装与回归

```bash
# 仓库根目录
uv sync --project tagpilot-semantic --extra dev
uv sync --project tagpilot-agent --extra dev

# 真实 BGE 使用 Python 3.12 独立环境
UV_PROJECT_ENVIRONMENT=.venv-models uv sync --project tagpilot-semantic --python 3.12 \
  --extra dev --extra models --frozen

bin/verify-tag-semantic.sh
VERIFY_UI=true bin/verify-tag-semantic.sh
```

模型目录不入 Git。当前演示需要：

```text
tagpilot-semantic/out/models/bge-m3/
tagpilot-semantic/out/models/bge-reranker-v2-m3/
```

## 本地启动

两个 Python 进程与 Java 必须使用同一个 `TAG_RUNTIME_TOKEN`。令牌只通过当前 shell 或本机受控配置注入，不写入 Git、命令文档或验收报告。

终端 1：启动真实 BGE/Milvus 语义引擎。

```bash
export TAG_RUNTIME_TOKEN='<本地随机令牌>'
export TAG_RUNTIME_PYTHON='tagpilot-semantic/.venv-models/bin/python'
export TAG_SNAPSHOT_DIR="$PWD/tagpilot-semantic/out/full-20260919/snapshots"
export TAG_INDEX_DIR="$PWD/tagpilot-semantic/out/full-20260919/indexes"
export TAG_EMBEDDING_PATH="$PWD/tagpilot-semantic/out/models/bge-m3"
export TAG_RERANKER_PATH="$PWD/tagpilot-semantic/out/models/bge-reranker-v2-m3"
export MILVUS_URI='http://127.0.0.1:19530'
./bin/tag-semantic-runtime.sh
```

终端 2：启动 Agent 编排层（默认 `http://127.0.0.1:8092`）。

```bash
export TAG_RUNTIME_TOKEN='<与终端1相同>'
export TAG_SEMANTIC_URL='http://127.0.0.1:8091'
./bin/tagpilot-agent.sh
```

终端 3：启动 Java 和 Vue。本地演示允许使用从页面“导出实时冻结”得到的当前来源文件；必须同时固定其 SHA-256，两者缺一时配置不生效。

```bash
export TAG_RUNTIME_TOKEN='<与终端1相同的令牌>'
export TAG_SNAPSHOT_DIR="$PWD/tagpilot-semantic/out/full-20260919/snapshots"
export TAG_LOCAL_DEMO_CURRENT_FREEZE='<实时冻结 JSONL 的绝对路径>'
export TAG_LOCAL_DEMO_CURRENT_FREEZE_SHA256='<实时冻结文件 SHA-256>'
PORT=1024 ./dev.sh start
```

打开 `http://localhost:1024/taglibrary/semantic-index`，选择“个人客户经营标签库”：

1. 确认表格显示 `L107-20260919-002 / ACTIVE / 969/969`。
2. 点击“发布前检查”，确认 `excluded=[]`、均分 94、最低 70。
3. 输入“上月借记卡消费金额至少0”，确认返回标签 1175、DSL 合法且待确认。
4. 点击“符合需求”，确认反馈按本人 Trace 入库，不会自动执行客群筛选。

## 可选的真实 LLM 选择器

选择器在 `tagpilot-agent` 中。只把经过 Java 资格剪裁和检索后的候选发给 OpenAI-compatible `chat/completions` 端点，不发送客户原始数据或整库快照。只有组织批准的端点和数据范围才能配置：

| 环境变量 | 用途 |
|---|---|
| `TAG_LLM_BASE_URL` | OpenAI-compatible 服务基地址 |
| `TAG_LLM_MODEL` | 已批准模型名 |
| `TAG_LLM_API_KEY` | 运行时凭据，只经环境注入 |

本机开发可在仓库根目录创建 `.tag-llm-config`（已加入 `.gitignore`），`dev.sh` / `bin/tagpilot-agent.sh` 会自动加载。DeepSeek 示例：

```text
TAG_LLM_BASE_URL=https://api.deepseek.com
TAG_LLM_MODEL=deepseek-flash
TAG_LLM_API_KEY=sk-...
```

重启 Agent 编排层后，页面必须显示 `model_connected=true`才能把该次查询记为 LLM 选择结果。未配置或调用失败时不自动执行，当前精确证据回退模式也不得冒充 LLM。

## 快照、索引和评测复验

```bash
# Milvus 实体行集与 manifest 对账（语义引擎已启动）
curl -H "Authorization: Bearer $TAG_RUNTIME_TOKEN" \
  'http://127.0.0.1:8091/stats?build_id=bge-m3-l107-20260919-002-r3'

# 重跑 600 题本地封存回归；输出路径必须是新文件
tagpilot-semantic/.venv-models/bin/python -m tag_semantic.eval.acceptance \
  --build-dir tagpilot-semantic/out/full-20260919/indexes/bge-m3-l107-20260919-002-r3 \
  --sealed tagpilot-semantic/out/full-20260919/eval/sealed-600-v2.json \
  --sha256 2c542a60b5a8124b855c89fd97465e13899f0848f7469fadb50d4cba934999d4 \
  --output /private/tmp/sealed-600-recheck.json
```

正式高质量验收不能重用当前同源 600 题。独立 Gold 必须由未参与语义生成/调优的人员编写和复核，外部保管 hash，并提供真实的 `reviewed_by/reviewed_at/source_ref/isolation_ref`。当前已执行结果、置信区间和人工待办见 `docs/validation/语义索引层建设验收记录.md`。
