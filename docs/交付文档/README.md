# 交付文档

面向甲方/验收方的正式交付材料。与 `development/`（开发者自用）、`validation/`（内部实测数据）区分：本目录放的是**可以直接交出去**的成品件。

本清单对齐竞赛**「四、预期交付物」**的三大类：设计文档、可运行代码/视频、路演 PPT。下表的「现状」只描述**已经存在于仓库里的素材**，不等于已达交付质量 —— 多数条目是散落在实施记录里的章节，需要整理成独立成篇的交付文本。

状态口径：`已成稿` 有独立文档且内容完整 ｜ `有素材` 内容散在别的文档/代码里，需整理 ｜ `缺失` 尚无对应产物。

---

## 一、设计文档

| # | 交付物 | 现状 | 现有素材来源 | 缺口 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 标签元数据设计规范 | 有素材 | [`design/标签语义层与检索索引建设方案.md`](../design/标签语义层与检索索引建设方案.md)（`ts_*` 概念/族/结构化口径/别名/码值语义/易混淆/词典）；`sql/migration/V*.sql` 表结构；[`design/agent-v3/expression-contract.json`](../design/agent-v3/expression-contract.json)（字段级算子契约样本） | 独立成文的「元数据设计规范」：字段字典、枚举取值、必填与校验规则、示例数据、版本演进 |
| 2 | AudienceQueryDSL 设计文档 | 有素材 | [`architecture/标签语义引擎与Agent编排层.md`](../architecture/标签语义引擎与Agent编排层.md)（DSL 定位、合法 DSL 也不得自动执行）；`tagpilot-semantic/tag_semantic/eval/offline_selector.py` 的 `AudienceQueryDSL` 与 `validate_dsl`；`ruoyi-objectgroup` 的 `RuleSqlBuilder` 与 `IRuleSqlBuilder` | 独立成文的 DSL 规范：EBNF/JSON Schema 语法、算子与类型系统、非法用例、与对象群表达式契约的对应关系、版本兼容策略 |
| 3 | 多路召回与重排技术方案 | 有素材 | [`design/标签语义层与检索索引建设方案.md`](../design/标签语义层与检索索引建设方案.md)（BM25 + 向量 + 标量过滤、别名切换）；[`architecture/标签语义引擎与Agent编排层.md`](../architecture/标签语义引擎与Agent编排层.md)（六通道检索）；`tagpilot-semantic/README.md` | 通道权重与融合公式、重排阶段的模型与阈值、消融/对比数据、失效与降级策略 |
| 4 | 受控工作流设计文档 | 有素材 | [`development/Agent-V2实施说明.md`](../development/Agent-V2实施说明.md)、[`development/Agent-SDK重构实施记录.md`](../development/Agent-SDK重构实施记录.md)、[`development/标签上下文与客群编辑实施说明.md`](../development/标签上下文与客群编辑实施说明.md) | 一张端到端受控流程图 + 状态机（澄清/确认/回退/超时降级）+ 每步的准入准出条件与人工卡点，取代现在的三篇分散实施记录 |
| 5 | 与原系统的接口清单 | 有素材（未汇总） | 各模块 Controller：`ruoyi-taglibrary`、`ruoyi-objectgroup`、`ruoyi-databroker`；Python 侧 `tagpilot-agent`（`:8092`）、`tagpilot-semantic`（`:8091`）的 `/lookup`、`/retrieve_batch`、`/evidence`、`/capabilities` | 一份汇总表：接口名、方向、方法/路径、请求响应示意、鉴权方式、调用方、失败语义。目前没有任何接口清单文档 |
| 6 | 洞察 Skill 规范（含 Skill Manifest 与图表 Skill 规范） | 有素材 | [`development/洞察Skill体系实施记录.md`](../development/洞察Skill体系实施记录.md)；[`design/agent-v3/能力接入与验证.md`](../design/agent-v3/能力接入与验证.md)；`tagpilot-insight/schemas/`（`Manifest`、`MetricDefinition`、`MetricPlan`、`MetricQuery`、`InsightReport`） | 对外口径的 Skill 编写规范：Manifest 字段与语义、图表 Skill 的类型与入参、Guard 约束、如何新增一个 Skill；`tagpilot-insight/README.md` 偏运行说明，需另出规范正文 |
| 7 | Benchmark 评测方案 | 有素材 | [`tagpilot-eval/README.md`](../../tagpilot-eval/README.md) 与 [`reports/`](../../tagpilot-eval/reports)；方案来源见 [`plans/TagPilot 合成评测数据生成与语义层持续完善方案.md`](../plans/TagPilot%20合成评测数据生成与语义层持续完善方案.md)；内部实测见 [`validation/语义索引层建设验收记录.md`](../validation/语义索引层建设验收记录.md) | 现有 README 是工程索引，需抽取成一份自洽的《评测方案》：指标定义（Recall@k / L1 / L2）、分区与污染控制、预算与稳定性口径；须如实保留 P2/P3 已知缺口（稳定性 `NOT_MEASURED` 等） |

## 二、可运行代码 / 视频

| # | 交付物 | 现状 | 现有素材来源 | 缺口 |
| :--- | :--- | :--- | :--- | :--- |
| 8 | 黄金闭环 MVP：自然语言输入 → 标签召回与口径澄清 → 条件修改与实时预估 → 人工确认生成客群 → 洞察 Skill 库自主选场景分析与图表 → 反馈沉淀为评测样本 | 有素材（分段落已实现，闭环未整体验收） | 前端 `ruoyi-ui` 的 `/agent` 路由 + `tagpilot-assistant`（:5174）；编排 `tagpilot-agent`（:8092）；检索 `tagpilot-semantic`（:8091）；洞察 `tagpilot-insight`；反馈沉淀见 `tagpilot-eval` 的样本入库链路 | 端到端跑通记录与录制脚本；「反馈沉淀为评测样本」这一步的落地程度待核实；一键启动与依赖说明 |
| 9 | 完整代码库 | 已成稿（即本仓库） | 本仓库 `main` 对应发布版本 | 交付时需冻结版本 tag 与 commit，并说明不含内部草稿（`plans/`、`validation/`、`.claude/` 等） |
| 10 | 演示视频 | 缺失 | — | 录制脚本（分镜 + 口播）、演示账号与脱敏数据、成片 |

## 三、路演 PPT

| # | 交付物 | 现状 | 现有素材来源 | 缺口 |
| :--- | :--- | :--- | :--- | :--- |
| 11 | 亮点①：高精度自然语言检索推荐标签 | 有素材 | `tagpilot-eval` 的 L1 结果（Recall@20 = 0.9907）与 P1/P2/P3 验收报告；检索方案见条目 3 | 把指标变成「一句话结论 + 一张图 + 一个真实样例」的幻灯片，注明数据口径与版本哈希 |
| 12 | 亮点②：客群洞察 Skill 体系 | 有素材 | 条目 6 的 Skill 资料；`tagpilot-insight` 的黄金 Skill 与合成预览 | 场景选型与图表效果截图 |
| 13 | 亮点③：评测与反馈数据飞轮 | 有素材 | `tagpilot-eval` 的 P0→P1→P2→P3 版本链条与根因/覆盖报告 | 画清「线上反馈 → 样本 → 回归集 → 指标」的闭环图；须标注尚未自动化的环节 |
| 14 | 5 分钟典型业务场景演示 | 缺失 | 可复用条目 8 的 MVP | 演示剧本（含时间轴）、备用录屏（现场失败时切换）、讲稿 |

## 缺口汇总（需新产出）

1. **独立成篇的设计文档 6 篇**（条目 1–6）：现有素材是实施记录与代码注释，需按「规范」体例重写，补上字段字典、语法定义、流程图与示例。
2. **与原系统的接口清单**（条目 5）：目前完全空白，需从各 Controller 与 Python 服务反推汇总。
3. **端到端闭环验收记录 + 演示视频**（条目 8、10、14）。
4. **路演 PPT 全篇**（条目 11–14）：素材齐但未成稿，需统一视觉与口径。
5. 所有引用数据的**版本冻结**：交付文档里出现的指标必须附代码版本（分支/commit/tag）与评测版本哈希，否则不可复核。

## 命名与版本约定

- 文件名：`<文档名>-v<版本>.md`，如 `标签元数据设计规范-v1.0.md`；二进制件（PPT/视频/PDF）同名加扩展名。
- 每份文档头部标注**交付日期**与**对应代码版本**（分支/commit 或发布 tag）。
- 交付文档一经发出即为存档件，修订**新增版本**，不要原地覆盖历史版本。
- 本目录只放成品件；过程记录、调试数据留在 `plans/`、`development/`、`validation/`。
- 目录索引见 [`../README.md`](../README.md)。
