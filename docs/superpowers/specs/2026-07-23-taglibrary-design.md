# 标签库管理模块设计文档

日期：2026-07-23（2026-07-24 修订）
状态：已确认（用户逐节批准；经规格评审修订）

> **2026-07-24 修订**：字段来源决策变更——标签库不再直接关联物理表，改为**关联数据集管理中已上线的数据集**（`dp_dataset` 默认 ONLINE 版本），字段快照取自该版本的启用输出字段（`dp_dataset_field`）。下文 §2/§3.1/§4/§5 已按新口径更新。

## 1. 背景与目标

RuoYi-Vue 项目中新增"标签库管理"模块（标签系统四大模块之二，第一个模块"数据代理"已落地为 `ruoyi-databroker`）。左侧菜单新增顶级目录**标签库管理**，下挂两个子菜单：**标签库管理**（卡片式库列表）与**标签管理**（树 + 详情页）。

样式参考三张截图（仅参考样式，数据以系统实际数据为准），并做如下微调：每个标签库卡片底部两个按钮——左侧"标签管理"直接跳转标签管理页；右侧"更多"为下拉组件，提供删除标签库、标签库标签字段管理、上下线、审批管理。

## 2. 关键决策（已与用户确认）

| 问题 | 决策 |
|---|---|
| 标签的数据模型 | **标签 = 数据集输出字段**：已上线数据集发布版本的启用输出字段（`dp_dataset_field`）作为标签来源（2026-07-24 修订，原方案为直接读取 `ind_tag_data` 宽表列） |
| 上下线/审批深度 | **状态机 + 轻量审批**：草稿→待审批→已上线⇄已下线；审批在弹窗/列表内完成，不建独立审批工作台页面 |
| 页面范围 | **只做核心**：新建、搜索、分类/标签对象筛选、卡片/列表切换、卡片操作；不做数据概览面板、批量编辑、分类管理 |
| 后端代码归属 | **新建 `ruoyi-taglibrary` Maven 模块**，与 `ruoyi-databroker` 平级 |
| 字段来源 | **关联已上线数据集**：建库时选择数据集管理中已上线（默认版本 ONLINE）的数据集，读取其发布版本的启用输出字段生成候选标签快照 |
| 总体方案 | **方案 A：元数据快照模式**——同步时列元数据快照进 `tl_tag` 表，与 databroker 的 `DpMetaColumn` 模式同构 |

## 3. 数据表设计

模块表前缀 `tl_`，沿用 RuoYi 标准审计列（`create_by/create_time/update_by/update_time/remark`）+ `del_flag`。DDL 放 `ruoyi-taglibrary/src/main/resources/sql/taglibrary_schema.sql`。

### 3.1 `tl_tag_library` 标签库

| 字段 | 类型 | 说明 |
|---|---|---|
| library_id | bigint PK auto | 主键 |
| library_name | varchar(64) | 名称 |
| library_code | varchar(64) unique | 编码 |
| category | varchar(32) | 分类，字典 `tag_library_category`（客户/产品/员工/交易/营销维度），不做独立分类管理表 |
| tag_object | varchar(16) | 标签对象，字典 `tag_object`（客户/企业/机构/商户） |
| dataset_id | bigint | 关联数据集ID（`dp_dataset`，须为已上线数据集）；dataset_name 联表回填展示 |
| owner_name | varchar(30) | 负责人 |
| status | char(1) | `0`草稿 `1`待审批 `2`已上线 `3`已下线 |

### 3.2 `tl_tag_dir` 标签目录（库内左侧树的分组）

| 字段 | 说明 |
|---|---|
| dir_id | 主键 |
| library_id | 所属库 |
| parent_id | 父目录（树形，默认 0） |
| dir_name / order_num | 名称 / 排序 |

建库时自动创建"默认目录"。

### 3.3 `tl_tag` 标签（字段快照，核心表）

| 字段 | 说明 |
|---|---|
| tag_id | 主键 |
| library_id / dir_id | 归属库与目录 |
| field_name | 源字段名（同步快照） |
| tag_name | 中文标签名；同步时用列 comment 初始化，无 comment 则用 field_name |
| data_type | 源字段数据类型（同步快照） |
| tag_type | 标签类型，字典 `tag_type`：选项型/布尔型/数值型/文本型/日期型；同步时按 data_type 推断初始值，可人工改 |
| business_caliber | varchar(500)，业务口径，可空 |
| tech_caliber | varchar(500)，技术口径，可空 |
| valid_period | varchar(32)，有效日期，默认 `永久有效` |
| update_cycle | varchar(8)，更新周期，字典（日/周/月），默认 `日` |
| create_way | varchar(8)，创建方式：`同步`（快照生成）/ `自建` |
| status | `0`草稿 `1`待审批 `2`已上线 `3`已下线，与库同构 |
| version | 版本号，编辑一次 +1 |

### 3.4 `tl_audit_log` 审批日志（库和标签共用）

| 字段 | 说明 |
|---|---|
| log_id | 主键 |
| biz_type | `library` 或 `tag` |
| biz_id | 对应主键 |
| action | 提交/通过/驳回/上线/下线 |
| from_status / to_status | 状态迁移 |
| apply_by / audit_by / audit_time / audit_comment | 申请人与审批人留痕 |

### 3.5 状态机

```
草稿 --提交审批(submit)--> 待审批 --通过(audit)--> 已上线 --下线(offline)--> 已下线
  ^                          |
  |---------驳回(audit)-------+
已下线 --重新上线 = 再次 submit--> 待审批
```

库与标签共用同一套流转。**接口收敛为三个动作**：`submit`（草稿/已下线 → 待审批）、`audit`（通过→已上线 / 驳回→原状态）、`offline`（已上线→已下线）。不单独设 `/online` 接口——重新上线即再次 submit 走审批，前端"上线"按钮对已下线对象调 submit。

删除校验：已上线/待审批的标签库禁止删除；库内仍含已上线标签时也禁止删除（须先下线标签），防止级联删除带走线上标签；删除库级联删其目录与标签。

## 4. 后端设计

模块 `ruoyi-taglibrary`，包 `com.ruoyi.taglibrary`（controller / service / service.impl / mapper / domain / domain.dto / domain.vo），路由前缀 `/taglibrary/**`，权限标识 `taglibrary:*:*`。XML mapper 放模块 `resources/mapper/taglibrary/`。接入方式照抄 databroker：根 pom 加 module + dependencyManagement，`ruoyi-admin/pom.xml` 加依赖，`application.yml` 的 `xss.urlPatterns` 加 `/taglibrary/*`。

### 4.1 标签库 `TlTagLibraryController` → `/taglibrary/library`

| 接口 | 权限 | 说明 |
|---|---|---|
| GET `/list` | `taglibrary:library:list` | 分页 + 搜索（名称/编码）+ category/tag_object 筛选；每行联表统计返回 `tag_count`（标签总数）、`online_count`（使用中/已上线）、`offline_count`（已下线）、`pending_count`（待发布=草稿+待审批），并联表回填 `datasetName` |
| GET `/datasets` | `taglibrary:library:query` | 已上线数据集列表（新建弹窗选用）：`dp_dataset` join 默认 ONLINE 版本 |
| GET `/{id}` | `taglibrary:library:query` | 详情 |
| POST `/` | `taglibrary:library:add` | 新建：校验 datasetId 必填、code 唯一 → 建默认目录 → 同步数据集字段快照（全部进默认目录、状态=草稿、create_way=同步） |
| PUT `/` | `taglibrary:library:edit` | 编辑基本信息 |
| DELETE `/{ids}` | `taglibrary:library:remove` | 删除（级联删目录/标签；已上线/待审批禁止删） |
| POST `/sync/{id}` | `taglibrary:library:sync` | 增量重新同步：新列补快照，不动已有标签状态；幂等 |
| POST `/submit/{id}` | `taglibrary:library:submit` | 提交审批（草稿/已下线→待审批） |
| POST `/audit` | `taglibrary:library:audit` | 审批（通过→已上线 / 驳回→原状态），写 `tl_audit_log` |
| POST `/offline/{id}` | `taglibrary:library:offline` | 下线（已上线→已下线），写 `tl_audit_log` |

### 4.2 目录 `TlTagDirController` → `/taglibrary/dir`

`list`（按 library_id 出树）、`add`、`edit`、`remove`（删目录前校验无标签）。

### 4.3 标签 `TlTagController` → `/taglibrary/tag`

| 接口 | 说明 |
|---|---|
| GET `/tree` | 标签管理页左侧树：标签库 → 目录 → 标签，按 online/offline tab 过滤，节点带数量 |
| GET `/list` `/{id}` | 列表 / 详情（详情页"基础信息 + 版本信息"数据源，含口径/有效日期/更新周期/创建方式） |
| PUT `/` | 编辑（中文名、目录、类型、口径、有效日期、更新周期；version+1） |
| PUT `/move` | 批量移动目录 |
| POST `/submit` `/audit` `/offline` | 支持批量 id 数组的状态流转（语义同 3.5，无独立 online 接口） |

### 4.4 字段快照同步

标签库通过 `dataset_id` 关联已上线数据集。同步流程：`dataset_id` → 取 `dp_dataset.default_version_id`（须 `version_status='ONLINE'`，否则报"关联数据集不存在或未上线"）→ 查 `dp_dataset_field`（`enabled='1'`，按 `order_num`）→ 增量生成快照：`field_name` = `field_alias`，`tag_name` 初始值 = `field_alias`（可人工改），`data_type` 原样快照，`tag_type` 按归一化后的 data_type 推断（小写、截括号、去 unsigned/zerofill；日期族→日期型，数值族含 tinyint→数值型，其余→文本型）。增量幂等：已有 field_name 不动。

## 5. 前端设计

`ruoyi-ui/src/views/taglibrary/` 两个页面 + `src/api/taglibrary/` 三个 api 模块（`library.js`、`dir.js`、`tag.js`），风格照抄 `views/databroker/`。

### 5.1 `taglibrary/list/index.vue` 标签库管理（卡片列表）

- 顶部工具栏：`+ 新建标签库` 主按钮（无批量编辑/数据概览）；右侧搜索框（名称/编码）+ 标签对象/分类两个字典下拉筛选 + 卡片/列表视图切换（默认卡片）
- 卡片内容（截图2 版式）：库名、所属分类、标签对象、负责人、更新时间、统计行（直接使用 `/list` 返回的 `online_count` / `pending_count` / `offline_count`，如"上线 N / 待发布 N"）、关联数据集名
- 卡片底部两个按钮：
  - 左：`标签管理` → `router.push('/taglibrary/tags?libraryId=xxx')`
  - 右：`更多` el-dropdown → 字段管理（抽屉内编辑字段中文名、目录、类型）｜上线/下线（按当前状态显示其一；上线对已下线对象调 submit 走审批流）｜审批管理（弹窗展示该库 `tl_audit_log` 记录 + 待审批时的通过/驳回操作）｜删除标签库（confirm 后调 DELETE）
- 新建弹窗：名称、编码、标签对象、分类、负责人、关联数据集（下拉列出已上线数据集，必填）；提交后自动同步字段并提示快照数量

### 5.2 `taglibrary/tags/index.vue` 标签管理（截图3 版式）

- 左侧面板：顶部标签库选择下拉（从卡片跳入时按 `libraryId` 预选中；菜单直进默认选第一个库）+ 搜索框；`上线标签`/`下线标签` 两个 tab（`上线标签` tab = status=已上线；`下线标签` tab = 其余所有非已上线状态，即草稿+待审批+已下线）；下方树：标签库 → 目录 → 标签，节点带数量角标，叶子节点用颜色圆点区分 tag_type（底部图例）
- 右侧主区：`标签详情` + 右上角`编辑`按钮；分块：基础信息（标签名称、数值类型、标签类型、有效日期、更新周期、创建方式）、口径信息（业务口径、技术口径）、技术信息（字段配置）、版本信息侧栏（所属子库、创建时间、版本 V N、最近修改人/时间）。使用信息/关联信息本期不展示
- 左侧树支持目录增删改、标签移动目录、单个/批量上下线与提交审批；审批操作集中在库列表页"审批管理"弹窗，本页不做审批操作

## 6. 菜单、权限与字典 SQL

`ruoyi-taglibrary/src/main/resources/sql/taglibrary_menu.sql`，menu_id 从 **2100** 起（2000 段已被数据代理占用）：

```sql
insert into sys_menu values('2100', '标签库管理', '0', '6', 'taglibrary', null, '', '', 1, 0, 'M', '0', '0', '', 'tag', 'admin', sysdate(), '', null, '标签库管理目录');
insert into sys_menu values('2101', '标签库管理', '2100', '1', 'list', 'taglibrary/list/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:library:list', 'list', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2102', '标签管理',  '2100', '2', 'tags', 'taglibrary/tags/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:tag:list', 'tag', 'admin', sysdate(), '', null, '');
```

按钮权限（F 型，挂对应菜单下，2110 起）：`library:query/add/edit/remove/sync/submit/audit/offline`、`dir:list/add/edit/remove`、`tag:query/edit/move/submit/audit/offline`。

字典 SQL 同文件：`tag_object`（客户/企业/机构/商户）、`tag_library_category`（客户维度/产品维度/员工维度/交易维度/营销维度）、`tag_type`（选项型/布尔型/数值型/文本型/日期型）、`tag_update_cycle`（日/周/月）。

## 7. 错误处理与校验

- library_code 唯一，重复返回明确错误提示
- 已上线/待审批的库禁止删除；非空目录禁止删除
- 状态机非法迁移（如草稿直接下线）后端拒绝并提示
- 同步接口对不存在的源表返回错误；重复同步为增量幂等

## 8. 验证方式

项目无测试套件（`mvn test` 空转），验证以 `mvn clean package` 编译通过 + 启动后手动跑通链路为准：建库 → 字段同步 → 标签管理页树/详情 → 提交审批 → 通过/驳回 → 上下线 → 删除校验。验收时明确说明未做自动化测试。

## 9. 实施步骤

1. 建 `ruoyi-taglibrary` 模块骨架（pom + 根 pom + admin pom + application.yml xss）
2. DDL + 菜单/字典 SQL
3. 后端四层代码（domain → mapper+XML → service → controller）
4. 前端 api 三模块 + 两个页面
5. 编译 + 手动链路验证
