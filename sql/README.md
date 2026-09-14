# SQL 脚本索引

TagPilot 全部数据库脚本的统一入口。**新增 SQL 前请先确认它属于下面哪一类，并放到对应目录。**

执行顺序与部署关系：

```
首次部署    sql/init/ry_init.sql            手工执行一次（建库 + 结构与基础数据）
增量变更    sql/migration/V*.sql            由 bin/db-migrate.sh 自动执行（CI Deploy 阶段）
可选数据    sql/seed/*.sql                  按需手工执行
一次性修复  sql/maintenance/*.sql           手工执行，执行前先核对影响行数
历史留档    sql/archive/*.sql               不再执行，仅供追溯
```

> `sql/migration/` 与 `sql/init/ry_init.sql` 的路径被 `bin/db-migrate.sh` 引用，**不要改名或移动**。

---

## 1. 初始化（`sql/init/`）

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 执行顺序 | 前置依赖 | 所属模块 | 运行环境 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ry_init.sql` | 全量初始化：创建 `ry` + `indiv_cust` 两库，含 sys_* 基础数据（账号/角色/158 菜单/字典/配置/岗位/定时任务）、QRTZ_* 调度表、dp_* / tl_* / ind_tag_data 全部业务数据 | 否 | **是（仅一次）** | 1 | MySQL 8.0+（utf8mb4_0900_ai_ci） | 全局 | 新服务器首次部署 | 否 | 以 2026-09-07 开发库实际状态导出；尾部已写入 `schema_migration` 基线记录 V20260714_01 ~ V20260905_03，故新环境执行迁移不会重放历史。<br>`dp_datasource` 连接密码使用部署机 `.databroker-crypto-secret` 加密，迁移该文件时需一并迁移密钥。<br>有意排除无主表 `dp_code_*` / `dp_asset_reference`，勿再创建。 |

执行：

```bash
mysql -h<host> -P3306 -uroot -p < sql/init/ry_init.sql
```

## 2. 增量迁移（`sql/migration/`）

**由 `bin/db-migrate.sh` 按文件名排序自动执行**，已应用版本记录在目标库 `schema_migration` 表；幂等、只向前、不得包含 `drop table`。

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 执行顺序 | 前置依赖 | 所属模块 | 运行环境 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `V20260714_01__databroker_datasource_order_num.sql` | dp_datasource 增加 order_num（拖拽排序） | **是**（CI Deploy） | 否 | 1 | 无 | databroker | 全部 | 自研迁移器 | 来源 `ruoyi-databroker/src/main/resources/sql/databroker_migration_order_num.sql` |
| `V20260811_01__databroker_dimension_table.sql` | dp_dimension_table 维表登记表 + 维表管理菜单（2040–2046） | **是**（CI Deploy） | 否 | 2 | 无 | databroker | 全部 | 自研迁移器 | 来源 `ruoyi-databroker/src/main/resources/sql/databroker_dimension_migration.sql` |
| `V20260905_01__tag_system_del_flag_widen.sql` | del_flag 由 char(1) 拓宽为 varchar(64)，修复逻辑删除唯一键冲突（P0-5） | **是**（CI Deploy） | 否 | 3 | 无 | 全局（dp_*/tl_*） | 全部 | 自研迁移器 | 来源 `sql/archive/tag_system_del_flag_migration.sql` |
| `V20260905_02__taglibrary_metadata_change.sql` | tl_tag_library_dimension + tl_tag_metadata_change 建表 | **是**（CI Deploy） | 否 | 4 | 无 | taglibrary | 全部 | 自研迁移器 | 来源 `ruoyi-taglibrary/src/main/resources/sql/taglibrary_metadata_migration.sql` |
| `V20260905_03__tag_mapping_sync_upgrade.sql` | 批量映射同步：tl_tag_library/tl_tag/tl_tag_metadata_change 加列、新增权限菜单 2136–2137、存量草稿迁入 status='4' | **是**（CI Deploy） | 否 | 5 | **须在 V20260905_02 之后** | taglibrary | 全部 | 自研迁移器 | 来源 `sql/archive/tag_mapping_sync_upgrade_migration.sql` |

**新增迁移脚本规范**：命名 `V<yyyymmdd>_<序号>__<描述>.sql`；幂等、只向前、不得包含 `drop table`。已应用的迁移文件**内容不可再修改**（因此其中标注的"来源"路径保留移动前的历史写法，实际文件见 `sql/archive/`）。

## 3. 种子 / 测试数据（`sql/seed/`）

按需手工执行，不属于自动部署流程。

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 执行顺序 | 前置依赖 | 所属模块 | 运行环境 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ind_tag_data.sql` | 客户标签宽表 `ind_tag_data` 建表 + `LOAD DATA` 导入说明 | 否 | 是 | 视需要 | `ry` 库已初始化 | taglibrary / objectgroup | 开发/测试 | 否 | 配套数据文件在仓库外（`ind_tag_data.csv`）；被 `docs/superpowers/plans/*` 引用 |
| `tag_mapping_test_data.sql` | 标签库批量映射同步（阶段7）测试数据，幂等可重复执行 | 否 | 是 | 视需要 | `ry` + `indiv_cust` 库；建议先执行 `sql/seed/ind_tag_data.sql` | taglibrary | 测试 | 否 | 配套计划见 `docs/plans/标签库批量映射同步优化计划.md` |
| `test_users_coverage.sql` | RuoYi 测试用户 qa_* 及 qa_scope_* 角色，覆盖账号状态 / 数据范围 / 组织属性场景，可重复导入 | 否 | 是 | 视需要 | 基线为 `sql/archive/ry_20260417.sql` | 全局（sys_*） | 测试 | 否 | 所有账号密码 `admin123`；不会改动 admin/ry 及业务数据 |

## 4. 维护 / 一次性修复（`sql/maintenance/`）

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 执行顺序 | 前置依赖 | 所属模块 | 运行环境 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cleanup_orphan_data.sql` | 标签系统孤儿数据一次性清理（维表关系残留、孤儿码值、孤儿对象群、空导入批次），对应《标签系统数据链路评估与优化方案》P0-6 | 否 | **是（需逐段确认）** | 一次性 | `ry` 库为已升级版本 | taglibrary / objectgroup | 测试库核对后再上生产 | 否 | 每段先给出"受影响行数预估"，确认无误后放开对应 `DELETE`；后续此类清理已由代码级联逻辑承接，**勿重复定时执行** |

## 5. 历史留档（`sql/archive/`）

已被取代、不再执行的脚本，保留以便追溯。**禁止删除。**

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 执行顺序 | 前置依赖 | 所属模块 | 运行环境 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ry_20260417.sql` | RuoYi 原版表结构 + 种子数据（不含 Quartz、不含 TagPilot 业务表） | 否 | 否（已被取代） | — | — | 全局 | — | 否 | 已被 `sql/init/ry_init.sql` 取代；仍可作为实体字段的 schema 参考 |
| `quartz.sql` | Quartz 调度表 `QRTZ_*` 建表 | 否 | 否（已被取代） | — | — | quartz | — | 否 | 已并入 `sql/init/ry_init.sql` |
| `tag_system_del_flag_migration.sql` | del_flag 拓宽迁移（原文） | 否 | 否 | — | — | 全局 | — | 否 | 已收录为 `sql/migration/V20260905_01__tag_system_del_flag_widen.sql` |
| `tag_mapping_sync_upgrade_migration.sql` | 批量映射同步结构迁移（原文） | 否 | 否 | — | — | taglibrary | — | 否 | 已收录为 `sql/migration/V20260905_03__tag_mapping_sync_upgrade.sql` |

## 6. 模块级 SQL（保留在原位，未集中到 `sql/`）

以下脚本位于各模块的 Maven 资源目录 `ruoyi-*/src/main/resources/sql/`，**保留原位置**：它们随模块打包进 jar，是模块自带的建表/菜单 DDL，路径被模块设计文档引用，移动会改变 jar 内容且无收益。此处仅登记索引。

### ruoyi-databroker

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 所属模块 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `databroker_schema.sql` | `dp_datasource` / `dp_meta_table` / `dp_meta_column` 等数据代理核心建表 | 否 | 是 | databroker | 否（Maven 资源） | 初始建设脚本，已并入 `sql/init/ry_init.sql` |
| `databroker_menu.sql` | 数据源目录管理菜单与按钮 | 否 | 是 | databroker | 否 | 同上 |
| `databroker_dataset_schema.sql` | `dp_dataset*` 数据集 6 张表建表 | 否 | 是 | databroker | 否 | 同上 |
| `databroker_dataset_menu.sql` | 数据集管理菜单与按钮 | 否 | 是 | databroker | 否 | 同上 |
| `databroker_dimension_migration.sql` | `dp_dimension_table` 维表登记表 + 菜单 2040–2046 | 否 | 是 | databroker | 否 | **已被取代** → `sql/migration/V20260811_01__databroker_dimension_table.sql` |
| `databroker_migration_order_num.sql` | `dp_datasource.order_num` 拖拽排序列 | 否 | 是 | databroker | 否 | **已被取代** → `sql/migration/V20260714_01__databroker_datasource_order_num.sql` |

### ruoyi-taglibrary

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 所属模块 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `taglibrary_schema.sql` | `tl_*` 标签库表结构 | 否 | 是 | taglibrary | 否（Maven 资源） | 初始建设脚本，已并入 `sql/init/ry_init.sql` |
| `taglibrary_menu.sql` | 标签库菜单与按钮（menu_id 2100 起） | 否 | 是 | taglibrary | 否 | 同上 |
| `taglibrary_metadata_migration.sql` | 标签库默认码表关系 + 标签元数据变更表 | 否 | 是 | taglibrary | 否 | **已被取代** → `sql/migration/V20260905_02__taglibrary_metadata_change.sql` |

### ruoyi-objectgroup

| 文件 | 用途 | 是否自动执行 | 允许手动执行 | 所属模块 | 框架管理 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `objectgroup_schema.sql` | 对象群（客群）表结构 | 否 | 是 | objectgroup | 否（Maven 资源） | 初始建设脚本，已并入 `sql/init/ry_init.sql` |
| `objectgroup_menu.sql` | 对象群菜单与按钮（menu_id 2200 起） | 否 | 是 | objectgroup | 否 | 同上 |

> 注：`ruoyi-generator/src/main/resources/vm/sql/sql.vm` 是代码生成器的 Velocity 模板，**不是**数据库脚本，不在本索引范围内。

---

## 7. 目录职责与新增约定

| 目录 | 职责 | 谁执行 |
| :--- | :--- | :--- |
| `init/` | 首次安装的完整数据库初始化 / baseline | 部署者手工执行一次 |
| `migration/` | 有先后顺序的增量升级脚本，由 `bin/db-migrate.sh` 驱动 | CI 自动 |
| `seed/` | 初始化字典、演示数据、测试数据、reference data | 开发/测试手工 |
| `maintenance/` | 数据修复、backfill、一次性补数据、排障 SQL | 开发/DBA 手工，需逐段确认 |
| `archive/` | 已废弃 / 已被替代 / 历史版本，有保留价值 | 不执行 |

新增脚本时：先判断它属于上表哪一类，不要直接丢在 `sql/` 根目录；不要创建 `database/`、`db/` 等第二套顶层体系。开发阶段的临时数据备份不要提交到仓库（需要时放在本地或备份系统，不要进 `sql/`）。
