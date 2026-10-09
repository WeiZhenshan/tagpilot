# TagPilot 评测体系重建设计

状态：**设计稿（待签收）**
日期：2026-10-08
范围：圈选主链路（需求 → 条件计划 → 完整客户 ID 集）；洞察技能链路留出接口，下一期接入。
前置决策（已确认）：① 圈选主链路优先；② 以 61 场景 + 100 Demo 为案例基底；③ 双档（smoke + core）节奏；④ 程序化判定为主、与 Agent 协议解耦。

---

## 1. 为什么重建

现行 `tagpilot-eval/`（P0→P3）把"案例从哪来、真值怎么证明、版本怎么冻结"做得极重，但"持续测量"最薄弱，四个硬伤：

| # | 硬伤 | 证据（2026-10-08 实测） |
|---|---|---|
| 1 | **跑不起** | 全量 1,994 条从未跑过 L2；预算 $150 只跑出 500 抽样；单案例 ≈ $0.135、p50 16.2s、p95 90.6s（`runs/p2-l2-v1/runs.jsonl`，542 runs / $73.04） |
| 2 | **不稳** | 3 次复跑 14 案例：**12 个不一致**（4 个三种结果、8 个两种、仅 2 个一致；`l2-summary.json` stability）。单次分数不可信，体系却用 `NOT_MEASURED` 盖住 |
| 3 | **测不准** | 判定为二值合取（`judge.py` checks 全真才 PASS）；无维度分、无置信区间；542 runs 中 59 次失败实为"跑不完"（RUN_NOT_TERMINAL/AGENT_NOT_TERMINAL），与语义错误混计 |
| 4 | **推不动** | 裁判直连 Agent 协议词表（outcome 枚举 / question reason / plan v3），Agent 每改行为→案例重建、判定重写、产物重冻结；无 CI、无差分入口；21 runs / 9 reports 版本矩阵靠人考古 |

另一处静默毒点：`data/p2-cases-v3/manifest.json` 摘要块写 DEV 1394 / GAP 200，实际 `cases.jsonl` 为 DEV **1389** / GAP **194**，而 `verify_package` 只校验文件哈希、不校验摘要——"冻结即可信"已有裂缝。

**结论**：`tagpilot-eval/` 停止作为活体系演进，原地冻结为**证据仓库**（P0–P3 冻结证据原样保留，不删除）；新建 `tagpilot-bench/` 承载测量体系。

## 2. 设计原则

1. **分层测量**：系统天然分三层，各层独立评分、失败可定位——一次运行同时给出三层分数，而不是端到端一个 PASS/FAIL。
   - 语义层（:8091，确定性、免费）：原子条件检索与证据
   - Agent 层（:8092，随机、付费）：条件计划 / 澄清 / 缺口
   - 执行层（Java，确定性、权威）：编译、COUNT、完整 ID 集
2. **以决策为中心**：每次运行回答"这次改动是变好还是变坏"——基线冻结、差分对照、方差可见。
3. **金标锚定真实业务**：61 场景（业务实算、含对照与陷阱）+ 100 Demo（结构化、全链路跑通过）。
4. **复用而非重造**：runner 取 `evaluate_workbench.py` 模式；等价类判定取 `judge.py` 的数学规范化并解耦；报告用 build-report-lite.mjs 契约。
5. **失败分类严格**：超时 ≠ 错误 ≠ 驳回；跑不完不计入语义分母，但计入成本与稳定性。

## 3. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ Suites（案例集，带哈希冻结）                                   │
│   core   ：61 场景 + 100 Demo + 4 多轮补丁  （≈165 条）        │
│   guard ：5 条越权/拒答输入                                   │
│   smoke  ：core/guard 的代表子集（≈13 条，改一次跑一次）        │
└─────────────────────────────────────────────────────────────┘
                    │ cases.jsonl + oracle.jsonl + manifest.json
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Runner（bench/runner.py）                                     │
│   固定 (snapshot_id, build_id, artifact_hash, eligible)       │
│   + reference_date=2026-09-18 / Asia/Shanghai                 │
│   驱动真实 Agent（默认 HTTP :8093 隔离实例；--inproc 备选）     │
│   reps ≥ 2，并发 ≤ 2，per-case 硬超时 180s                     │
│   逐案例落盘；失败分类 error/timeout；幂等 resume               │
└─────────────────────────────────────────────────────────────┘
                    │ results.jsonl + traces/ + errors.jsonl
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Graders（三层，各自独立）                                      │
│   L1 语义：原子条件 → /retrieve_batch → Recall@K（免费）        │
│   L2 计划：终态/树/口径/澄清/缺口 —— 解耦版等价类判定            │
│   L3 执行：READY 案例 → Java 编译 + COUNT + 完整 ID 集对账      │
│   输出 grade = {pass, outcome, tree, caliber, clarify, gap,   │
│                 idset}（每案例一行多维分）                      │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Report（summary.json + report.html + 差分）                    │
│   主指标 pass 率 ± Wilson CI；按维度/场景/难度分解；            │
│   成本·延迟·降级分层；baseline vs vN 对照                      │
└─────────────────────────────────────────────────────────────┘
```

## 4. 案例集设计

### 4.1 来源与合并

| 来源 | 条数 | 现状 | 重建动作 |
|---|---|---|---|
| 61 场景（`sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md`，A01–K08） | 61 | 五段式（主输入/口语/口径对齐/对照/期望+人数/评测陷阱），**无结构化树、无 ID 集** | 全部结构化：树 + oracle + 人数对账 |
| 100 Demo（`tagpilot-eval/data/p3-demo-100-v3/`） | 100 | 结构化完整（树/turns/oracle ID 集），P3 全链路 100/100 通过 | 直接复用；校验口径与当前 G 快照一致 |
| 多轮补丁示例（61 文档尾部 4 条） | 4 | 文字 | 转成 turns 案例（B02 追加 / C01 收窄 / G02 改写 / 空集不放宽） |
| 负面输入（61 文档尾部 5 条） | 5 | 文字 | 独立 suite `guard`：断言不产出可执行名单 / 明确澄清 |

**去重与权重**：61 与 100 在 7 个场景（入金/到期/代发/激活/基金/活动/渠道）有表达级重叠。全部保留（同一能力的多个测例），但每条打 `scenario` 与 `source` 标签，报告支持按场景聚合，**防止 7 个场景被两种来源双重加权**。

### 4.2 案例 schema（统一）

```jsonc
{
  "case_id": "SC-A02",              // SC-* = 61 场景；DM-* = Demo；PT-* = 补丁；GD-* = guard
  "suite": "core",
  "source": "scenario-61 | demo-100 | patch | guard",
  "scenario": "高价值客户贡献",
  "tags": ["A-资产机构", "直达", "单条件"],   // tags[0] = 报告主分组
  "difficulty": "直达 | 需组合 | 需澄清 | 明细 | 空集",
  "requirement": "帮我圈选当前时点 AUM 大于等于 100 万元的客户。",
  "turns": [],                       // 多轮案例预置后续话术；单轮为空
  "reference_date": "2026-09-18",
  "timezone": "Asia/Shanghai",
  "expected": {
    "outcome": "READY",              // READY | NEEDS_USER_INPUT | CAPABILITY_GAP
    "tree": { "...条件树..." },       // 与 P3 同一 schema，判定侧自有契约
    "clarify_slots": [],             // 需澄清案例：必备槽位
    "gap_codes": [],                 // 缺口案例：必备原因
    "counts": {"target": 203, "contrast": 1797, "prefix": 176}
  },
  "oracle_ref": "SC-A02",            // oracle.jsonl 中的完整 ID 集键
  "provenance": {
    "authoring": "HUMAN_DOC_STRUCTURED",   // 或 P3 原值
    "oracle": "MYSQL_RECOUNT",             // 与文档人数对账方式
    "verified": true
  }
}
```

### 4.3 61 场景结构化（本期最大工作量）

流程（每案例可审、可复算）：

1. 解析文档五段式 → 案例骨架（主输入/口语/对照/难度/人数/陷阱）
2. 从"口径对齐"重建结构条件树：绑定 `tl_tag`（field_name→tag_id）、操作符、码值、口径（时间锚）
3. **oracle 实算**：树 → SQL → 本机 MySQL 只读事务 → 完整 ID 集
4. **人数对账（硬门槛）**：实算人数必须等于文档 Numbers（target/contrast/prefix 三列全对）；不符的案例必须逐条归因（树错→改树；文档错→记录并修正），**未通过对账的案例不进 suite**
5. 抽样人工复读：每类（A–K）抽 1–2 条人工核对树与 SQL 的语义一致性

已抽样验证可行（2026-10-08）：A02=203 ✓、G01=66 ✓、B02=39 ✓、B04 目标 0/对照 49 ✓——文档人数与 `L_INDVCST_LABEL` 实算完全一致。

### 4.4 smoke 子集（13 条）

覆盖每个难度与关键陷阱的代表：A01（全集基线）、A02（直达）、B02（组合）、B04（空集）、C03（到期+风评）、D03（派生归一）、E03（明细+多条件）、F03（明细只数）、G02（组合类数）、H01（活动指定）、I01（多渠道）、J04（OR 排除）、GD-01（越权）。

### 4.5 oracle 与真值链

- `oracle.jsonl`：`{case_id, count, ids[], ids_sha256}`；全量 ID 集只在本机评测控制面，**不进入任何 Agent 可见输入**。
- 真值锚定三元组：`snapshot_id + build_id + artifact_hash`（复跑时核对）＋ 宽表 `L_INDVCST_LABEL`（2,000 行，SIM20260918 前缀）＋ fixture 哈希。
- 数据只读：所有实算走只读事务；不建群、不改客户数据（沿用 P3 约束）。

## 5. 判定设计（程序化，与 Agent 协议解耦）

### 5.1 解耦层

```
Agent 公开产物(result.plan / outcome / questions)  ← API 契约（v2）
        │  adapter.py（唯一允许知道 Agent 词表的模块，版本化）
        ▼
评测侧标准树（自有 schema，不随 Agent 演化）
        │  tree.py 数学规范化（继承 judge.py 已证明的等价类）
        ▼
与 expected.tree 比较 → 维度分
```

等价类（沿用并扩展 `judge.py` 已验证的规则）：同级 AND/OR 扁平化排序、码值集合排序、数值格式、单值集合、区间展开、同向数值边界蕴含、单位归一。

### 5.2 六维评分（每案例一行）

| 维度 | 含义 | 说明 |
|---|---|---|
| `outcome` | 终态正确 | READY / NEEDS_USER_INPUT / CAPABILITY_GAP 与该案例期望一致 |
| `tree` | 条件树等价 | 规范化后逐项相等（含漏条件、AND/OR 改变、错阈值、错字段检测） |
| `caliber` | 口径无显式矛盾 | 只判显式矛盾，不因未复述口径而失败（沿用现行规则） |
| `clarify` | 澄清行为正确 | 该问必问（槽位覆盖）；不该问未问；options 合规 |
| `gap` | 缺口原因正确 | 映射到该案例 gap 要求 |
| `idset` | 完整 ID 集相等 | L3；仅 READY 案例 |
| **`pass`** | **主指标** | `outcome ∧ tree`（严格完整）；其余维度仅诊断，不参与主指标 |

不采信 Agent 自报的 `valid` / `plan_status` / `diagnostics`。

### 5.3 三层执行与失败分类

- **L1（免费）**：树原子条件 → 中文短语 → `/retrieve_batch`（k=20）→ 目标标签是否进 top-K；每案例附 `l1_recall` 列。
- **L2（付费）**：runner 产出结果即判。
- **L3（确定性）**：READY 案例走 Java 权威链（`/taglibrary/agent/plan/compile` → `/objectgroup/group/run`）取 COUNT 与完整 ID 集，与 oracle 比对；COUNT 相同仍必须比 ID 集。
- **失败分类**（每一行必带）：`ok` / `timeout`（硬超时）/ `error`（harness 或模型服务故障）/ `refusal`（安全拒绝，独立成列）。超时与 error 进 `errors.jsonl`，不占 (case, rep) 语义位，但计入成本与稳定性统计。

## 6. Runner 设计

基于 `tagpilot-agent/scripts/evaluate_workbench.py` 已验证的模式扩展：

| 属性 | 设计 |
|---|---|
| 驱动 | 默认 HTTP → 隔离实例 `:8093`（生产等价：认证/契约/并发控制）；`--inproc` 进程内直驱（离线/CI，复用 RunManager） |
| 固定三元组 | 启动时读快照 manifest，冻结 `snapshot_id/build_id/artifact_hash/eligible`，运行结束核对 |
| run_id | `bench-{suite}-{case}-r{rep}-{batch8}`，每次运行唯一批次号（规避 Agent 幂等陷阱） |
| reps | 默认 2（smoke 3）；报告输出每案例重复与一致性 |
| 并发 | 默认 2（Agent 服务上限），可调 |
| 超时 | per-case 硬顶 180s，独立于流活性；超时进 `errors.jsonl` |
| 重试 | 429/5xx 抖动退避 ≤2 次；记录 retry_count；失败尝试全部计费 |
| 落盘 | `results.jsonl` 逐案例追加；`traces/{case}_r{rep}.json` 全量交换；`errors.jsonl` 追加 |
| resume | 按 (case, rep) 幂等跳过 |
| 预算 | `--budget-usd` 硬闸门（付费命令必须显式给出） |

## 7. 报告与差分

- `summary.json`：主指标 pass 率 ± Wilson 95% CI；六维度分解；按 `tags[0]` / `difficulty` / `source` 分组；成本、延迟（p50/p95）、超时率、降级分层（budget 收尾 vs 真故障分开）。
- `report.html`：用 `build-report-lite.mjs`（15 KB 单文件，拷入 `bench/tools/` 以保证自包含），生成排序表格与逐案例链接。
- 差分：`baseline/` vs `v1/`… 目录约定；`compare` 输出逐案例变化（改善/回归/不变）+ 主指标差值 vs 噪声地板。

## 8. 目录布局与命令

```
tagpilot-bench/
├── README.md
├── cases/
│   ├── core/    cases.jsonl  oracle.jsonl  manifest.json
│   ├── guard/   cases.jsonl  manifest.json
│   └── smoke/   manifest.json（引用 core/guard 的 case_id 列表）
├── bench/
│   ├── runner.py        # 驱动 + reps + 落盘 + resume
│   ├── adapter.py       # Agent 产物 → 标准树（唯一协议耦合点，版本化）
│   ├── tree.py          # 条件树 schema + 数学规范化
│   ├── grade.py         # 六维判定
│   ├── l1.py  l3.py     # 语义层 / 执行层判定
│   ├── report.py        # summary.json
│   └── compare.py       # 差分
├── tools/
│   ├── build_cases_61.py    # 61 文档 → 结构化（一次性，产物入 cases/）
│   ├── build_oracle.py      # 树 → MySQL 实算 → ID 集 + 人数对账
│   └── build-report-lite.mjs
├── runs/<suite>/<variant>/   # baseline, v1, ...（traces 与 report.html 不提交）
│   ├── results.jsonl  errors.jsonl  traces/  report.html  summary.json
└── docs/case-authoring.md    # 金标撰写与对账规范
```

命令（示意）：

```bash
# 内环：改一次跑一次
PYTHONPATH=tagpilot-bench ../tagpilot-agent/.venv/bin/python -m bench.runner \
  --suite smoke --reps 3 --budget-usd 15 --variant v3

# 外环：发版前
PYTHONPATH=tagpilot-bench ../tagpilot-agent/.venv/bin/python -m bench.runner \
  --suite core --reps 2 --budget-usd 60 --variant v3

# 报告与差分
node tagpilot-bench/tools/build-report-lite.mjs tagpilot-bench/runs/core
```

## 9. 成本与分辨率

按实测 $0.135/案例、p50 16.2s / p95 90.6s（并发 2）：

| 档 | 规模 | 预估成本 | 预估墙钟 | 主指标噪声地板 |
|---|---|---|---|---|
| smoke | 13 × 3 reps = 39 runs | ≈ $5 | ≈ 15 分钟 | ±16pp（仅粗筛） |
| core | 165 × 2 reps = 330 runs | ≈ $45 | ≈ 1.5–2 小时 | ±5.5pp |

（首跑后用实测 `usage` 修正；预算触顶即停，如实记录。）

## 10. 实施阶段

| 阶段 | 内容 | 交付物 |
|---|---|---|
| P1 案例集 | 61 结构化 + 100 复用校验 + oracle 实算 + 人数对账；抽样人工复核 | `cases/*` + 对账报告 |
| P2 判定器 | adapter/tree/grade 实现；正反例测试（已知正确/等价改写/错阈值/漏条件/伪造 valid） | 判定单元测试全绿 |
| P3 Runner | HTTP/inproc 双驱动、reps、落盘、resume、预算闸门 | pilot 5 案例全链产物 |
| P4 基线 | smoke → core 首跑 → 报告 → 签收 | `runs/core/baseline/{report.html,summary.json}` |

每阶段完成即停下等签收；P4 首跑前重跑 `eval-audit` 自检（见 §12）。

## 11. 旧体系处置

- `tagpilot-eval/` **原地冻结**为证据仓库：README 顶部加一行标注"历史证据，评测体系已迁移至 tagpilot-bench"，其余不动（P0–P3 冻结哈希、reviews、runs 保持原样）。
- 提取到新体系的三件（均为重写或改写，不做跨包 import）：等价类规范化规则（源自 `judge.py`，独立实现并保留其对抗性测试用例集）、树解释/ID 集比对逻辑（源自 `oracle.py`）、契约 schema 参考（`schemas/`）。
- 不做：删除旧目录、改动旧冻结产物。

## 12. 验收自查（对齐 eval-audit 检查表）

- [ ] **Oracle/Null 测试**：标准树自身过判定应 100% PASS；空输出/常量输出应全 FAIL；判定对"空集正确"与"跑不动"必须区分
- [ ] **人数对账**：61 案例实算人数 = 文档人数（target/contrast/prefix），不符项归因清零
- [ ] **金标来源透明**：每条案例 `provenance` 标注树与 oracle 的作者与校验方式；61 树为文档结构化、100 树为 P3 原值
- [ ] **噪声地板**：core × 2 reps 的 pass 率 CI ≤ ±6pp；小改动（<6pp）不做结论
- [ ] **失败不混计**：timeout/error/refusal 独立于语义失败；成本含失败尝试
- [ ] **端状态判定**：L3 判完整 ID 集（非 transcript、非 COUNT 单项）
- [ ] **可复跑**：runner/案例集/判定三方版本与哈希一同冻结；baseline 可逐字节复现（除模型随机性）
- [ ] **差分可见**：任一 variant 与 baseline 的逐案例变化可查
- [ ] **标准树不可达**：cases.jsonl/oracle.jsonl 不进 Agent 任何可见输入；本机隔离

## 13. 未决事项（待实现期确认）

1. `tagpilot-bench` 目录名（备选：`tagpilot-measure`）
2. L3 在 core 全量跑的成本（Java 编译 + COUNT + ID 集）——P3 实测 100 案例可承受，core 需复测
3. smoke 子集最终 13 条的选择（P1 完成后给用户确认）
4. 61 案例"口语"列（每案例第二表达）是否作为独立变体入 core（现设计：保留字段，暂不拆独立案例）
