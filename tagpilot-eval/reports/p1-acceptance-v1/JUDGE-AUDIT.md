# 裁判与数据解析复核（收尾第 2 项）

范围：`oracle.py`（条件树解释与裁判）、`judge.py`（终态级裁判）、`sources.py` 与 `inventory.py`（来源解析）。
方法：对抗性探针 + 反例测试（`tests/test_judge_audit.py`，31 例）。目标只有一个——**裁判会不会把错误答案判对，解析会不会静默读错**。

## 结论摘要

| 面 | 结论 |
|---|---|
| 条件树裁判（false pass） | **不会**。`PASS` 要求 `normalized()` 结构相等；`normalized` 完全由标准树决定，结构相等即语义相等，不存在"结构不同却判过"的路径。 |
| 条件树裁判（false fail） | 已把**有数学依据**的等价类并入标准化：同级 AND/OR 扁平化与排序、码值集合排序、数值格式统一、**单子节点分组 ≡ 其子**、**between[a,b] ≡ (≥a 且 ≤b)**、**= x ≡ in[x]**、**!= x ≡ not_in[x]**。不在此列的等价（如 `not_in[A,B]` 与 `!=A 且 !=B`）仍判失败，不猜测。 |
| 终态裁判（false pass） | 复核发现**此前根本没有终态裁判**：READY/澄清/缺口的处置完全未判。这是真正的假通过面，已补 `judge.py`。 |
| 解析器 | 靠分母校验兜底（969/970/2000/1723），未知 SQL 字面量一律抛错不猜测；发现并修复 1 处潜在崩溃。 |

## 逐项发现

**F1 树级裁判不存在假通过（已用属性测试固定）**
`Tree` 为 `extra='forbid'`，`normalized()` 做上述规范化后，`normalized(a) == normalized(b)` ⟹ 两树可证明等价。任何语义扰动（改阈值、改操作符、改绑定、改字段、调换 between 端点、去掉一侧边界）必判 FAIL。

**F2 探针覆盖有上限，但已显式化而非静默**
`boundary_rows` 在组合数 > 4096 时退化为"基线 + 单字段扰动"。这是覆盖度限制，不是假通过来源（F1 已保证结构不同必失败），但会让**证据强度**下降。已加测试固定该上限行为，运行报告须展示探针数。

**F3 终态层是真正的假通过面——已补齐**
`judge.grade_case` 现在独立判定：
- `outcome_expected`（READY/NEEDS_USER_INPUT/CAPABILITY_GAP/PARTIAL 是否符合案例定义）；
- READY：结构等价 + 完整 ID 集相等（不是只比人数）+ 口径一致性 + 无多余反问；
- NEEDS_USER_INPUT：必填槽位是否被问、是否发出 interrupt；
- CAPABILITY_GAP：缺口原因是否落在案例声明的 `gap_codes` 映射内。
裁决不采信 Agent 的 `valid` / `plan_status` / `diagnostics`；`valid:true` 但结构不符照样 FAIL（反例 `forged_valid_flag`）。

**F4 计划翻译器不再忽略 `value_scale`；口径只判结构化矛盾**
Agent 用 `values:["10"], value_scale:10000` 表达 10 万元。翻译器此前直接取 `"10"`，会把正确答案判错；已按 scale 归一。
口径检查只比较**结构化**时间/统计字段（anchor 类型、窗口、偏移、日历模式、端点、统计方式），**排除 `time_anchor_label` 这类展示文案**——实测 Agent 写"当前"、快照写"当前时点"属同义，按文比对会产生 13 处伪冲突。未声明口径不判失败（口径由标签身份确定），仅记 `evidence.caliber_declared`。

**F5 解析器修复 1 处潜在崩溃**
`inventory` 读取旧字段字典的 NULL 率列时对空值/`—` 直接 `float()`，会抛 `ValueError` 而非给出可读错误。已改为：非数值单元格一律跳过，不参与差异比对，也不猜测。

**F6 来源分母漂移必须显式记录（由第 3 项处置引起）**
第 3 项为标签 637 补两条码值后，工作树码值分母由 **177 字段 / 1723 码值** 变为 **178 / 1725**。这使既有测试 `test_source_denominators_and_leading_zeros` 失败——属于处置的预期后果，不是回归被掩盖。
- 工作树断言更新为 178/1725（并断言 637 的码值存在）；
- 冻结事实包**仍记录观测时的已发布状态 177/1723**，漂移写入 `data/p0-v2/source-drift.json` 与 manifest 的 `source_drift`；
- 原则：事实包描述观测时的已发布状态，工作树前移只作处置记录，不回填事实包。

**F7 多轮驱动必须按被测系统契约（新消息开新 run）**
实测按"复用同一 run 续问"驱动时，20 个多轮母案例**全部失败**——不是 Agent 的问题，而是驱动方式与契约不符：只有 WAITING（待澄清）才用 `resume`，其余每条新用户消息都应以**新 run** 携带 `previous_plan` 与 `history`（与 Java 客户端一致）。修正后多轮恢复正常。判定为无效证据的问题不在裁判，而在驱动层。

## 未覆盖 / 残留风险

- 未证明任意代数等价；只证明上述已列出的等价类。这是刻意选择。
- 探针上限下的交互型缺陷在理论上仍可能逃过 `boundary_equal`，但会被 `normalized_tree_equal` 拦住（结构不同即失败），故只影响证据展示。
- 解析器仍假设码表为 6 列、模拟 SQL 显式列名；列序错误会以错误定义进入 `definition`，但会被 `PUBLISHED_CODE_MEANING_CONFLICT` 捕获。
- 口径比对依赖 Agent 显式声明的结构化字段；未声明时不做推断（记录但不判失败）。
- 以上均为离线证据。真实 Java 编译/执行未接入（本轮 L3 = NOT_APPLICABLE）。
