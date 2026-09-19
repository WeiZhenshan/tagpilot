# 标签语义与索引运行时

Java 是快照发布、当前资格、激活状态和审计的权威端。Python 只消费不可变快照与显式资格集合，拒绝自动切换存储模式。所有检索仅返回候选，`auto_execute=false`。

## 安装与验证

```bash
# 仓库根目录；基础工程验证支持 Python 3.11–3.14
uv sync --project ai-runtime --extra dev
bin/verify-tag-semantic.sh
# 同时检查 Vue 生产构建
VERIFY_UI=true bin/verify-tag-semantic.sh
```

真实 BGE 推理需 Python 3.11–3.13 与模型依赖。不要让 `models` 的平台条件在 Python 3.14 上跳过后误认为模型已经可用。2026-09-19 已在独立 `.venv-models`（Python 3.12）加载固定版本 BGE-M3 / reranker，完成开发集、隔离 HTTP 和 Milvus 实测；业务库尚未发布，不能外推全库准确率。

```bash
UV_PROJECT_ENVIRONMENT=.venv-models uv sync --project ai-runtime --python 3.12 --extra dev --extra models --frozen
# 模型目录不入 Git；先准备完整权重，再执行离线实测
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ai-runtime/.venv-models/bin/python ai-runtime/scripts/real_development_report.py \
  --embedding ai-runtime/out/models/bge-m3 --reranker ai-runtime/out/models/bge-reranker-v2-m3 \
  --output /private/tmp/semantic-development-new.json
```

## 本地/生产服务配置

预先准备本地模型目录及相同的 Java/Python 服务认证令牌，通过受控环境变量注入；不要将令牌放入文档、命令历史或 Git。

| 环境变量 | 用途 |
|---|---|
| `TAG_RUNTIME_TOKEN` | Java 与 Python 相同的服务间令牌；为空时拒绝服务 |
| `TAG_RUNTIME_URL` | Java 调用地址，默认 `http://127.0.0.1:8091` |
| `TAG_SNAPSHOT_DIR` | 两端共享的快照目录，默认仓库根下 `data/tag-snapshots` |
| `TAG_INDEX_DIR` | Python 构建目录，默认 `data/tag-index` |
| `TAG_EMBEDDING_PATH` | 已下载 BGE-M3 完整目录；构建记录内容指纹 |
| `TAG_RERANKER_PATH` | 已下载 bge-reranker-v2-m3 目录 |
| `TAG_RUNTIME_PYTHON` | 启动脚本的 Python 路径；真实模型可指定 `ai-runtime/.venv-models/bin/python` |
| `MILVUS_URI` / `MILVUS_TOKEN` | 外部 Milvus 地址与认证；默认 localhost:19530 |
| `TAG_ALLOW_HASH_BASELINE` | 仅隔离实验显式设 `true`，允许 HashEmbedder；不可用于正式质量验收 |

```bash
# 配置好上述环境变量后运行；生产由进程管理器托管
bin/tag-semantic-runtime.sh
# 可选只检查已运行的 Milvus；不启动容器
TAG_CHECK_MILVUS=true PORT=1024 ./dev.sh start
```

`dev.sh` 运行 `logs/runtime/ruoyi-admin.jar` 副本，避免 Maven 覆盖运行中的嵌套 JAR 引发登录类加载错误。重新构建后须正常重启后端加载新代码。

## 权威操作顺序

1. `POST /taglibrary/semantic/bootstrap/export` 冻结来源。请求 `{"libraryId":107}`；把返回 `data.jsonl` 原样存盘。
2. `python -m tag_semantic.bootstrap.expand_full freeze.jsonl --out-dir drafts` 生成 DRAFT；可用 `--confirmations` 指定业务复核包，不能批量自动 REVIEWED。
3. 通过 `POST /bootstrap/import` 导入概念、标签与码值草稿；别名、易混淆对和示例通过各自编辑接口入库。导入保护现有 REVIEWED/HUMAN/LLM 内容。
4. 业务人员在语义维护页确认概念、口径、单位、码义与依据；修改复核内容会退回 DRAFT。画像只有已复核 LOW 业务标签允许手动聚合，小样本与敏感字段被抑制。
5. `GET /snapshot/quality?libraryId=107` 检查；`POST /snapshot/publish?libraryId=107` 发布。当前库均为 DRAFT，发布应被门禁拒绝。
6. `POST /index-build/start?snapshotId=...&storeType=MILVUS` 由 Java 登记 BUILDING、调用 Python 构建并对账到 READY。Java 与 Python 不共盘时先用 `fetch-snapshot` 下载到 Python 的快照目录。
7. `POST /index-build/{buildId}/activate` 激活或回滚。只有 Java 可以改变数据库 ACTIVE；库锁串行化，失败补偿，当前资格重新校验。
8. `POST /retrieve` 请求 `{"libraryId":"107","requirement":"近30天异名跨行转入"}`；Java 固定 build 后提供动态资格，写回 Trace。Python `/retrieve` 必须明确传 `eligible_tag_ids`，空集返回空候选。
9. `POST /feedback` 只认认证身份及本人 Trace；查询原文默认仅存 SHA-256。反馈挖掘需另外提供经过业务脱敏复核的表达，不能从摘要反推客户原文。

上述相对 API 均以 `/taglibrary/semantic` 为前缀。快照下载使用 `semantic:list`，构建/运维使用 `semantic:bootstrap`，发布/激活/对账使用 `semantic:publish`，编辑与复核分别使用 `edit/review`。全量快照读取权限必须只授权相应治理人员/服务。

```bash
# TAG_JAVA_TOKEN 是有 semantic:list 权限的 Java 登录令牌
ai-runtime/.venv/bin/tag-semantic fetch-snapshot --base-url http://127.0.0.1:8080 \
  --snapshot-id SNAPSHOT_ID --out data/tag-snapshots/SNAPSHOT_ID.jsonl
```

## 巡检、回滚和备份

- `GET /index-build/{buildId}/stats` 返回实际 Milvus 行集对账、加载态和 alias；Python 不可用时明确失败。
- `POST /library/107/reconcile` 以数据库 ACTIVE 为准恢复 alias；不得用 alias 反写业务 ACTIVE。
- `POST /library/107/cleanup` 保留当前 ACTIVE 与最近三个可回滚 build，只清理更旧 RETIRED。文件锁等待本机在途读取；跨主机部署需共享支持锁的文件系统或外置分布式租约。
- 清理进入终态 PURGED，保留快照、manifest、docs、向量及词典以供重建；重建必须分配新 build_id。多个 Python 工作进程都会检查清理标记。
- 清理与激活目前为同步受控调用，生产异步调度、告警接收人、etcd/minio/宿主机指标采集尚未部署。

```bash
ai-runtime/.venv/bin/python ai-runtime/scripts/monitor_runtime.py --build-id BUILD_ID
ai-runtime/.venv/bin/python -m tag_semantic.index.maintenance backup data/tag-index/BUILD_ID /backup/BUILD_ID.tar.gz
ai-runtime/.venv/bin/python -m tag_semantic.index.maintenance rebuild data/tag-index/BUILD_ID data/tag-index/NEW_BUILD --build-id NEW_BUILD
```

备份命令只打包经逐文件校验的索引产物，不包含数据库、模型权重或密钥。正式备份需另用受控 MySQL 备份流程一致备份 `ry.ts_*`、完整快照目录、模型目录及独立密钥配置；恢复后检查模型/配置/content/doc_id 指纹，再经 Java 登记和激活。勿运行全量初始化 SQL。断电可能留下未登记快照、`.building-*` 或孤立 Collection，应对照数据库与 manifest 人工确认归属后清理，不能按名称批量删除。

## 评测与污染隔离

```bash
ai-runtime/.venv/bin/python ai-runtime/scripts/development_report.py
# 封存题由业务保管，位于训练、富化、反馈目录之外
ai-runtime/.venv/bin/python -m tag_semantic.eval.acceptance \
  --build-dir data/tag-index/BUILD_ID --sealed /restricted/gold.json \
  --sha256 VERIFIED_SHA256 --output /restricted/report.json
```

封存集必须 `status=SEALED`、`sealed=true`、至少 600 条，并校验外部 SHA-256。顶层 `provenance` 对象须提供非空 `reviewed_by/reviewed_at/source_ref/isolation_ref`；这只是来源声明校验，仍需人工核实真实签核和隔离。题目包括唯一 `id/query/eligible_tag_ids/atomic_conditions`，正常可回答题不得以空答案通过；原子条件给出 `accept_tag_ids`、封存评测必需的 `family_key`，需要全部字段时另给 `required_tag_ids`。码值题给字符串数组 `expected_codes` 与 `expected_code_tag_id`，不得丢失前导零。相同查询与资格集合不得重复凑数。澄清及不可表达题独立评价，不计入正常题命中率分母；召回 Top-20 与重排最终 Top-10 分开统计。报告不输出题目正文，也不覆盖已有报告。当前封存集仍为空占位，**不能据 20 条开发题宣称达到 Gold 99.5% 或 969 全覆盖**。

反馈飞轮建议每周离线汇总，去重 Trace/用户，排除封存题摘要，只在样本≥5、接受率≥0.9 时生成 DRAFT 候选；业务确认后进入下一次快照，已物化别名不再额外加分。当前提供纯离线挖掘模块，尚无无人值守入库任务。

实际测量、未完成项与变更偏差见 `docs/validation/语义索引层建设验收记录.md`。
