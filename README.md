<p align="center">
    <img alt="TagPilot Logo" src="docs/images/tagpilot-logo.png" width="180">
</p>

<h1 align="center">TagPilot 标签智能体（竞赛交付版）</h1>

<p align="center">标签中台（DataBroker / TagLibrary / ObjectGroup）+ 自然语言圈选 + 洞察 Skill 工作台</p>

**分支**：`tagpilot-release` · **版本**：`competition-20260930`（commit 见 `git rev-parse HEAD`）  
**演示剧本**：[docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md](docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md)  
**数据库（推荐）**：[`sql/seed/competition/tagpilot-competition-20260930.sql.gz`](sql/seed/competition/tagpilot-competition-20260930.sql.gz) — 彩排全库 `ry` + `indiv_cust`  
**语义索引**：`bge-m3-l107-20260928-006-p3g`（与库内 ACTIVE 一致；目录 `tagpilot-semantic/out/full-20260919/`，随 zip 脚本打包）  
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

### 1. 数据库（推荐：竞赛全库快照）

```bash
# 与 application-druid.yml 默认一致时示例：
DB_PASSWORD=123456 bash bin/import-competition-db.sh
```

说明见 [`sql/seed/competition/README.md`](sql/seed/competition/README.md)。快照已含：标签库 **107**、已发布 **元 Skill**、语义 **ACTIVE 快照**、演示对照客群 **「全量客户（资产结构基准）」**、`schema_migration` 全记录等；**无需**再跑 `ry_init.sql`、`db-migrate.sh`、`agent-meta-skills.sql`。

**DataBroker 数据源密码**：库内密文与导出机的 [`.databroker-crypto-secret`](.databroker-crypto-secret) 绑定。评委需向交付方索取同一份密钥文件放到仓库根目录，或在「数据源管理」里重新录入密码。

<details>
<summary>备选：从空库按脚本初始化（无竞赛快照时）</summary>

```bash
mysql -h127.0.0.1 -P3306 -uroot -p < sql/init/ry_init.sql
DB_USER=root DB_PASSWORD=你的密码 bash bin/db-migrate.sh
mysql --default-character-set=utf8mb4 -uroot -p ry < sql/seed/agent-meta-skills.sql
```

</details>

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

首次启动时 `dev.sh` 会生成本机 `.tag-runtime-token`；若尚无 `.databroker-crypto-secret` 也会随机生成（**与竞赛库快照不匹配时 JDBC 数据源会解密失败**，见上文）。

---

## 演示数据与对照客群

演示「客群资产结构透视」用到**两个客群**，只有对照客群是预置数据：

| 角色 | 来源 | 说明 |
| :--- | :--- | :--- |
| 目标客群 | 现场圈选生成 | 按演示脚本输入一句话（如「当前AUM月日均余额50万元及以上的客户」）→ 核验 → 统计人数（实测 **287 人**） |
| **对照客群** | **库内预置对象群**「全量客户（资产结构基准）」 | 当前授权范围内的全部客户（SCOPE_ALL），**2,000 人**；技能运行时在「对照客群」下拉中选择它 |

- 对照客群已随竞赛全库快照提供（`sql/seed/competition/tagpilot-competition-20260930.sql.gz`），导入后即可用，**无需现场创建**。
- 需要重建时（换了其他快照或对象群被删）：

```bash
mysql --default-character-set=utf8mb4 -h127.0.0.1 -uroot -p ry < sql/seed/competition/demo-baseline-cohort.sql
```

脚本幂等（按「库 107 + 名称」判重），且方案的 `build_id/snapshot_id/artifact_hash` 在执行时从**库内 ACTIVE 快照与索引构建**读取——换快照后重建也不会报「对照客群与当前发布版本不一致」。详见 [`sql/seed/competition/README.md`](sql/seed/competition/README.md)。

- **预期数字**：目标 287 人 vs 对照 2,000 人，逐项目标/对照/差值的对账表（AUM 均值、三类资产占比、潜力等级分布）见[演示脚本附录 A](docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md)。
- **运行前提**：技能运行需客群人数 ≥ 20（低于则不下发统计），携带的分析列（标签 chip）**最多 5 个**；对照客群只列出与当前发布版本一致、且带已发布方案的已保存对象群。

---

## 评委复现清单（非代码、易遗漏）

| 项 | 是否随仓库/快照 | 说明 |
| :--- | :--- | :--- |
| MySQL `ry` + `indiv_cust` | **是**（`sql/seed/competition/*.sql.gz`） | 业务、Skill 登记、语义元数据、部分历史会话（若有） |
| `.databroker-crypto-secret` | **否**（单独交付） | 与快照内 `dp_datasource` 密文配对；缺失则重配数据源密码 |
| BGE `bge-m3` + reranker | **否** | `bin/download-bge-models.sh` |
| `tagpilot-semantic/out/full-*` | zip 脚本附带 | 与库内 `ts_catalog_snapshot` 的 ACTIVE 版本应对齐；若检索报 503，联系交付方更新索引包 |
| `.tag-llm-config` | **否** | 评委自备 API Key；圈选与 Skill 必需 |
| `.tag-runtime-token` | 启动时自动生成 | Java/Python 共用，删后 `dev.sh restart` 即可 |
| `tagpilot-agent/out/workbench.sqlite` | **否** | Agent 运行事件；新机为空，**不**影响按演示脚本重新圈选 |
| Redis | 空即可 | 仅登录 Token/缓存 |
| 上传头像等 `ruoyi.profile` 文件 | **否** | 缺则头像 404，不影响演示 |
| PPT / 设计说明 | 另交 | 不在代码 zip |

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
