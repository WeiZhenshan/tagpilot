# Task：200 个标签圈选校准母案例（calibration-v2）

状态：P1 收尾完成。标准答案为 **DRAFT**；**独立模型复核已完成**（192 ACCEPT / 8 REVISE）；**本人人工抽检待填答**；L1/L2 已在真实链路上运行。**P2 未授权**。

## 任务与完成条件

在标签库 107 当前可见事实与固定基准日 2026-09-18 / Asia/Shanghai 下，客户经理提出一个圈选需求。理想 Agent 保留每一项明确要求，正确绑定标签、码值、单位与口径，按支持能力返回 READY、NEEDS_USER_INPUT 或 CAPABILITY_GAP。用户未确认前不执行建群；缺失字段或不明口径不允许降低条件。

本次验收范围是：冻结来源、审计 969 标签、交付 200 个母案例及四项契约、处置来源冲突、独立复核、人工抽检机制、真实运行链路（L1/L2 + 独立终态裁判 + 裁判验收套件），并确保 P2 被拦截。**不是**银行口径验收。

## 任务文件与角色边界

- `data/calibration-v2/inputs.jsonl`：首轮公开输入与固定日期，不含标准答案。
- `data/calibration-v2/cases.jsonl`：私有标准条件树、目标与禁止标签、资格列表、终态、槽位、缺口、固定多轮话术、事实引用与谱系。
- `data/calibration-v2/oracle-results.jsonl`：私有完整模拟 ID 集，仅针对指定 SQL hash（标准树未改写，沿用 v1 真值）。
- `data/calibration-v2/reviews.jsonl`：逐题独立复核结论与理由。
- `data/p0-v2/`：事实包（facts 与观测一致）+ 来源冲突处置 + 码值分母漂移。
- `reviews/independent-review-v1.jsonl`：独立复核结论（200 题）。
- `reviews/human-review-v2/human-review.html`：分层抽检 40 题，含标准树、来源证据与导出框。
- `knowledge/WORLD.md`：通用规则，不含任何题目的组合答案或人数。

## 环境与公平性

被测 Agent 运行在真实链路上（本地语义服务 + Agent 编排 + DeepSeek），使用**隔离的评测实例**，不影响开发实例。契约要求 `RunRequest.reference_date`/`timezone` 作为显式场景上下文注入，相对时间只能以基准日推算。

被测 Agent 只获得输入与其资格允许的业务事实；不能读取评测控制面。多轮回复按预定义变更脚本逐轮给出，最多四轮，不根据错误临时补造用户需求。每次运行记录代码、模型、快照、build、artifact、资格、日期、配置、耗时与成本。

## 裁判与证据

1. **L0**：核验来源 hash、引用、码值前导零、字段单位、操作符、未解决事实与资格。
2. **L1**：对标准树的每个原子条件构造短语，调用 `/retrieve_batch` 检查目标标签是否进入 top-K（k=20，fast 模式）；分母只含含原子条件的题。
3. **L2**：真实 Agent 跑批（含多轮 `resume`），由独立终态裁判判定终态、结构、完整 ID 集、口径、澄清槽位与缺口原因。判定不采信 Agent 的 `valid`/`plan_status`/`diagnostics`。
4. **裁判验收套件**：已知正确 / 等价改写 / 已知错误 / 漏条件 / 伪造 valid / 计划缺失 / 证据缺失 / 非终态。
5. **L3**：Java 执行本轮为 **NOT_APPLICABLE**，不计入通过分母。
6. 边界覆盖阈值上下与相等、NULL、零、负数、日期端点、分母为零。错误绑定、漏条件、AND 改 OR、伪造 valid 和缺失证据分别失败或 RUN_INVALID。

`FIXTURE_ORACLE_AVAILABLE` 只表示存在离线真值，不能解释为真实 Java 执行通过。9 个事实冲突以缺口暴露，禁止自动猜测累计/最高等口径。

## 本次范围的停止条件

数据集为 P1 / CALIBRATION / DRAFT，恰好 200 个母案例。正式生成、分区、P2 跑批、变更建议及应用命令均返回 SCOPE_BLOCKED。L2 跑批在本批校准题上完成并保存证据，但不据此扩大至 2,000 条，也不发布语义更改。P1 验收通过与否另行决定。
