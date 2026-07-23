# 数据集管理模块设计（单宽表 + 字段选择 + 历史版本）

日期：2026-07-23
状态：已与用户确认（旧数据清空重来；草稿→发布→下线多版本并存；勾选表格字段选择 UI）

## 1. 背景与范围

数据代理（databroker）模块已有数据源管理（左树右详情）。本模块补全"数据集管理"，菜单已在数据库注册（sys_menu 2020–2031，repo SQL 中缺失，本次补回）。

已注册权限点（必须全部实现，不多做）：

- 菜单 C：`databroker:dataset:list`，component `databroker/dataset/index`
- 按钮 F：`databroker:dataset:{query,add,edit,remove,preview,publish,offline}`
- 数据集目录 F：`databroker:dataset:catalog:{list,add,edit,remove}`（4 段 perms）

明确不做（YAGNI）：JOIN/UNION 图编排、计算列、筛选条件、字段脱敏/敏感级 UI（表列保留默认值留位）。一个数据集 = 某数据源下的一张宽表 + 选取的输出字段。

库中已存在 6 张表（`dp_dataset`, `dp_dataset_catalog`, `dp_dataset_version`, `dp_dataset_field`, `dp_dataset_dependency`, `dp_dataset_log`），结构即数据模型，沿用不改。旧版图结构数据（JOIN/UNION definition_json）全部 TRUNCATE 清空。

## 2. 定义格式 definition_json（schemaVersion=2，单宽表）

```json
{
  "schemaVersion": 2,
  "datasourceId": 100,
  "tableId": 101,
  "fields": [
    { "columnId": 171, "alias": "cust_id", "dataType": "varchar", "enabled": true, "orderNum": 1 }
  ]
}
```

- `datasourceId` 恒等于 `dp_dataset.datasource_id`（创建数据集时选定数据源，不可改）
- 字段顺序即 `orderNum` 升序；`alias` 为输出列名，在版本内唯一
- 同步冗余：`dp_dataset_field` 按 version_id 全量重写（field_alias/field_name/source_table_id/source_column_id/data_type/enabled/order_num，其余列默认值）
- `dp_dataset_dependency` 按 version_id 全量重写：1 条 TABLE 依赖 + N 条 COLUMN 依赖

## 3. 版本工作流

- 状态机：`DRAFT → ONLINE → OFFLINE`；每个数据集**至多一个 DRAFT**
- 新建数据集：自动创建 V1 DRAFT（空定义），`latest_version_no=1`
- 只有 DRAFT 可保存定义；保存时校验并写 `health_status`(VALID/INVALID) + `validation_message`，DRAFT 允许 INVALID 保存
- 发布（publish）：仅 DRAFT、且校验必须 VALID；填 `release_note`，写 `publish_by/publish_time`；可选设为默认版本（`dp_dataset.default_version_id`）。多版本可同时 ONLINE
- 下线（offline）：ONLINE→OFFLINE；若为默认版本则清空 `default_version_id`
- 复制版本：基于任意版本生成新 DRAFT（version_no = latest+1），已有 DRAFT 时拒绝
- 校验规则：数据源存在且正常；tableId 在 `dp_meta_table` 中属于该数据源且 status=0；启用字段的 columnId 在该表 `dp_meta_column` 中存在；alias 非空且版本内唯一；发布时至少 1 个启用字段

## 4. 后端（ruoyi-databroker 模块）

分层完全复刻数据源管理：domain / mapper(接口+XML) / service(接口+impl) / controller。新增类：

- domain：`DpDataset`, `DpDatasetCatalog`, `DpDatasetVersion`, `DpDatasetField`, `DpDatasetDependency`, `DpDatasetLog`；树 DTO 复用 `TreeNode`（增加 `datasetId` 字段，nodeType 用 `catalog`/`dataset`，id 前缀 `cat_`/`ds_`）
- mapper ×6 + `resources/mapper/databroker/` 下 XML ×6
- service：`IDpDatasetCatalogService`, `IDpDatasetService`（+impl）
- controller：`DpDatasetCatalogController`, `DpDatasetController`

### 端点契约

| 方法/路径 | 权限 | 说明 |
|---|---|---|
| GET `/databroker/dataset/tree` | `databroker:dataset:list` | 目录+数据集混合树 |
| GET `/databroker/dataset/{datasetId}` | `:query` | 数据集详情（含 defaultVersionId/latestVersionNo/数据源名） |
| POST `/databroker/dataset` | `:add` | body: catalogId, datasetCode, datasetName, datasourceId, ownerName, remark → 建数据集 + V1 DRAFT |
| PUT `/databroker/dataset` | `:edit` | body: datasetId, catalogId, datasetName, ownerName, status, remark（编码/数据源不可改） |
| DELETE `/databroker/dataset/{datasetIds}` | `:remove` | 逻辑删（del_flag='2'） |
| PUT `/databroker/dataset/{id}/move` | `:edit` | 拖拽移动/排序（镜像数据源 move 签名） |
| GET `/databroker/dataset/{datasetId}/versions` | `:query` | 版本列表（不含 definition_json），附 isDefault |
| GET `/databroker/dataset/version/{versionId}` | `:query` | 版本详情：definitionJson + fields 明细 |
| PUT `/databroker/dataset/version` | `:edit` | 保存草稿：{versionId, versionName, tableId, fields[]} → 重写 definition_json/field/dependency + 校验 |
| POST `/databroker/dataset/{datasetId}/version/copy` | `:edit` | body: {sourceVersionId} → 新 DRAFT |
| POST `/databroker/dataset/version/{versionId}/publish` | `:publish` | body: {versionName, releaseNote, setDefault} |
| POST `/databroker/dataset/version/{versionId}/offline` | `:offline` | 下线 |
| POST `/databroker/dataset/preview` | `:preview` | body: {versionId} → 重校验后 JDBC `SELECT 启用字段 FROM 宽表 LIMIT 100`，返回 {columns:[{name,dataType}], rows:[{alias:value}]} |
| GET `/databroker/dataset/{datasetId}/logs` | `:query` | 操作日志分页 |
| GET `/databroker/dataset/datasource/{datasourceId}/tables` | `:query` | 透传宽表分页查询（objectName 过滤），来自 dp_meta_table |
| GET `/databroker/dataset/table/{tableId}/columns` | `:query` | 透传字段列表，来自 dp_meta_column |
| GET `/databroker/dataset/catalog/list` | `databroker:dataset:catalog:list` | 目录扁平列表 |
| POST `/databroker/dataset/catalog` | `:catalog:add` / PUT `:catalog:edit` / DELETE `/{id}` `:catalog:remove` / PUT `/move` `:catalog:edit` | 镜像数据源目录 |

约定：controller 返回 `AjaxResult`/`TableDataInfo`；删除/发布/下线/预览/保存草稿均写 `dp_dataset_log`；预览用 `JdbcConnectionFactory` 短连接（只读 SELECT，反引号包裹标识符，LIMIT 100）；数据集删除为逻辑删；目录仅空目录可删（无子目录、无数据集）。

## 5. 前端（ruoyi-ui）

新增 `src/api/databroker/dataset.js`（含 catalog 函数）与 `src/views/databroker/dataset/index.vue`，布局/交互复刻 `views/databroker/datasource/index.vue`：

- 左侧 300px 树：目录+数据集混合树，搜索过滤、右键菜单（新增根/子目录、新增/编辑/删除数据集）、同类型拖拽排序；加载后保持展开与选中状态
- 右侧：
  - 目录节点 → 目录信息卡 + 操作按钮
  - 数据集节点 → 头部信息条（名称/编码/数据源/默认版本 tag/状态）+ 5 个 el-tabs：
    1. **基本信息**：编码(禁改)/名称/负责人/目录/数据源/状态/备注，可编辑保存
    2. **字段定义**：版本下拉（DRAFT 可编辑，ONLINE/OFFLINE 只读并提示）→ 宽表选择（数据集所属数据源的表，可搜索）→ 字段勾选表格（复选框、搜索过滤、全选/反选(作用于过滤结果)、列：字段名/类型/注释、行内编辑别名、启用开关、上移/下移）→ 保存草稿（展示校验结果）
    3. **版本管理**：版本表（版本号/名称/状态 tag/健康/发布人/时间/发布说明/默认标记），操作：查看、复制为新版本、发布（弹窗：版本名称/发布说明/设为默认）、下线、设为默认入口随发布
    4. **数据预览**：版本下拉（默认取默认在线版本）→ 执行预览 → 100 行 el-table
    5. **操作记录**：日志分页表（镜像数据源日志 tab）
- 新建数据集弹窗：目录、编码、名称、数据源（必选，之后不可改）、负责人、备注；创建后切到字段定义 tab 引导选表选字段

## 6. SQL（补回仓库，与现库一致）

- `ruoyi-databroker/src/main/resources/sql/databroker_dataset_schema.sql`：6 张 dp_dataset* 建表语句（按现库 SHOW CREATE 誊写，改 utf8mb4 通用 collation）
- `ruoyi-databroker/src/main/resources/sql/databroker_dataset_menu.sql`：sys_menu 2020–2031（按现库记录誊写）

## 7. 验证

项目无测试套件。验证 = `mvn clean package -DskipTests` 编译通过 + 启动后端 curl 走通：建数据集 → 选表选字段保存草稿 → 发布 → 预览 → 复制版本 → 下线 → 删除；前端 `npm run build:prod` 构建通过 + dev 人工核页面。
