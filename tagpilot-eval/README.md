# TagPilot 合成评测工程（P0 / P1）

本轮执行范围：**P0 事实冻结和审计、P1 工程骨架与 200 个校准母案例**。正式生成 **0 条**。`generate / split / run / diagnose / propose / compare / apply` 命令均在产生副作用前拒绝；不得据此进入 P2。

当前交付是可复现的校准稿，不是已完成业务验收的评测集。母案例由 Agent 编写配方后确定性物化，全部标记 `DRAFT / CALIBRATION / PENDING`。独立模型复核、用户抽检和真实 Agent / Java 运行尚未执行。

## 交付入口

| 工件 | 内容 |
|---|---|
| [交付报告](reports/p0-p1-v1/REPORT.md) / [可展开案例页面](reports/p0-p1-v1/report.html) | 当前基线、审计摘要、200 个首轮原话与标准树 |
| [事实包](data/p0-v1/manifest.json) | 来源 hash、活动快照与索引、固定参考日期、来源冻结副本 |
| [事实清单](data/p0-v1/facts.jsonl) / [问题清单](data/p0-v1/issues.jsonl) | 969 标签字段与码值、逐字段口径证据、冲突与执行数据覆盖 |
| [母案例](data/calibration-v1/cases.jsonl) / [输入集](data/calibration-v1/inputs.jsonl) | 200 个私有真值对象 / 无答案首轮输入 |
| [模拟结果](data/calibration-v1/oracle-results.jsonl) | 166 个可计算轮次的完整模拟客户 ID 集、数量与 hash |
| [抽检队列](reports/p0-p1-v1/human-review-queue.jsonl) | 按类别分层选取的 40 个母案例，全部待审核 |
| [验证记录](reports/p0-p1-v1/VERIFICATION.md) | 225 项工程检查通过，包含 166 个可计算轮次的独立交叉校验 |
| [Task Spec](tasks/calibration-200/Task.md) / [通用知识](knowledge/WORLD.md) | 任务边界、输入与真值隔离、裁判规则、证据限制 |
| [JSON Schema](schemas/) | EvalCase、EvalRun、EvalVerdict、SemanticChangeSet 四项契约 |
| `reports/p0-p1-v1/progress.sqlite3` | 200 个待复核任务，绑定数据集 manifest hash |

## 已确认的基线

2026-09-26 本机只读观测：标签库 107 有 970 个字段，其中业务标签 969 个、对象键 1 个；ACTIVE 快照为 `L107-20260919-002`，ACTIVE 索引为 `bge-m3-l107-20260919-002-r3`。当前检索使用 BGE-M3 与 bge-reranker-v2-m3，索引 3,374 个文档，服务返回 `id_reconciled=true`。这是版本与行集证据，不代表本轮评测通过。

P0 对照数据库元数据、发布快照、原始标签文档、建表及码值 SQL、仓库模拟 SQL，得到 960 个来源可对应标签与 9 个未解决标签。`VERIFIED_SOURCE` 不表示银行口径签署，`official_bank_verified` 始终为 false。

- 9 个阻断项：1 个业务类型与语义类型冲突、2 个比例类型与 COUNT 单位冲突、6 个标签与“最高”概念冲突。相关母案例明确预期能力缺口，未伪造 READY 真值。
- 417 个提示项：358 个旧字段字典与当前 SQL 的 NULL 率差异、57 个期间金额统计口径待复核、2 个非平凡单位倍率。提示不自动改写来源定义。
- 当前仓库模拟 SQL 有 2,000 行；739 个业务字段有区分度，230 个字段为常量。数据库只核对了模拟行数，未读取并逐单元格核对客户值，因此完整 ID 集仅对绑定 hash 的**仓库 SQL**成立。
- 177 个码值字段共 1,723 个码值；复用来源与 Demo 约定分别标注。前导零保留为字符串。

## 200 个母案例

| 类别 | 母案例数 | 重点 |
|---|---:|---|
| 单字段 | 60 | 五类标签、八个业务域、明确阈值和码值 |
| 组合 | 50 | AND/OR、产品空白、金额、明确比例与产品类数 |
| 澄清 | 30 | 不明确的金额、时间、业务口径，不擅自补默认值 |
| 边界 | 20 | 严格/包含端点、NULL、负数、前导零、全客群 |
| 多轮 | 20 | 添加、修改、删除、回答澄清并保留原条件 |
| 能力缺口 | 20 | 事实冲突、缺少明细、操作符/资格限制 |

200 个母案例归入 199 个谱系组，不能当作 200 个统计独立样本。全部为校准分区；当前每个母案例只物化一条首轮表达及固定后续轮次，未执行原总方案中的双表达润色或正式扩写。首轮终态为 146 READY、34 NEEDS_USER_INPUT、20 CAPABILITY_GAP；覆盖标签数与域分布以报告为准，不宣称全量覆盖。

## 运行

Python >= 3.11。正常依赖为 Pydantic 2；开发检查需要 pytest、jsonschema；只有实时只读采集需要 PyYAML 和本机 mysql 客户端。本轮使用仓库已有虚拟环境，未安装软件或启动服务。

从仓库根目录执行；所有新输出目录必须不存在，避免覆盖已审核版本。

```bash
# 已交付数据的离线验证
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli validate --p0 tagpilot-eval/data/p0-v1 --calibration tagpilot-eval/data/calibration-v1
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m pytest -q tagpilot-eval/tests

# 从固定只读观测重建来源包，不访问数据库
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli inventory --root . --observation tagpilot-eval/data/p0-observation-20260926.json --output tagpilot-eval/out/p0-replay

# 仅允许 200 个 P1 母案例
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli seed --root . --p0 tagpilot-eval/out/p0-replay --output tagpilot-eval/out/calibration-replay --count 200
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli report --p0 tagpilot-eval/out/p0-replay --calibration tagpilot-eval/out/calibration-replay --output tagpilot-eval/out/report-replay
PYTHONPATH=tagpilot-eval tagpilot-agent/.venv/bin/python -m tagpilot_eval.cli journal --calibration tagpilot-eval/out/calibration-replay --output tagpilot-eval/out/progress.sqlite3
```

`live.py` 是独立的只读采集入口：内部读取现有本机数据库配置及运行时 token，固定 SQL 在一致性只读事务内执行，仅输出元数据与模拟行数；配置、密码和 token 不进入产物。服务健康、统计端点的采样与数据库事务不是跨系统原子快照，采集器/审计器会核对活动版本与 hash，但仍需保留观测时间。重复采集会得到新的观测包，不能冒充同一实验版本。

## 工程边界与后续接口

- **已实现**：四项严格契约及 Schema、来源 hash 核验、200 母案例物化、码值/类型/资格/口径质量检查、独立 Decimal / 日期 / NULL 裁判、同级逻辑及集合顺序归一化、边界探针、完整 ID 集校验、报告与 SQLite 待复核进度。
- **测试完成**：每个可计算轮次通过独立 SQLite 参考查询交叉核对；裁判反例包括错阈值、错逻辑、错绑定、同人数不同集合、伪造通过字段、损坏证据及越阶段调用。SQLite 是测试用独立后端，不能替代 MySQL / Java 执行验收。
- **仅预留契约**：L1 检索跑批、Agent SSE/多轮适配、`AudiencePlan schema_version=3` 参考导出、真实 Java 执行、独立模型审查、分组分区和近重复检测、成本预算、归因与变更发布。命令明确拒绝调用，不存在假装成功的占位结果。
- **评分限制**：当前条件树裁判支持已证明的排序、同级扁平化与数值格式归一化；尚不证明任意代数等价。`PARTIAL`、澄清问句与能力原因只有契约和金标，真实输出自动评分器尚待接入。
- **审核方式**：先审 40 条队列，同时核对 `truth_basis` 与源事实，记录 reviewer、时间、ACCEPT/REJECT、原因。当前 SQLite 人工复核记录只作任务进度；不得把 DRAFT 金标直接改为正式留出集。
- **进入 P2 前**：需要用户另行授权，完成独立复核、人工校准、阻断事实处理/显式排除、Agent 适配与裁判验收。修订应新建数据集版本和 manifest；本轮不会执行这些后续动作。

## 输入与答案隔离

被测 Agent 将来只接收 `inputs.jsonl` 的输入与必要业务来源，通过真实资格约束读取语义。`cases.jsonl`、`oracle-results.jsonl`、抽检页和报告属于评测控制面，不可索引进检索语料，也不可传入 Agent prompt。多轮后续话术由评测控制器在相应阶段发送；不能一次性泄漏未来用户回复。

本模块未修改业务代码、数据库、索引或客户数据，未运行任何付费模型调用，未创建群体，未提交或推送 Git。
