# TagPilot 合成评测工程

当前状态：**P0 事实审计 + P1 校准集与收尾 + P2 首期评测已交付**。

P2 交付（见 [验收报告](reports/p2-acceptance-v1/REPORT.md)）：**1,994 条合格案例**（500 母案例 × 4）、分区与污染检查、L1 全量分层基线、L2 真实 Agent 500 条分层基线、失败根因报告、覆盖报告，全部冻结到版本哈希。

**P2 已知缺口（原报告第 7 节）**：L2 稳定性复跑 `NOT_MEASURED`（实际执行 42/300 次）；回译独立核对覆盖 1,002/1,500 条改写；码值字段覆盖 162/177；每标签 ≥2 母案例未达标；33 条复核未产出结论、32 条要求修改但未给改法。上述历史结论保留。P3 已获单独授权，受控变更、版本对照和 100 个 Demo 案例的实际运行见 [P3 报告](reports/p3-acceptance-v1/REPORT.md)。不进入 P4 扩量。

## P2 交付入口

| 工件 | 内容 |
|---|---|
| [P2 验收报告](reports/p2-acceptance-v1/REPORT.md) | 版本哈希清单、四层结果、失败根因、未达标项 |
| [根因报告](reports/p2-diagnosis-v3/diagnosis.json) | 超时与无效运行单列；语义失败按方案 §四.1 归因；证据不足进 UNATTRIBUTED |
| [覆盖报告](reports/p2-coverage-v2/coverage.json) | 总标签/可确认/可表达/具备执行样本 + 码值校验 |
| [正式案例 p2-cases-v3](data/p2-cases-v3/manifest.json) | 1,994 条；DEV 1389 / REGRESSION 407 / HOLDOUT 198 |
| [L1 结果](runs/p2-l1-v2/l1-summary.json) | Recall@20 = 0.9907（DEV+REGRESSION，HOLDOUT 未运行） |
| [L2 结果](runs/p2-l2-v1/l2-summary.json) | 抽样 500 条判定 + 分层；稳定性 NOT_MEASURED |
| [P2 基准复验](data/p2-basis-v1/verification.json) | 已发布快照/索引与 P0 冻结值是否仍逐字节一致 |

P2 的隔离单位是 `(谱系组, 掩码模板签名)`：只看谱系组会让同一套话术模板散落到不同分区，留出集就不再独立于开发集。

## 已确认基线

| 工件 | 内容 |
|---|---|
| [P1 验收报告](reports/p1-acceptance-v1/REPORT.md) / [HTML](reports/p1-acceptance-v1/report.html) | 版本清单、六项状态、L1/L2 结果、残留缺口 |
| [裁判与解析复核](reports/p1-acceptance-v1/JUDGE-AUDIT.md) | 裁判能否把错答判对、解析能否静默读错的审计结论 |
| [事实包 p0-v2](data/p0-v2/manifest.json) | supersedes p0-v1；facts 不变，issues 附处置 |
| [来源冲突处置](data/p0-v2/dispositions.jsonl) / [码值分母漂移](data/p0-v2/source-drift.json) | 9 个阻断项逐条处置与证据 |
| [校准集 calibration-v2](data/calibration-v2/manifest.json) | supersedes calibration-v1；200 母案例，独立复核已落实 |
| [独立复核结论](reviews/independent-review-v1.jsonl) | 200 题逐题判定、理由与保留项 |
| [人工抽检页](reviews/human-review-v2/human-review.html) | 分层 40 题，含标准树、来源证据与导出框 |
| [L1 结果](runs/l1-calibration-v2/l1-summary.json) | 原子条件 Recall@20 与全条件覆盖 |
| [L2 结果](runs/l2-calibration-v2/l2-summary.json) | 真实 Agent 终态、判定、分层与成本 |
| [四项契约 Schema](schemas/) | EvalCase / EvalRun / EvalVerdict / SemanticChangeSet |

## 已确认基线

只读观测 2026-09-26：标签库 107 有 970 字段（业务标签 969 + 对象键 1）；ACTIVE 快照 `L107-20260919-002`、ACTIVE 索引 `bge-m3-l107-20260919-002-r3`，3,374 文档，`id_reconciled=true`。检索用 BGE-M3 + bge-reranker-v2-m3。

P0 审计：960 个来源可对应标签 + 9 个未解决；**9 个 ERROR 阻断项**（1 业务/语义类型冲突、2 比例-计数冲突、6 概念"最高"冲突）、417 个提示项。`VERIFIED_SOURCE` 不代表银行口径签署，`official_bank_verified` 恒为 false。

## 独立复核与人工抽检

独立复核由与被测 Agent 及配方作者不同的上下文完成，逐题核对：标签重绑定、字段与单位、时间与统计口径、阈值与码值是否出现在原话、资格与未解决事实边界、自然表达。

- 200 题全部有结论：**192 ACCEPT / 8 REVISE**。8 题改写仅涉及多轮母案例首轮话术同文，标准树与后续轮次不变。
- 6 题保留提示：`contains` 谓词的原话引用了模拟数据字面量（`SIM_…`），属 Demo 约定。
- 机械复核零缺陷：字段绑定、单位、口径、阈值、码值成员、资格、未解决事实、标签重绑定、禁止标签、操作符支持。

人工抽检页 `reviews/human-review-v2/human-review.html` 提供 40 题（分层抽样，按 case_id 摘要排序，可复现）。填答后导出 JSON，用 `human-import` 导入台账；导入会校验覆盖完整性与拒绝原因。

## 真实运行链路

| 层 | 内容 | 本轮状态 |
|---|---|---|
| L0 | 结构 / 引用 / 版本 / 来源字段校验 | 完成 |
| L1 | 本地语义检索：每个原子条件构造短语，检查目标标签是否进入 top-K 与口径一致 | 完成（免费，本地服务） |
| L2 | 真实 Agent：`/agent/v2/runs` + `/resume` 多轮，独立终态裁判 | 完成（DeepSeek 付费） |
| L3 | Java 权威编译与执行 | **NOT_APPLICABLE**（未接入，不计入分母） |

Agent 适配：`RunRequest` 新增可选 `reference_date` / `timezone`，注入上下文与系统提示，使"近 N 天 / 上月 / 上年"等相对时间以固定基准日 2026-09-18 推算。**该改动需重启 Agent 服务生效**；评测使用隔离实例，不打扰开发实例。

裁判验收套件（`judge.acceptance_suite`）覆盖：已知正确、等价改写、已知错误（错阈值 / 错操作符）、漏条件、伪造 `valid`、计划缺失、证据缺失、非终态。判定不采信 Agent 的 `valid` / `plan_status` / `diagnostics`。

## 运行

Python >= 3.11。生产依赖 Pydantic 2；开发检查需 pytest、jsonschema；实时采集需 PyYAML 与本机 mysql 客户端。L1/L2 需要本地语义服务 `:8091` 与 Agent 实例，以及环境变量 `TAG_RUNTIME_TOKEN`（或仓库根 `.tag-runtime-token`）。

从 `tagpilot-eval/` 执行；所有新输出目录必须不存在，避免覆盖已审核版本。

```bash
# 离线验证与测试
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli validate --p0 data/p0-v2 --calibration data/calibration-v2
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m pytest -q tests

# 收尾第 3 项：从 p0-v1 生成带处置记录的事实包
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli dispose --p0-v1 data/p0-v1 --output data/p0-v2

# 收尾第 1 项：机械证据包 / 按复核结论物化校准集
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli review --p0 data/p0-v2 --calibration data/calibration-v1 --output out/review-packet
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli review --p0 data/p0-v2 --calibration data/calibration-v1 --reviews reviews/independent-review-v1.jsonl --output data/calibration-v2

# 收尾第 4 项：人工抽检页与结论导入
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli human-review --p0 data/p0-v2 --calibration data/calibration-v2 --reviews reviews/independent-review-v1.jsonl --output reviews/human-review-v2
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli human-import --queue reviews/human-review-v2/queue.json --decisions <导出.json> --output reviews/human-review-v2/ledger.jsonl

# 收尾第 5 项：L1 / L2（真实运行）
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli l1 --p0 data/p0-v2 --calibration data/calibration-v2 --output runs/l1-calibration-v2 --k 20
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli l2 --p0 data/p0-v2 --calibration data/calibration-v2 --output runs/l2-calibration-v2

# 收尾第 6 项：冻结验收
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli freeze --p0 data/p0-v2 --calibration data/calibration-v2 --reviews reviews/independent-review-v1.jsonl --runs runs --human-ledger reviews/human-review-v2/ledger.jsonl --output reports/p1-acceptance-v1
```

L2 断点续跑：已完成的 `case_id` 会被跳过，结果逐行追加，长跑中断不丢进度；重跑同一 `run_id` 由 Agent 侧幂等缓存直接返回，不重复计费。

### P2 命令

付费命令必须显式给出 `--budget-usd`，未设预算只做估价、不发起调用。

```bash
# 基准复验（可传 --observation 与 P0 冻结观测逐表比对）
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli basis --p0 data/p0-v2 --root .. --output data/p2-basis-v1

# 500 母案例与分区
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli mothers --p0 data/p0-v2 --root .. --output data/p2-mothers-v1
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli split --p0 data/p0-v2 --mothers data/p2-mothers-v1 --output data/p2-split-v1

# 表达扩写（付费，可断点续跑；--limit 用于小批试跑）
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli generate --p0 data/p0-v2 --split data/p2-split-v1 --root .. --output data/p2-variants-v1 --budget-usd 15

# 物化正式集 → 全量独立复核 → 按复核结论落库
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli assemble --p0 data/p0-v2 --root .. --split data/p2-split-v1 --variants data/p2-variants-v1 --output data/p2-cases-v1
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli case-review --p0 data/p0-v2 --cases data/p2-cases-v1 --root .. --output reviews/p2-ai-review-v1 --budget-usd 20
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli materialize --cases data/p2-cases-v1 --reviews reviews/p2-ai-review-v1/reviews.jsonl --output data/p2-cases-v2

# 覆盖报告与分层 L2（付费；L2 只跑 DEV+REGRESSION，不碰 HOLDOUT）
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli coverage --p0 data/p0-v2 --cases data/p2-cases-v2 --output reports/p2-coverage-v1
PYTHONPATH=. ../tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli run --p0 data/p0-v2 --cases data/p2-cases-v2 --output runs/p2-l2-v1 --budget-usd 110 --agent-url http://127.0.0.1:8093
```

预算分阶段设上限（生成/复核/L2 各自封顶），而不是共用一个总额。改写只在**表达**上关推理（`reasoning_effort: none`），回译作为真值校验环节保留推理。

## 工程边界

- **已实现**：四项契约及 Schema、来源 hash 核验、来源冲突处置与漂移记录、200 母案例物化、独立复核与人工抽检机制、计划翻译器、独立终态裁判与验收套件、L1 检索跑批、L2 真实 Agent 跑批与多轮、报告与冻结。
- **P3 新增**：候选概念关联、Java 受控变更包、不可变 A/B/C/D 索引对照、固定 100 个自然语言 Demo 案例、实际 Agent 多轮与 Java COUNT/完整模拟 ID 集验证。`propose/compare/apply` 不隐式发布或激活。实际成绩以对应报告为准。
- **本轮未做**：P4 扩量、真实客户数据验证、客群建群、银行业务签署与容量验收。
- **评分限制**：裁判只证明所声明的等价类（同级扁平化、集合排序、数值格式、单值集合、区间展开、AND 内相同表达式/单位/口径/NULL 策略的同向数值边界蕴含）。不会因为当前数据的客户集合碰巧相同就认定错阈值或错字段正确。口径检查只判显式矛盾，不因代理未复述口径而失败。澄清问句与缺口原因按映射判定；合并口径/阈值问句额外要求在同一问题中明说“阈值/门槛”，并有至少两种带比较符与单位的数值边界选项。单纯窗口数字、重复同一边界及其它问题中的数字不算补足槽位；不做模型自由评分。
- **数据边界**：P0/P2 真值绑定仓库 SQL；P3 另核验 2000 个模拟客户的 15 个目标字段与 fixture 完全一致，证据在 `reports/p3-fixture-consistency.json`。结论仅限本机模拟数据。

## 输入与答案隔离

被测 Agent 只接收 `inputs.jsonl` 的输入与资格允许的业务事实。`cases.jsonl`、`oracle-results.jsonl`、抽检页与报告属于评测控制面，不可索引进检索语料，也不可传入 Agent prompt。多轮后续话术由评测控制器逐轮发送，不一次性泄漏未来用户回复。

P0/P1 阶段未修改业务数据库与索引。P3 的受控语义变更、快照和索引由 Java 控制面应用；客户数据未改动，未创建群体。

### P3 固定 Demo 复现

本机服务启动后，从仓库根运行；外部模型须使用用户授权的既有配置。`p3_run` 直接调用正式 Agent，发送合成原话与可见证据，答案树与完整客户集合留在本机裁判。

```bash
# 已冻结的 100 案例：标准、口语、省略、模糊澄清、指代追加
PYTHONPATH=tagpilot-eval:tagpilot-semantic tagpilot-semantic/.venv-models/bin/python -m tagpilot_eval.p3_run \
  --p0 tagpilot-eval/data/p3-facts-v3 --cases tagpilot-eval/data/p3-demo-100-v3 \
  --output tagpilot-eval/runs/p3-demo-new-run --build bge-m3-l107-20260928-006-p3g
```

每次复跑使用新输出目录以创建新运行 ID；同目录恢复仅跳过已完成案例。`--case-ids CAL-8001 ...` 只重跑指定失败题，首轮证据保留。Java 验证使用 `p3_run.run_java`，先通过标准验证码登录 `local.JavaClient`，随后调用既有权威编译与真实 COUNT；不创建客群。变更应用、快照发布、索引登记和激活仍由 Java 权限接口控制。

[100 个原话与预设后续消息](reports/p3-acceptance-v1/DEMO_CASES.md)；[第一轮变更包](changes/p3-semantic-v1/changeset.json)；[第二轮变更包](changes/p3-semantic-v2/changeset.json)；[后续消歧补丁](changes/p3-semantic-v4/changeset.json)。字段累计含义和 C1–C5 码值中包含 Demo 约定，不能当作银行签署。

## 独立洞察 SQL 参考套件

新增 `tagpilot_eval.insight`，与原圈选 P0/P1/P2/P3 案例集分开；不扩量、不调用模型或业务数据库。固定 800 人来源 / 240 人客群由 Java H2 测试生成 SQL 输出，再调用聚合执行器与独立手算常量对账。检查三个 Skill、确定性复跑、标准化 / Wilson区间证明、分档和原因组合、Fact / Chart Guard。

```bash
# 推荐：仓库根目录，Java 定向测试 + 独立参考 + 洞察库测试
bin/verify-insight.sh
# 单独读取已产生的 Java 聚合输出（需要本地 insight extra）
uv sync --project tagpilot-eval --extra insight
uv run --project tagpilot-eval --extra insight python -m tagpilot_eval.insight --java-aggregates /path/to/aggregates.json --output /path/to/verification.json
```

结果位于 `tagpilot-insight/reports/sql-reference-verification.json`：G1总AUM1.2亿元、G2理财缺口45pp/机会120人、G3高/中/低80/60/40人均一致。此结果是合成 H2 SQL 验证，不是目标 MySQL、真实HTTP整链或银行生产验收；工作台浏览器使用该报告的 mock API。
