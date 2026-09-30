<p align="center">
    <img alt="TagPilot Logo" src="docs/images/tagpilot-logo.png" width="180">
</p>

<h1 align="center">TagPilot 标签智能体（竞赛交付版）</h1>

<p align="center">标签中台（DataBroker / TagLibrary / ObjectGroup）+ 自然语言圈选 + 洞察 Skill 工作台</p>

**分支**：`tagpilot-release` · **版本**：`competition-20260930`（commit 见 `git rev-parse HEAD`）  
**演示剧本**：[docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md](docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md)  
**语义索引**：`bge-m3-l107-20260919-002-r3`（LOCAL，随包位于 `tagpilot-semantic/out/full-20260919/`）  
**BGE 权重**：不入 Git，需本机下载（约 4.3GB，见下文）

---

## 30 秒说明

1. 准备 MySQL、Redis、JDK 8、Node、Python 3.12、`uv`、Maven。  
2. 初始化数据库 → 下载 BGE → 安装依赖 → 配置大模型 API → 编译 Java。  
3. `./dev.sh start` → 浏览器登录 `admin` → 菜单进入 **智能圈选**（`/agent`）→ 按演示脚本操作。

---

## 环境要求

| 组件 | 版本/说明 |
| :--- | :--- |
| JDK | **8**（Amazon Corretto 8 等；`dev.sh` 会尝试自动切换） |
| Maven | 3.6+ |
| MySQL | 8.0+，端口 3306 |
| Redis | 端口 6379 |
| Node.js | 18+（`ruoyi-ui`、`tagpilot-assistant`） |
| Python | **3.12**（语义引擎 FlagEmbedding；3.14+ 不可用） |
| uv | Python 包管理，见 https://docs.astral.sh/uv/ |
| 大模型 API | 仓库根目录 `.tag-llm-config`（见 [.tag-llm-config.example](.tag-llm-config.example)） |
| Milvus | **可选**；本交付包使用 **LOCAL** 索引，默认无需 Docker Milvus |

---

## 一次性准备（按顺序）

### 1. 数据库

```bash
mysql -h127.0.0.1 -P3306 -uroot -p < sql/init/ry_init.sql
DB_USER=root DB_PASSWORD=你的密码 bash bin/db-migrate.sh
```

脚本索引见 [sql/README.md](sql/README.md)。演示数据在 `ry_init.sql` 的 `indiv_cust` 宽表（标签库 107，2000 人样本）。

### 2. 下载 BGE 模型（必需）

```bash
bash bin/download-bge-models.sh
```

模型目录约定见 [tagpilot-semantic/models-sources.json.example](tagpilot-semantic/models-sources.json.example)。  
`dev.sh` 在检测到 `tagpilot-semantic/out/models/bge-m3` 时会自动设置 `TAG_EMBEDDING_PATH`；reranker 请手动：

```bash
export TAG_RERANKER_PATH="$PWD/tagpilot-semantic/out/models/bge-reranker-v2-m3"
```

请勿对评委环境设置 `TAG_ALLOW_HASH_BASELINE=true`（仅开发基线）。

### 3. Python 依赖

```bash
uv sync --project tagpilot-semantic --extra dev --extra models
uv sync --project tagpilot-agent --extra dev
```

### 4. 前端依赖

```bash
cd ruoyi-ui && npm install && cd ..
cd tagpilot-assistant && npm install && cd ..
```

### 5. 大模型配置

```bash
cp .tag-llm-config.example .tag-llm-config
# 编辑 .tag-llm-config，填入 TAG_LLM_API_KEY
```

圈选与洞察 Skill 运行时需要可用的对话模型（脚本默认 DeepSeek 官方端点）。

### 6. 编译后端

```bash
mvn clean package -DskipTests
```

---

## 启动与验证

```bash
./dev.sh start
./dev.sh status
```

`status` 应看到 **五项** running：后端、Vue 前端、语义引擎 (8091)、Agent (8092)、智能体工作台 (5174)。

| 服务 | 端口 | 说明 |
| :--- | :--- | :--- |
| ruoyi-admin | 8080 | Java API |
| ruoyi-ui | 80（可用 `PORT=8081 ./dev.sh start`） | 管理端 + `/agent` 嵌入 |
| tagpilot-semantic | 8091 | 标签检索 |
| tagpilot-agent | 8092 | 圈选 / Skill 编排 |
| tagpilot-assistant | 5174 | React 工作台 UI |

首次启动时 `dev.sh` 会生成本机 `.tag-runtime-token`、`.databroker-crypto-secret`（不入 Git，请勿删除否则需重导库或重配数据源）。

**演示**：登录 `admin` / `admin123`（若与初始化脚本一致）→ 智能圈选 → 跟随 [演示脚本](docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md)。

---

## 故障排查

| 现象 | 处理 |
| :--- | :--- |
| 语义引擎启动失败 | 确认已 `download-bge-models.sh` 且 `uv sync --extra models`；检查 `TAG_EMBEDDING_PATH` / `TAG_RERANKER_PATH` |
| 索引不可用 | 确认存在 `tagpilot-semantic/out/full-20260919/snapshots` 与 `indexes`；若仅有 Git 克隆无 `out`，请使用 `bin/package-competition-zip.sh` 生成的完整 zip |
| 401 / 服务认证失败 | Java 与 Python 的 `TAG_RUNTIME_TOKEN` 不一致时删除 `.tag-runtime-token` 后重启 `./dev.sh restart` |
| 圈选无响应 | 检查 `.tag-llm-config` 与 API Key；`./dev.sh agent status` |
| 编译使用 JDK 17 失败 | 安装 JDK 8 或 `export JAVA_HOME=...` 后重试 |

---

## 项目结构（精简）

```
ruoyi-*              # Java：平台 + DataBroker + TagLibrary + ObjectGroup
ruoyi-ui             # Vue 管理端（含 /agent）
tagpilot-semantic/   # 语义检索（:8091）
tagpilot-agent/      # Agent 编排（:8092）
tagpilot-assistant/  # 工作台 UI（:5174）
skills/              # 洞察 Skill 源码（SKILL.md）
sql/                 # 初始化与迁移
bin/                 # download-bge-models.sh、db-migrate.sh、package-competition-zip.sh
dev.sh               # 一键启停
```

---

## 打包说明（维护者）

评委完整包（含 LOCAL 索引、不含 BGE 权重）：

```bash
bash bin/package-competition-zip.sh
# 输出 tagpilot-release-<git-sha>.zip
```

---

## 许可证

基于 RuoYi-Vue，MIT 协议。
