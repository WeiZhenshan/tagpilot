# TagPilot 文档导航

全项目文档的统一入口。

导航关系：

```
README.md            项目概览与快速开始（仓库根目录）
    ↓
docs/README.md       本文件 —— 全部文档导航
    ↓
architecture/ design/ plans/ development/ ……   各类详细文档
```

数据库脚本不放在 `docs/` 下，见 [`../sql/README.md`](../sql/README.md)。

---

## 一、集中管理的文档（`docs/`）

### 架构 `docs/architecture/`

| 文档 | 类别 | 所属模块 | 路径 | 用途 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 标签系统核心功能模块详解 | 架构 / 模块说明 | 全局 | [`architecture/标签系统核心功能模块详解.md`](architecture/标签系统核心功能模块详解.md) | 统一标签管理系统的定位与四大核心模块（数据代理 / 标签库 / 对象群 / 审批流程）的功能定义与机制 | 现行 |

### 设计 `docs/design/`

| 文档 | 类别 | 所属模块 | 路径 | 用途 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 数据代理模块-数据源管理开发文档 | 详细设计 / 开发文档 | databroker | [`design/数据代理模块-数据源管理开发文档.md`](design/数据代理模块-数据源管理开发文档.md) | 数据源管理模块的应用架构、Maven 模块调整、数据库设计、菜单权限、后端接口设计 | 现行 |
| 标签系统数据链路评估与优化方案 | 技术方案 / 评估报告 | databroker + taglibrary + objectgroup | [`design/标签系统数据链路评估与优化方案.md`](design/标签系统数据链路评估与优化方案.md) | 数据流向总览、删除链路依赖保护缺失的 P0/P1/P2 问题与优化方案 | 部分落地：P0-5 → `sql/migration/V20260905_01__tag_system_del_flag_widen.sql`；P0-6 → `sql/maintenance/cleanup_orphan_data.sql` |
| 标签语义层与检索索引建设方案 | 架构方案 / 详细设计 | taglibrary + AI Runtime | [`design/标签语义层与检索索引建设方案.md`](design/标签语义层与检索索引建设方案.md) | 标签智能体模块 A 基础数据架构：`ts_*` 语义层（概念/族/结构化口径/别名/码值语义/易混淆/词典）、`TagCatalogSnapshot` 版本快照、Milvus Standalone 索引（BM25 + 向量 + 标量过滤 + 别名切换）与构建流水线、评测与治理 | 现行方案（2026-09-16，待评审） |
| 标签语义层与检索索引建设方案 v1（本地索引版） | 架构方案 / 历史版本 | taglibrary + AI Runtime | [`design/标签语义层与检索索引建设方案-v1-本地索引版.md`](design/标签语义层与检索索引建设方案-v1-本地索引版.md) | 同上方案的首版：索引层采用 numpy 内存向量矩阵 + rank_bm25 本地产物、不引入向量数据库；语义层设计与现行版一致 | 历史参考（已被 Milvus 版取代） |

### 计划 `docs/plans/`

| 文档 | 类别 | 所属模块 | 路径 | 用途 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 标签库批量映射同步优化计划 | 实施计划 | taglibrary | [`plans/标签库批量映射同步优化计划.md`](plans/标签库批量映射同步优化计划.md) | 版本同步、元数据审核、中文码值展示改造方案与实施顺序 | 已确认（文档内标注 2026-09-05）；对应结构迁移已收录于 `sql/migration/V20260905_02/_03`，测试数据见 `sql/seed/tag_mapping_test_data.sql` |

### 开发 `docs/development/`

| 文档 | 类别 | 所属模块 | 路径 | 用途 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 若依环境使用手册 | 开发环境 / 部署指南 | 全局 | [`development/若依环境使用手册.docx`](development/若依环境使用手册.docx) | 若依系统开发环境搭建（Maven、Eclipse、数据库与日志配置）、启动验证、war/jar 部署 | 现行（注意：文内指向的初始化脚本名为旧版 `sql/ry_20180423.sql`/`quartz.sql`，当前初始化脚本为 `sql/init/ry_init.sql`） |

### 工作流固定路径（保留在 `docs/superpowers/specs/`）

superpowers 工作流按约定把计划与规格写入 `docs/superpowers/{plans,specs}/`，**不可移动**，否则工作流将找不到它们。下列设计规格是这两个模块长期有效的设计依据，请勿删除（已完成的逐任务施工计划在本轮清理中移除，设计知识均由这些规格承载）。

| 文档 | 类别 | 所属模块 | 路径 | 用途 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| databroker-datasource 设计规格 | 设计规格 | databroker | [`superpowers/specs/2026-07-05-databroker-datasource-design.md`](superpowers/specs/2026-07-05-databroker-datasource-design.md) | 数据源管理设计规格（架构、5 张表、接口契约、菜单权限、加密方案） | 现行 |
| databroker-dataset 设计规格 | 设计规格 | databroker | [`superpowers/specs/2026-07-23-databroker-dataset-design.md`](superpowers/specs/2026-07-23-databroker-dataset-design.md) | 数据集管理设计规格（definition_json 格式、版本状态机、端点契约、前端布局） | 现行 |
| taglibrary 设计规格 | 设计规格 | taglibrary | [`superpowers/specs/2026-07-23-taglibrary-design.md`](superpowers/specs/2026-07-23-taglibrary-design.md) | 标签库模块设计规格（数据表设计、状态机、接口契约、字段快照同步、菜单 SQL） | 现行 |

### 文档资源 `docs/images/`

| 资源 | 路径 | 被谁引用 |
| :--- | :--- | :--- |
| TagPilot 徽标 | [`images/tagpilot-logo.png`](images/tagpilot-logo.png) | 根目录 `README.md`（HTML `<img>`，请勿移动） |

---

## 二、保留在固定位置、未集中到 `docs/` 的文档

以下文档因工具、GitHub 或模块约定必须留在原位置。**不要把它们的副本放进 `docs/`。**

### 仓库根目录

| 文档 | 类别 | 路径 | 用途 | 为何保留原位 |
| :--- | :--- | :--- | :--- | :--- |
| README.md | 项目概览 | [`../README.md`](../README.md) | 项目第一入口：简介、核心模块、技术栈、快速开始 | 约定俗成的仓库第一入口 |
| AGENTS.md | Agent 工作区指南 | [`../AGENTS.md`](../AGENTS.md) | ZCode / Claude 等 Agent 的工作区指令：模块布局、构建运行、关键陷阱、编辑约定 | Agent 工具按约定读取根目录 |
| CLAUDE.md | Agent 项目指令 | [`../CLAUDE.md`](../CLAUDE.md) | Claude Code 的架构说明与命令约定 | Agent 工具按约定读取根目录 |
| PRODUCT.md | 产品设计上下文 | [`../PRODUCT.md`](../PRODUCT.md) | 用户画像、产品目的、品牌性格、设计原则与反例 | 设计类工具从仓库根目录读取 |
| LICENSE | 许可证 | [`../LICENSE`](../LICENSE) | MIT（基于 RuoYi-Vue） | GitHub 规范位置 |

### 模块目录

| 文档 | 类别 | 路径 | 用途 | 为何保留原位 |
| :--- | :--- | :--- | :--- | :--- |
| ruoyi-ui/README.md | 模块 README | [`../ruoyi-ui/README.md`](../ruoyi-ui/README.md) | 前端模块的克隆、安装、开发、发布命令 | 就近描述本模块如何运行，靠近代码更易维护 |

### Agent / IDE 工具目录

`.claude/`、`.impeccable/` 等工具目录只保留工具配置（如 `.claude/launch.json` 的开发服务器启动配置），**不存放文档**。历史会话级计划与一次性执行报告已在本轮清理中移除；这些目录由各自工具在下次运行时按需重建。

---

## 三、相关工程配置（非文档，固定位置）

以下文件不是文档，但属于同一套数据库/部署流程的入口，排障时常用：

| 文件 | 用途 |
| :--- | :--- |
| [`../bin/db-migrate.sh`](../bin/db-migrate.sh) | 增量迁移执行器，遍历 `sql/migration/V*.sql` 并记录到 `schema_migration` |
| [`../.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) | 唯一的 CI 流水线：构建 jar + dist → 执行迁移 → 发布到 `/opt/tagpilot/releases/` 并健康检查/回滚 |
| [`../dev.sh`](../dev.sh) | 本地一键启停前后端 |
| [`../sql/README.md`](../sql/README.md) | 数据库脚本统一索引 |

---

## 四、不属于文档的文件（避免误判）

| 文件 | 实际用途 |
| :--- | :--- |
| `ruoyi-admin/src/main/resources/banner.txt` | Spring Boot 启动时打印的 ASCII 艺术字横幅 |
| `ruoyi-ui/public/robots.txt` | 前端站点的搜索引擎爬虫配置 |
| `ruoyi-generator/src/main/resources/vm/sql/sql.vm` | 代码生成器的 Velocity 模板，不是数据库脚本 |

---

## 五、目录职责与新增约定

| 目录 | 职责 |
| :--- | :--- |
| `architecture/` | 系统整体架构、技术架构、模块架构、数据架构、架构决策 |
| `design/` | 详细设计、模块设计、功能设计、技术方案、数据模型设计、接口设计 |
| `plans/` | 项目计划、实施计划、Roadmap、迁移/重构计划 |
| `development/` | 本地开发环境、开发指南、编码规范、工程规范、模块开发说明 |
| `superpowers/` | superpowers 工作流固定产物目录，**不要手工往里放东西** |

只创建有实际文档的目录；某个分类暂时没有文档就不要创建空目录。跨模块、项目级的文档放 `docs/`；模块自身的运行说明留在模块根目录。


### 语义索引层实施与验收（2026-09-19）

- [补齐任务清单](design/语义层与索引层补齐任务清单.md)：按完整验收口径回填，未完成项保持显式。
- [建设验收记录](validation/语义索引层建设验收记录.md)：实测数据、代码交付、偏差与待业务/模型/生产验证项。
- [运行与恢复说明](../ai-runtime/README.md)：外部服务连接、认证、冻结复核发布、备份重建与封存评测。
