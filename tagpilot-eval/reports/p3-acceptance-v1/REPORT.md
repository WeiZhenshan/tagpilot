# TagPilot P3 语义改进与固定 100 例 Demo 实跑报告

本机 Demo 验证完成：固定 100 个案例的最后一次独立判定均通过，全部产出 READY；100/100 经真实 Java 编译、COUNT 与完整模拟客户 ID 集对账通过。仅实施 P3，没有扩充 P2 到 P4、没有生成 10,000 条数据。最终完整回放轮（v6）原始判定为 {'PASS': 100}；历次失败与复跑均保留，不挑选最好的一次。

当前采用快照 `L107-20260928-006`、build `bge-m3-l107-20260928-006-p3g`（G）。激活记录见 [active-bundle.json](active-bundle.json)，逐例最终证据见 [latest-case-evidence.jsonl](final/latest-case-evidence.jsonl)，实际查询证据见 [L3 results.jsonl](../../runs/p3-java-final-v1/results.jsonl)。此结论限固定模拟数据与开发轨迹，不代表银行业务口径签署或生产验收。

## 实施内容

三轮受控应用 v1/v2/v4 合计 186 条操作：业务概念 10、字段语义 9、别名 56、正反例 75、概念候选关联 19、业务词典 17。v3 为未应用草案。各包保留 before/after、来源、修改前 hash 和 AI 复核记录；数据库实际应用记录见 [database-audit.json](database-audit.json)，文件 hash 见 [applied-package-summary.json](applied-package-summary.json)。数据库 `source=HUMAN` 是既有策划通道枚举，实际复核人为 AI，不代表人工或银行签署。

- 补齐金额累计/单笔最高、信用卡张数、最低利率、上年 12 月的结构化口径。五个累计转入字段使用 `DEMO_CONVENTION`，其余以来源字段含义核对。原 969 事实保留：963 VERIFIED_SOURCE、5 DEMO_CONVENTION、1 UNRESOLVED；637 在本轮开始前已是 DRAFT，所有 L2 对照固定排除它，新快照含 968 个已发布标签。
- 新增概念候选关联及快照 schema v2；读取端兼容 v1。关联只展开可见候选，不改变主概念/标签族、不作为等价命中。正反例与别名在既有 tpl1 文档和详情中生效，未导入完整评测题到向量库。
- 新增 Java `changeset/validate` 与 `changeset/apply`：白名单字段、基线/修改前 hash、事务锁、幂等与审计；应用、发布和激活分开。迁移为 `V20260928_01__semantic_p3_changeset_relation.sql`，本机已记录到 schema_migration。
- 后续单独版本化 NFKC 别名解析、具体字段词消歧、重排预算（k=10、max_length=512、batch_size=8），以及模型共享与候选排序保留。BGE 模型和 tpl1 模板保持原版本；共享模型仍按模型内容 hash 隔离。旧 manifest 的 rerank_k=50 原运行端实际使用环境默认 30，旧版保持该行为，G 使用明确的 manifest-v1 预算。
- 为本轮阻断问题补充必要 Agent/Guard 修复：候选与详情压缩保留码值/口径、日期端点原子校验、逐字来源与明确字段保护、需求 ID 一致性、未确认假设逐项提问、经理行动安排不生成客群条件、月份字段名等价归一化。多轮冻结、资格、阈值和 Java 权威编译继续生效；默认 SDK 轮数由 10 调至 16，单次硬时限仍为 90 秒。

## 根因与回归处置

P2 实际提供 8 个根因簇，方案规定“最多 20 个”，本轮按实际簇处理。来源为 [P2 diagnosis](../p2-diagnosis-v3/diagnosis.json)。

| 根因簇 | P2 影响母案例 | 本轮处理与边界 |
|---|---:|---|
| OUTCOME | 65 | 模糊词保留 ASK，明确独立产品字段消歧；不把缺阈值当能力缺口。100 Demo 轨迹逐轮验证，不推断其余 65 母案例全部修复。 |
| SOURCE_FACT | 9 | 8 个字段修订，SUM 标为 Demo 约定；既有 DRAFT 637 保持排除。 |
| TIMEOUT | 26 | 重排配置/共享模型、观察预算、SDK 轮数及澄清收敛分别处理，超时记录保留。 |
| CODE_UNIT_ENDPOINT | 2 | 持有标志按 0/1 码值；日期端点、单位倍率与月份校验。 |
| DISAMBIGUATION | 2 | 当前/历史、累计/最高、理财/基金风评分别绑定；“账上”需要范围澄清。 |
| RETRIEVAL_MISS | 2 | 全角符号 NFKC 解析恢复原 12 个 L1 未全覆盖案例；候选排序保留。 |
| CLARIFICATION_BEHAVIOR | 1 | 对真正的缺口径/阈值提问；明确字段不产生默认定义假设。 |
| RUN_INVALID | 1 | 鉴权/环境与语义失败分开；早期 637 资格摘要不一致单列无效运行。 |

首个完整 G 轮（full-v2）为 98 PASS / 2 FAIL：CAL-8048 首轮未询问资产范围却冻结暂定 AUM>0；CAL-8062 将经理“这周准备跟进”误加为筛选条件。修复后追加回放又暴露 CAL-8076 的需求 ID 不一致，最终统一 ID 与修复提示。回归对照另发现 CAL-1001 的 month/月金额识别与发布 month_of_year 不一致，以及 CAL-1076 将明确授信状态泛化成速易贷状态；均经真实模型复测通过。

裁判也作了独立修正：多轮首轮 PASS 不能覆盖末轮失败/PARTIAL；AND 内完全同字段/单位/口径/NULL 策略的同向边界允许数学蕴含归一化；合并口径/阈值提问需明说阈值且提供数值边界选项。错阈值、错字段、错口径、AND/OR 改变、仅问窗口均有失败反例。旧证据不覆写，早期再判定见 [p3-regrade-v1](../p3-regrade-v1/summary.json)。

## 固定对照与留出

| L1 版本 | 语义/配置 | 召回原子条件 | 全条件覆盖案例 |
|---|---|---:|---:|
| A | 原语义/原配置 | 1868/1880（99.3617%） | 1284/1296 |
| B | 第一轮新语义/原配置 | 1868/1880（99.3617%） | 1284/1296 |
| C | 原语义/NFKC | 1880/1880（100%） | 1296/1296 |
| D | 第一轮新语义/NFKC | 1880/1880（100%） | 1296/1296 |
| G | 选定语义/配置，DEV+REGRESSION | 1880/1880（100%） | 1296/1296 |
| G | HOLDOUT 单独检查 | 200/200（100%） | 128/128 |

A/B 纯数据改动的 L1 净收益为 0，无回归；12 个召回缺失的恢复来自 NFKC 配置。口径修订的收益由 L2/L3 验证，不能声称 A/B 召回提升。以上 L1 为 fast/no-rerank@20，不代表 deep@10 的留出正确率。198 个 HOLDOUT 中 128 例具有本层可评估标签条件，其余 70 例不进入该分母；留出只读聚合，不用于语义补丁。P2 旧报告的 atomic 指标实际为案例平均，P3 按原始 recalled 数组计算微平均，不改旧报告。

最终 L2 固定 15 例旧回归对照，模型 deepseek-flash、提示、案例 hash、资格 hash、日期相同：A=14/15，G=15/15，无新增回归；A 的 CAL-1001 因旧口径缺 12 月信息返回 CAPABILITY_GAP。p95：A=81.242s，G=18.293s。该对照比较选定语义+配置，共用最终 Agent 修复，不归因为纯数据增益。详见 [L1 comparison](l1-controlled-comparison.json)、[L2 comparison](l2-final-controlled-comparison.json)。

## 100 个客户经理案例与真实执行

[完整原话、预设后续消息和期望人数](DEMO_CASES.md)；[案例 JSONL](../../data/p3-demo-100-v3/cases.jsonl)。五种表达为标准、口语、省略、模糊澄清、指代追加。40 个多轮案例（24 澄清、16 追加），共 140 条用户消息；全部为 DEV。100 个唯一原话/母案例 ID，40 个谱系组，覆盖 15 个目标字段，不能当作 100 个独立业务定义或全标签覆盖。初始终态为 76 READY / 24 NEEDS_USER_INPUT，补充后全部期望 READY。

真值先由来源与固定 fixture 构造，独立条件树/完整 ID oracle 留在本机，不发送给被测 Agent。v3 仅纠正 3 个“账上还有”的首轮范围澄清预期；100 条初始原话、最终条件树及完整 ID oracle 均与 v2 一致。结构/来源/码值/口径检查 100/100 无错误；AI 编写与核对，不冒充独立外部复核或人工抽检。详见 [dataset-validation.json](dataset-validation.json)、[authoring-correction.json](../../data/p3-demo-100-v3/authoring-correction.json)。

| 业务场景 | 案例 | 最后 L2 通过 | L3 COUNT+完整ID通过 | 有客户命中的案例 |
|---|---:|---:|---:|---:|
| 大额入金转化 | 15 | 15 | 15 | 15 |
| 定期到期承接 | 15 | 15 | 15 | 15 |
| 代发客户流失预警 | 14 | 14 | 14 | 0 |
| 沉睡客户激活 | 14 | 14 | 14 | 14 |
| 基金客户配置优化 | 14 | 14 | 14 | 14 |
| 营销活动复盘 | 14 | 14 | 14 | 0 |
| 渠道迁移 | 14 | 14 | 14 | 14 |

实际链路：正式 Claude Agent SDK 服务 `/agent/v2/runs`（含 resume/新 run 追加）→ Java 权威 `/taglibrary/agent/plan/compile` → `/objectgroup/group/run` 的真实 COUNT → Java SQL 换成客户 ID 投影后在本机只读事务取得全部 ID → 独立 fixture oracle。COUNT 和完整 ID 必须都相等，不能仅看 preview 前 100 人。未创建实体客群、未修改客户记录。

额外执行 12 个 READY 回归案例的 Java COUNT 与完整 ID 对账，全部通过（包括上年 12 月保险金额）；3 个 NEEDS_USER_INPUT 回归不执行查询。正式工作台经 Java `threads/runs` 自动选用 ACTIVE G，随后权威核验、人数统计、预览全部成功，示例会话 **P3 Demo 大额入金转化验收** 返回 39 人，未创建实体客群。证据见 [Java core summary](../../runs/p3-java-core-v1/summary.json)、[workbench-smoke.json](workbench-smoke.json)。

2000 个 SIM20260918 模拟客户的 15 个目标字段与独立 fixture 全部相同，差异 0。72 个案例非空，28 个案例为空，全部来自代发预警和营销复盘；这两个场景目前可展示正确解析、澄清与空结果，缺少有命中客户的演示样本。查询结果 0 人被保留，没有放宽条件。

最终逐例延迟（含多轮，不含人工停顿）：p50=15.223s、p95=50.886s、max=79.950s；逐条用户消息延迟：p50=10.840s、p95=28.236s、max=46.697s（140 条，并发 2）。统计来自事件去重与最后运行记录，详见 [final summary](final/summary.json)。指定验收迭代共 217 次案例运行，SDK 已记录估算合计 40.693706 USD；不是 DeepSeek 账单，其他开发回放另有原始目录记录。

## 版本、复现与回滚

| 工件 | SHA256 |
|---|---|
| G snapshot content | `a261326a7ea3526fb25aa88e6625bbbf162b7d727d76060130a78698e9bb9b6e` |
| G artifact | `b21ec4e101058f4a6b558e0dbb73e7169e9797fabcb4a40142bd28bbf77f00d3` |
| G retrieval config | `d9107c6007ba89a1d9883c8479a540f24dff54acab9fe914b77c4b529519ecf4` |
| cases.jsonl | `00961b454e36ee418f7f039ae573120537ddcf4dd18005d79d66825b84c061ff` |
| inputs.jsonl | `885367c8940d4b305e2a987fdceeffa414fb63f3b33765c87e64c3452125bfd4` |
| oracle-results.jsonl | `0b03f208d884f3e393ff4980485dbaf57e74c91c4c241feb29dba1b84740971f` |

每轮目录记录模型/提示/数据/资格/build/hash、事件、token、耗时、SDK 估值和失败。最终运行源码与 jar hash 见 [runtime-final-v6.json](runtime-final-v6.json)；后续裁判/来源物化改动的 hash 另列 [delivery-manifest.json](delivery-manifest.json)。来源 gzip 逐字节补齐派生事实包，manifest、案例和 oracle hash 未变，见 [frozen-source-materialization.json](frozen-source-materialization.json)。旧索引 manifest 保持 NOT_EVALUATED 原值；报告与 Java evalSummary 分开关联。

复现命令见 [评测 README](../../README.md#p3-固定-demo-复现)。使用新输出目录创建真实新 run；同目录仅恢复未完成项。回滚经标准 Java 发布权限接口激活原 build `bge-m3-l107-20260919-002-r3`（原 snapshot `L107-20260919-002`），保留旧文件及 Milvus 集合；语义数据撤销应根据已审计 before 值提交新的前向补偿包，不删除历史。

## 检查结果与证据范围

相关检查全部通过：Java 28、Agent 97、语义引擎 24、评测包 371；后端强制 jar 构建成功；P3 相关 diff 空白检查通过。详见 [validation-evidence.json](validation-evidence.json)。Java 默认 Maven 的其它模块零测试不算覆盖；没有额外运行前端或生产容量检查。

本轮完成用户授权的 P3 本地改进与 100 例实际圈选验证。以下保持明确限制：

- 未扩量至 P4，未重跑 P2 全部 500 例 L2 根因簇；“首轮问题簇整体错误下降 ≥30%”没有全分母证据。15 例固定回归已通过，不能替代全部 407 例回归的 L2 验收。
- 留出只证明 L1 召回；未进行 L2 留出或三次全量稳定性验证。固定100轨迹通过不能保证任意新口语或每次随机运行都成功。
- 沉睡激活限定 APP 低活跃；基金配置限定持有空白/风评/资产；营销复盘限定载体活动参与；渠道迁移限定已开通手机银行和 APP 低活跃。严格无活动、基金只数/集中度、活动 ROI/因果和柜面迁移明细仍需业务定义与数据能力。
- SUM、C1–C5 等包含 Demo 约定；人工抽检与银行签署未完成。28 个空集场景的正样本补齐是独立数据工作，本轮未用数据修改制造命中。
