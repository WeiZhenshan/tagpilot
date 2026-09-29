# TagPilot 评测 P2 验收（首期评测冻结）

数据集版本 `p2-cases-v3`（1994 条）；活动快照 `L107-20260919-002`；索引 `bge-m3-l107-20260919-002-r3`。

## 1. 数据集

- 母案例 500，正式案例 1994（每母案例 4 条：1 条配方原话 + 3 条模型改写）
- 类别配额：{'SINGLE': 600, 'COMPOSITION': 500, 'CLARIFICATION': 300, 'BOUNDARY': 200, 'MULTITURN': 200, 'GAP': 194}
- 分区：{'REGRESSION': 407, 'DEV': 1389, 'HOLDOUT': 198}
- 终态分布：{'READY': 1440, 'NEEDS_USER_INPUT': 340, 'CAPABILITY_GAP': 214}
- 覆盖标签：359

## 2. 改写核对与复核

- 回译核对：{'PASS': 1002, 'BACK_TRANSLATION_UNAVAILABLE': 73, 'BACK_TRANSLATION_NOT_APPLICABLE': 425}
- 隔离改写：2 条
- 独立复核结论：{'ACCEPT': 1929, 'REVISE': 32, 'UNAVAILABLE': 33, 'QUARANTINE': 6}

## 3. L1 检索与消歧

- 样本 1296 例、1880 个原子条件；k=20
- 原子条件 Recall@20 = **0.9907**（目标 ≥0.98）；全条件覆盖 1284/1296
- 分区：['DEV', 'REGRESSION']；HOLDOUT 是否排除：True
- 未全覆盖：['CAL-1034', 'CAL-1131', 'CAL-1354', 'CAL-3100', 'CAL-3101', 'CAL-3102', 'CAL-3391', 'CAL-3392', 'CAL-3393', 'CAL-4060', 'CAL-4061', 'CAL-4062']

## 4. L2 Agent 基线（真实运行）

- 运行 542 次；抽样 500 条；稳定性复跑计划 100 条×3，实际执行 42/300 次
- 抽样判定：{'PASS': 398, 'FAIL': 101, 'RUN_INVALID': 1}
- 分层（类别）：{'BOUNDARY': {'cases': 47, 'pass': 34, 'fail': 13, 'run_invalid': 0}, 'CLARIFICATION': {'cases': 71, 'pass': 68, 'fail': 3, 'run_invalid': 0}, 'COMPOSITION': {'cases': 129, 'pass': 108, 'fail': 20, 'run_invalid': 1}, 'GAP': {'cases': 50, 'pass': 22, 'fail': 28, 'run_invalid': 0}, 'MULTITURN': {'cases': 50, 'pass': 44, 'fail': 6, 'run_invalid': 0}, 'SINGLE': {'cases': 153, 'pass': 122, 'fail': 31, 'run_invalid': 0}}
- 分层（分区）：{'DEV': {'cases': 386, 'pass': 310, 'fail': 75, 'run_invalid': 1}, 'REGRESSION': {'cases': 114, 'pass': 88, 'fail': 26, 'run_invalid': 0}}
- 成本（SDK 估值）：73.0431；停止原因：PROCESS_STOPPED_AT_BUDGET_CAP

## 5. 覆盖报告

- 标签：{'total': 969, 'source_confirmable': 960, 'unresolved': 9, 'expressible_in_a_standard_tree': 273, 'with_execution_sample': 273, 'appearing_as_target': 359}
- 码值字段：{'total': 177, 'covered_as_target': 162, 'target': 177, 'status': 'NOT_MET', 'shortfall': 15}
- 码值校验：MET（1723/1723）

## 6. 失败根因

- 未通过 114 例；其中**硬超时 28 例、无效运行 1 例单列**，不计入语义归因分母（513）
- 证据不足以归因：0 例（不硬凑原因）

| 根因簇 | 影响母案例 | 严重度 | 处理方向 |
|---|---:|---:|---|
| OUTCOME | 65 | 2 | 终态判断错误（该澄清却作答、该报缺口却给条件） |
| SOURCE_FACT | 9 | 3 | 来源定义或码表冲突未解决 |
| TIMEOUT | 26 | 1 | 运行超过单题时限（预算/收敛问题，不是语义不足） |
| CODE_UNIT_ENDPOINT | 2 | 2 | 码值、单位或区间端点错误 |
| DISAMBIGUATION | 2 | 2 | 用了易混淆的其它标签（当前/历史、本行/他行、累计/最高）：补易混淆关系与候选关联 |
| RETRIEVAL_MISS | 2 | 2 | 目标标签未进入检索前 K：先看别名与概念关联是否缺失 |
| CLARIFICATION_BEHAVIOR | 1 | 1 | 澄清槽位未被问到或问了不该问的 |
| RUN_INVALID | 1 | 1 | 环境、裁判或鉴权问题；不计入语义归因 |

## 7. 未达标与限制（如实列出，不做隐藏）

| 项 | 状态 | 说明 |
|---|---|---|
| L2 稳定性复跑 | NOT_MEASURED | 计划 100 条×3 = 300 次，实际执行 42 次（预算上限 $150 用尽后停止）。方案 §五.3 的「三次运行语义一致率 ≥90%」本轮**无证据**，不作推断、不给近似值。 |
| 回译独立核对 | PARTIAL | 改写中通过回译核对 1002 条；其余为结构上无法比对（澄清/缺口/派生/全客群）或推理吃满 token，已分别计数。 |
| 码值字段覆盖 | NOT_MET | 覆盖 162/177；差额已列出未覆盖清单。 |
| 每标签至少出现在 2 个母案例 | NOT_MET | 该义务按 10,000 条档写成；2,000 条档的母案例数供不出全部 969 个标签各两次。 |
| AI 复核未产出结论 | 33 条 | 复核模型未返回可解析 JSON；标记保留、不冒充已复核。 |
| AI 复核要求修改但未给改法 | 32 条 | 复核员判定不忠实或语气不自然但未给出具体改法；按设计保留并计数，转 P3 改进。 |
| L1 未全覆盖案例 | 12 例 | 未进入 top-K；同一母案例的多条改写同时失败，指向标签消歧而非改写抖动。 |
| L3 Java 执行 | NOT_APPLICABLE | 本轮未接入隔离的 Java 编译/执行路径，不计入通过分母。 |

## 8. 版本清单

| 工件 | sha256 |
|---|---|
| 事实包 manifest | `25f005e766a51837…` |
| 事实清单 facts.jsonl | `2fcdd070e4d049a7…` |
| 根因报告 diagnosis.json | `e0c550d51a3914df…` |
| 母案例 cases.jsonl | `d45065bb06128334…` |
| 分区 manifest | `25ace69efa2cefdb…` |
| 模型改写 variants.jsonl | `e05f7f64b2ad6d1e…` |
| 正式案例 manifest | `de88015400273b7f…` |
| 正式案例 cases.jsonl | `eef451a80264cfae…` |
| 独立复核 reviews.jsonl | `2a222bb7e95d53e2…` |
| L1 l1-summary.json | `68bd2cd1a5cd84ae…` |
| L2 l2-summary.json | `4a968a734a3b87ff…` |
| 覆盖报告 coverage.json | `c40968a8d299ab9b…` |

> 本报告冻结上述哈希对应的工件；任何后续修订必须新建数据集版本与 manifest。
