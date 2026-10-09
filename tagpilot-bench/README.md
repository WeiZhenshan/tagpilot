# tagpilot-bench

TagPilot 评测体系（重建）。取代一次性的 `tagpilot-eval`（已于 2026-10-08 物理删除，恢复锚点 tag `bench-predel-20261008`）。

**设计稿**：[`../docs/design/TagPilot 评测体系重建设计.md`](../docs/design/TagPilot%20评测体系重建设计.md)

## 它是什么

分层测量 + 差分决策：一次运行同时给出三层分数，失败可定位到层。

| 层 | 组件 | 性质 | 测什么 |
|---|---|---|---|
| L1 语义 | `:8091` 语义引擎 | 确定性、免费 | 原子条件能否检索到目标标签（Recall@K） |
| L2 Agent | `:8092` Agent | 付费、重跑方差大 | 终态 / 条件树 / 口径 / 澄清 / 缺口 |
| L3 执行 | Java 权威链 | 确定性、权威 | 编译 + COUNT + **完整客户 ID 集** |

主指标 = `pass` = 终态正确 ∧ 该终态对应的正确性（READY→条件树、澄清→槽位、缺口→原因）。

## 核心不变量（教训来自旧体系）

- **与 Agent 协议解耦**：只有 `adapter.py` 知道 Agent 词表；Agent 改协议只改它。
- **复跑换 run_id**：Agent 对同 run_id 幂等，会造成假 100% 稳定。
- **多轮按契约**：WAITING→`resume`；其余新消息→新 run 携带 `previous_plan`（JUDGE-AUDIT F7）。
- **方差内置**：reps + Wilson 置信区间；超时/错误/驳回独立成列，不混进语义失败。
- **金标人数硬校核**：61 场景的实算人数必须等于文档人数，不符即错。
- **真值锚定三元组**：`snapshot_id + build_id + artifact_hash`（+ eligible）。

## 目录

```
cases/core/{cases,oracle,manifest}.jsonl|json   161 案例（61 场景 + 100 Demo）；141 READY + 20 澄清/缺口
cases/core/CASES.md                             人类可读案例清单
cases/guard/cases.jsonl                         5 条越权/拒答输入（期望不产出可执行名单）
cases/smoke/cases.jsonl                         内环子集（13 条）
cases/_source/                                  作者输入：61 文档解析、标签映射、trees/*.json、non_ready.json
tagpilot_bench/
  schema.py    案例/树/期望（自足契约）
  oracle.py    解释器 + 数学规范化 + 边界探针 + ID 集比对
  adapter.py   Agent 计划 → 评测树（唯一协议耦合点）
  grade.py     六维判定
  facts.py     标签事实（tag_id → 字段/类型/单位）
  db.py        只读访问 indiv_cust 宽表
  runner.py    驱动真实 Agent（reps/超时/多轮/预算/落盘/resume）
  report.py    summary.json（Wilson CI + 维度分解）
  compare.py   baseline vs vN 差分
tools/         案例物化（parse_61 / build_cases_61 / build_demo_cases / merge_cases / build_guard_cases / build_smoke）
runs/<suite>/<variant>/   results.jsonl / errors.jsonl / traces/ / summary.json
docs/legacy/   旧体系参照（JUDGE-AUDIT.md、reference/*.py）——只读，不 import
```

## 现状（2026-10-09）

- **P1 案例集完成**：61 场景全部结构化（50 实算人数对账通过 + 11 明细类无字段 → 澄清/缺口）；
  100 Demo 复用（oracle 从当前库重算，12 条与 P3 冻结值有 1–4 人漂移，见 `cases/core/demo_drift.json`）。
- **P2 判定器完成**：六维判定 + 验收套件（已知正确/等价改写/错阈值/伪造 valid/证据缺失/非终态）全绿。
- **P3 Runner 就绪**：HTTP 驱动 :8092，reps/超时/多轮/预算/落盘/resume；请求形状已对齐 RunRequest。
- **P4 基线待跑**：需你确认规模与预算后执行首次 smoke → core。

> 20/61 场景属「明细」类（基金只数/集中度、90 天活动、年龄、柜面/电子交易、活动触达转化、机会分、历史转出率）——
> 这些字段**不在宽表**，正确行为是澄清或报能力缺口，故建模为非 READY（见 `cases/_source/non_ready.json`）。

## 用法

```bash
PY=../tagpilot-agent/.venv/bin/python

# 1) 物化案例（先有 cases/_source/trees/*.json）
$PY -m tagpilot_bench.cli build-cases

# 2) 判定器自检（oracle/null）
$PY -m tagpilot_bench.cli selftest

# 3) 内环：改一次跑一次（并发默认 2）
$PY -m tagpilot_bench.runner --suite cases/smoke --reps 3 --variant v1 --budget-usd 15 --concurrency 2

# 4) 外环：发版前
$PY -m tagpilot_bench.runner --suite cases/core --reps 2 --variant v1 --budget-usd 60 --concurrency 2

# 5) 三层报告与差分（L1 免费确定性；L3 需 Java 令牌或回退本地 oracle）
$PY -m tagpilot_bench.cli l1 cases/core
$PY -m tagpilot_bench.cli l3 runs/core/v1
$PY -m tagpilot_bench.cli regrade runs/core/v1        # 判定逻辑改动后离线重判，不重跑
$PY -m tagpilot_bench.cli report runs/core/v1 cases/core/cases.jsonl
$PY -m tagpilot_bench.cli compare runs/core
```

运行前需：本机 Java(8080) / 语义(8091) / Agent(8092) 在线，仓库根 `.tag-runtime-token` 存在，
Agent 模型端点按 `.tag-llm-config` 配置。

## 作者指南

见 [`cases/_source/AUTHORING.md`](cases/_source/AUTHORING.md)（条件树 schema 与人数对账流程）。
