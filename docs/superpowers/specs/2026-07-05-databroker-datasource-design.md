# 数据代理模块-数据源管理 设计文档

## 参考

完整开发文档见 `doc/数据代理模块-数据源管理开发文档.md`，本文件为该文档的精炼摘要，用于实现规划。

## 架构

- 新建 Maven 模块 `ruoyi-databroker`，依赖 `ruoyi-framework`，由 `ruoyi-admin` 引入
- 复用 RuoYi JWT/Redis 认证和 `@PreAuthorize` 权限
- MVC 分层：Controller → Service → Mapper/XML
- 独立 JDBC 连接采集目标库 `information_schema`

## 数据库（5 张表）

| 表 | 说明 |
|---|---|
| `dp_datasource_catalog` | 数据源目录树 |
| `dp_datasource` | 数据源配置（密码加密存储） |
| `dp_meta_table` | 元数据表/视图 |
| `dp_meta_column` | 元数据字段 |
| `dp_datasource_log` | 操作日志 |

## 后端接口（前缀 `/databroker`）

| 接口 | 方法 | 权限 |
|---|---|---|
| `/datasource/tree` | GET | `databroker:datasource:list` |
| `/datasource/{id}` | GET | `databroker:datasource:query` |
| `/datasource` | POST | `databroker:datasource:add` |
| `/datasource` | PUT | `databroker:datasource:edit` |
| `/datasource/{ids}` | DELETE | `databroker:datasource:remove` |
| `/datasource/test` | POST | `databroker:datasource:test` |
| `/datasource/{id}/sync` | POST | `databroker:datasource:sync` |
| `/datasource/{id}/tables` | GET | `databroker:datasource:list` |
| `/datasource/table/{tableId}/columns` | GET | `databroker:datasource:query` |
| `/datasource/table/{tableId}/cnName` | PUT | `databroker:datasource:edit` |
| `/datasource/{id}/logs` | GET | `databroker:datasource:query` |

## 密码加密

- `DataBrokerCryptoService`：AES/GCM/NoPadding
- 密钥来自 `databroker.crypto.secret`
- 接口返回和日志永不暴露明文

## 前端

- API 模块：`ruoyi-ui/src/api/databroker/datasource.js`
- 页面：`ruoyi-ui/src/views/databroker/datasource/index.vue`
- 布局：左侧目录+数据源树，右侧基本信息/表信息/操作记录三个 Tab
- 沿用 RuoYi Vue 2 + Element UI 风格

## 菜单权限（ID: 2000-2007）

| ID | 名称 | 权限标识 |
|---|---|---|
| 2000 | 数据代理 | 目录 |
| 2001 | 数据源管理 | `databroker:datasource:list` |
| 2002-2007 | 查询/新增/修改/删除/测试连接/同步元数据 | 对应权限 |

## 实现顺序

同文档 §13：Maven 模块 → 配置 → 数据库 → Domain/Mapper/XML → 加密 → CRUD → 测试连接 → 元数据采集 → 同步 → 表/字段/日志接口 → 前端 API → 前端页面 → 菜单导入 → 联调
