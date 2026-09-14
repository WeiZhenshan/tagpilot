# 标签库管理模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 RuoYi-Vue 中新增 `ruoyi-taglibrary` 模块：顶级菜单"标签库管理"下的标签库卡片列表页（含卡片双按钮）与标签管理页（树+详情），字段快照式标签、状态机+轻量审批。

**Architecture:** 新建 Maven 模块 `ruoyi-taglibrary`（照抄 `ruoyi-databroker` 接入方式），4 张 `tl_*` 表；标签 = 关联宽表列的元数据快照（`tl_tag`），同步自建库 `information_schema.columns`；库与标签共用 草稿→待审批→已上线⇄已下线 状态机，三动作接口 submit/audit/offline，留痕 `tl_audit_log`。前端 Vue 2 + Element UI，两个页面 + 三个 api 模块，风格照抄 `ruoyi-ui/src/views/databroker/`。

**Tech Stack:** Spring Boot 2.5.15 / Java 8 / MyBatis XML / MySQL；Vue 2 + Element UI。

**Spec:** `docs/superpowers/specs/2026-07-23-taglibrary-design.md`（本计划严格按其执行）

**关于 TDD 的重要说明：** 本项目**没有任何测试套件**（全仓 0 个 src/test 文件，`mvn test` 空转），不引入测试框架。每个任务的验证步骤 = `mvn compile`（或 `mvn clean package -DskipTests`）通过 + 指定的 curl/手动验证点。严禁声称"测试通过"。

**通用约定（所有任务适用，不再重复）：**
- 代码注释、菜单名、commit message 用中文；Java 类作者标签 `@author ruoyi`。
- 所有 domain 实体 extend `com.ruoyi.common.core.domain.BaseEntity`（自带 createBy/createTime/updateBy/updateTime/remark/params）。
- Controller extend `BaseController`，返回 `AjaxResult`/`TableDataInfo`，分页用 `startPage()` + `getDataTable(list)`。
- 权限注解格式 `@PreAuthorize("@ss.hasPermi('taglibrary:xxx:yyy')")`。
- 提交代码前必须 `mvn compile -pl ruoyi-taglibrary -am -q` 通过（涉及 admin 依赖时 `mvn clean package -DskipTests -q`）。

---

### Task 1: 模块骨架（pom × 3 + 包结构）

**Files:**
- Create: `ruoyi-taglibrary/pom.xml`
- Modify: `pom.xml`（modules + dependencyManagement）
- Modify: `ruoyi-admin/pom.xml`（dependencies）
- Modify: `ruoyi-admin/src/main/resources/application.yml`（xss.urlPatterns）

- [ ] **Step 1: 创建 `ruoyi-taglibrary/pom.xml`**

照抄 `ruoyi-databroker/pom.xml`，只改 artifactId/name/description：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <parent>
        <artifactId>ruoyi</artifactId>
        <groupId>com.ruoyi</groupId>
        <version>3.9.2</version>
    </parent>
    <modelVersion>4.0.0</modelVersion>

    <artifactId>ruoyi-taglibrary</artifactId>

    <description>
        taglibrary标签库管理模块
    </description>

    <dependencies>
        <!-- 通用工具-->
        <dependency>
            <groupId>com.ruoyi</groupId>
            <artifactId>ruoyi-common</artifactId>
        </dependency>
        <!-- 安全框架 -->
        <dependency>
            <groupId>com.ruoyi</groupId>
            <artifactId>ruoyi-framework</artifactId>
        </dependency>
    </dependencies>
</project>
```

（注：先以 `ruoyi-databroker/pom.xml` 实际内容为准对齐依赖，databroker 还依赖了 mysql-connector-java；本模块不直连外部库，可不引。）

- [ ] **Step 2: 根 `pom.xml` 两处修改**

1. `dependencyManagement` 中 `ruoyi-databroker` 条目（pom.xml:224 附近）后追加：

```xml
            <dependency>
                <groupId>com.ruoyi</groupId>
                <artifactId>ruoyi-taglibrary</artifactId>
                <version>${ruoyi.version}</version>
            </dependency>
```

2. `<modules>`（pom.xml:231-239）中 `<module>ruoyi-databroker</module>` 后追加 `<module>ruoyi-taglibrary</module>`。

- [ ] **Step 3: `ruoyi-admin/pom.xml` 加依赖**

在 `ruoyi-databroker` 依赖（ruoyi-admin/pom.xml:67 附近）后追加：

```xml
        <!-- taglibrary标签库管理模块-->
        <dependency>
            <groupId>com.ruoyi</groupId>
            <artifactId>ruoyi-taglibrary</artifactId>
        </dependency>
```

- [ ] **Step 4: `application.yml` 的 `xss.urlPatterns` 追加 `/taglibrary/*`**

注意：`xss.urlPatterns`（application.yml:136 附近）是**逗号分隔的标量**，不是 YAML 列表。把现有值 `urlPatterns: /system/*,/monitor/*,/tool/*,/databroker/*` 直接改为在末尾追加——`urlPatterns: /system/*,/monitor/*,/tool/*,/databroker/*,/taglibrary/*`（以实际现值为准，仅末尾加 `,/taglibrary/*`）。

- [ ] **Step 5: 建包骨架（空目录占位）**

```
ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/{controller,service/impl,mapper,domain/dto,domain/vo}
ruoyi-taglibrary/src/main/resources/{mapper/taglibrary,sql}
```

- [ ] **Step 6: 编译验证**

Run: `mvn clean package -DskipTests -q`
Expected: BUILD SUCCESS，`ruoyi-taglibrary/target/` 生成 jar。

- [ ] **Step 7: Commit**

```bash
git add ruoyi-taglibrary pom.xml ruoyi-admin/pom.xml ruoyi-admin/src/main/resources/application.yml
git commit -m "feat: 新增ruoyi-taglibrary模块骨架"
```

---

### Task 2: DDL + 菜单/字典 SQL

**Files:**
- Create: `ruoyi-taglibrary/src/main/resources/sql/taglibrary_schema.sql`
- Create: `ruoyi-taglibrary/src/main/resources/sql/taglibrary_menu.sql`

- [ ] **Step 1: 写 `taglibrary_schema.sql`（完整内容如下）**

```sql
-- ----------------------------
-- 标签库管理模块表结构
-- ----------------------------
drop table if exists tl_tag_library;
create table tl_tag_library (
  library_id   bigint(20)   not null auto_increment comment '标签库ID',
  library_name varchar(64)  not null                comment '标签库名称',
  library_code varchar(64)  not null                comment '标签库编码',
  category     varchar(32)  default ''              comment '分类（字典 tag_library_category）',
  tag_object   varchar(16)  default ''              comment '标签对象（字典 tag_object）',
  source_table varchar(64)  default ''              comment '关联数据表名',
  owner_name   varchar(30)  default ''              comment '负责人',
  status       char(1)      default '0'             comment '状态（0草稿 1待审批 2已上线 3已下线）',
  del_flag     char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by    varchar(64)  default ''              comment '创建者',
  create_time  datetime                               comment '创建时间',
  update_by    varchar(64)  default ''              comment '更新者',
  update_time  datetime                               comment '更新时间',
  remark       varchar(500) default null            comment '备注',
  primary key (library_id),
  unique key uk_tl_library_code (library_code, del_flag)
) engine=innodb auto_increment=100 comment='标签库表';

drop table if exists tl_tag_dir;
create table tl_tag_dir (
  dir_id      bigint(20)   not null auto_increment comment '目录ID',
  library_id  bigint(20)   not null                comment '所属标签库ID',
  parent_id   bigint(20)   default 0               comment '父目录ID',
  dir_name    varchar(64)  not null                comment '目录名称',
  order_num   int(4)       default 0               comment '显示顺序',
  del_flag    char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by   varchar(64)  default ''              comment '创建者',
  create_time datetime                               comment '创建时间',
  update_by   varchar(64)  default ''              comment '更新者',
  update_time datetime                               comment '更新时间',
  remark      varchar(500) default null            comment '备注',
  primary key (dir_id),
  key idx_tl_dir_library (library_id)
) engine=innodb auto_increment=100 comment='标签目录表';

drop table if exists tl_tag;
create table tl_tag (
  tag_id           bigint(20)   not null auto_increment comment '标签ID',
  library_id       bigint(20)   not null                comment '所属标签库ID',
  dir_id           bigint(20)   not null                comment '所属目录ID',
  field_name       varchar(64)  not null                comment '源字段名',
  tag_name         varchar(128) not null                comment '标签中文名',
  data_type        varchar(32)  default ''              comment '源字段数据类型',
  tag_type         varchar(16)  default ''              comment '标签类型（字典 tag_type）',
  business_caliber varchar(500) default ''              comment '业务口径',
  tech_caliber     varchar(500) default ''              comment '技术口径',
  valid_period     varchar(32)  default '永久有效'       comment '有效日期',
  update_cycle     varchar(8)   default '日'            comment '更新周期（字典 tag_update_cycle）',
  create_way       varchar(8)   default '同步'           comment '创建方式（同步/自建）',
  status           char(1)      default '0'             comment '状态（0草稿 1待审批 2已上线 3已下线）',
  version          int(8)       default 1               comment '版本号',
  del_flag         char(1)      default '0'             comment '删除标志（0存在 2删除）',
  create_by        varchar(64)  default ''              comment '创建者',
  create_time      datetime                               comment '创建时间',
  update_by        varchar(64)  default ''              comment '更新者',
  update_time      datetime                               comment '更新时间',
  remark           varchar(500) default null            comment '备注',
  primary key (tag_id),
  key idx_tl_tag_library_status (library_id, status),
  key idx_tl_tag_dir (dir_id),
  unique key uk_tl_tag_field (library_id, field_name, del_flag)
) engine=innodb auto_increment=100 comment='标签表（字段快照）';

drop table if exists tl_audit_log;
create table tl_audit_log (
  log_id        bigint(20)   not null auto_increment comment '日志ID',
  biz_type      varchar(16)  not null                comment '业务类型（library/tag）',
  biz_id        bigint(20)   not null                comment '业务对象ID',
  action        varchar(16)  not null                comment '动作（提交/通过/驳回/上线/下线）',
  from_status   char(1)      default ''              comment '变更前状态',
  to_status     char(1)      default ''              comment '变更后状态',
  apply_by      varchar(64)  default ''              comment '申请人',
  audit_by      varchar(64)  default ''              comment '审批人',
  audit_time    datetime                               comment '审批时间',
  audit_comment varchar(500) default ''              comment '审批意见',
  create_by     varchar(64)  default ''              comment '创建者',
  create_time   datetime                               comment '创建时间',
  primary key (log_id),
  key idx_tl_audit_biz (biz_type, biz_id)
) engine=innodb auto_increment=100 comment='标签审批日志表';
```

- [ ] **Step 2: 写 `taglibrary_menu.sql`（完整内容如下）**

```sql
-- ----------------------------
-- 标签库管理模块菜单 SQL（menu_id 2100 起，2000 段已被数据代理占用）
-- sys_menu 共 20 列（含 route_name），每条 insert 20 个值，格式与 databroker_menu.sql 一致。
-- ----------------------------
insert into sys_menu values('2100', '标签库管理', '0', '6', 'taglibrary', null, '', '', 1, 0, 'M', '0', '0', '', 'tag', 'admin', sysdate(), '', null, '标签库管理目录');
insert into sys_menu values('2101', '标签库管理', '2100', '1', 'list', 'taglibrary/list/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:library:list', 'list', 'admin', sysdate(), '', null, '标签库管理菜单');
insert into sys_menu values('2102', '标签管理', '2100', '2', 'tags', 'taglibrary/tags/index', '', '', 1, 0, 'C', '0', '0', 'taglibrary:tag:list', 'tag', 'admin', sysdate(), '', null, '标签管理菜单');

-- 标签库按钮
insert into sys_menu values('2110', '标签库查询', '2101', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2111', '标签库新增', '2101', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2112', '标签库修改', '2101', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2113', '标签库删除', '2101', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2114', '同步字段', '2101', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:sync', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2115', '提交审批', '2101', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:submit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2116', '审批', '2101', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:audit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2117', '库下线', '2101', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:library:offline', '#', 'admin', sysdate(), '', null, '');

-- 标签按钮
insert into sys_menu values('2120', '标签查询', '2102', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2121', '标签修改', '2102', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2122', '移动目录', '2102', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:move', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2123', '标签提交审批', '2102', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:submit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2124', '标签审批', '2102', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:audit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2125', '标签下线', '2102', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:tag:offline', '#', 'admin', sysdate(), '', null, '');

-- 目录按钮
insert into sys_menu values('2126', '目录查询', '2102', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2127', '目录新增', '2102', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2128', '目录修改', '2102', '9', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2129', '目录删除', '2102', '10', '#', '', '', '', 1, 0, 'F', '0', '0', 'taglibrary:dir:remove', '#', 'admin', sysdate(), '', null, '');

-- 字典：标签对象 / 标签库分类 / 标签类型 / 更新周期
insert into sys_dict_type (dict_name, dict_type, status, create_by, create_time, remark) values
('标签对象', 'tag_object', '0', 'admin', sysdate(), '标签对象字典'),
('标签库分类', 'tag_library_category', '0', 'admin', sysdate(), '标签库分类字典'),
('标签类型', 'tag_type', '0', 'admin', sysdate(), '标签类型字典'),
('更新周期', 'tag_update_cycle', '0', 'admin', sysdate(), '标签更新周期字典');

insert into sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) values
(1, '客户', '客户', 'tag_object', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '企业', '企业', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '机构', '机构', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(4, '商户', '商户', 'tag_object', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(1, '客户维度', '客户维度', 'tag_library_category', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '产品维度', '产品维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '员工维度', '员工维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(4, '交易维度', '交易维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(5, '营销维度', '营销维度', 'tag_library_category', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(1, '选项型', '选项型', 'tag_type', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(2, '布尔型', '布尔型', 'tag_type', '', 'success', 'N', '0', 'admin', sysdate(), ''),
(3, '数值型', '数值型', 'tag_type', '', 'primary', 'N', '0', 'admin', sysdate(), ''),
(4, '文本型', '文本型', 'tag_type', '', 'info', 'N', '0', 'admin', sysdate(), ''),
(5, '日期型', '日期型', 'tag_type', '', 'warning', 'N', '0', 'admin', sysdate(), ''),
(1, '日', '日', 'tag_update_cycle', '', 'default', 'Y', '0', 'admin', sysdate(), ''),
(2, '周', '周', 'tag_update_cycle', '', 'default', 'N', '0', 'admin', sysdate(), ''),
(3, '月', '月', 'tag_update_cycle', '', 'default', 'N', '0', 'admin', sysdate(), '');
```

（执行前自查：`sys_dict_type`/`sys_dict_data` 若已存在同名 dict_type 记录则跳过对应 insert，避免重复。）

- [ ] **Step 3: 在 MySQL 执行两个脚本并抽查**

```bash
mysql -uroot ry < ruoyi-taglibrary/src/main/resources/sql/taglibrary_schema.sql
mysql -uroot ry < ruoyi-taglibrary/src/main/resources/sql/taglibrary_menu.sql
```

（以 `application-druid.yml` 里的实际库名/账号为准；执行后 `show tables like 'tl_%';` 应有 4 张表，`select count(*) from sys_menu where menu_id between 2100 and 2129;` 应为 21。）若本地不便执行 SQL，则记录在案，留到 Task 7 联调前执行。

- [ ] **Step 4: Commit**

```bash
git add ruoyi-taglibrary/src/main/resources/sql/
git commit -m "feat: 标签库管理模块DDL与菜单字典SQL"
```

---

### Task 3: Domain 实体与出入参

**Files:**
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/TlTagLibrary.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/TlTagDir.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/TlTag.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/TlAuditLog.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/dto/AuditRequest.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/dto/MoveRequest.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/vo/MetaColumnVO.java`

- [ ] **Step 1: 写 4 个实体**

风格照抄 `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpDataSource.java`：`extends BaseEntity`、字段 camelCase + getter/setter + toString（可用 `org.apache.commons.lang3.builder.ToStringBuilder` 同 databroker）。字段与 Task 2 DDL 一一对应：

- `TlTagLibrary`：`Long libraryId; String libraryName; String libraryCode; String category; String tagObject; String sourceTable; String ownerName; String status; String delFlag;` 另加 4 个**非表字段**（仅 `/list` 联表统计回填，加 `@TableField(exist=false)` 等价处理——本项目不用 MP，直接在实体里声明普通字段、XML 里 resultMap 映射即可）：`Long tagCount; Long onlineCount; Long offlineCount; Long pendingCount;`
- `TlTagDir`：`Long dirId; Long libraryId; Long parentId; String dirName; Integer orderNum; String delFlag;`
- `TlTag`：`Long tagId; Long libraryId; Long dirId; String fieldName; String tagName; String dataType; String tagType; String businessCaliber; String techCaliber; String validPeriod; String updateCycle; String createWay; String status; Integer version; String delFlag;`
- `TlAuditLog`：`Long logId; String bizType; Long bizId; String action; String fromStatus; String toStatus; String applyBy; String auditBy; Date auditTime; String auditComment;`

- [ ] **Step 2: 写 DTO/VO**

```java
// AuditRequest：审批/状态流转请求（submit/offline 复用）
public class AuditRequest {
    private Long[] ids;        // 批量对象ID
    private Boolean pass;      // audit 用：true通过 false驳回
    private String auditComment;
    // getter/setter
}

// MoveRequest：批量移动目录
public class MoveRequest {
    private Long[] tagIds;
    private Long dirId;
    // getter/setter
}

// MetaColumnVO：information_schema.columns 查询结果
public class MetaColumnVO {
    private String columnName;
    private String dataType;
    private String columnComment;
    // getter/setter
}
```

- [ ] **Step 3: 编译 + Commit**

Run: `mvn compile -pl ruoyi-taglibrary -am -q` → BUILD SUCCESS

```bash
git add ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/domain/
git commit -m "feat: 标签库模块domain实体与出入参"
```

---

### Task 4: Mapper 接口 + XML

**Files:**
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/mapper/TlTagLibraryMapper.java` 等 4 个接口
- Create: `ruoyi-taglibrary/src/main/resources/mapper/taglibrary/TlTagLibraryMapper.xml` 等 4 个 XML

- [ ] **Step 1: 4 个 Mapper 接口**

照抄 `ruoyi-databroker/.../mapper/DpDataSourceMapper.java` 的方法命名风格。方法清单：

- `TlTagLibraryMapper`：`selectLibraryList(TlTagLibrary q)`（含联表统计）、`selectLibraryById(Long id)`、`selectLibraryByCode(String code)`、`insertLibrary`、`updateLibrary`、`deleteLibraryByIds(Long[] ids)`（逻辑删 del_flag='2'）、`updateLibraryStatus(@Param("id") Long id, @Param("status") String status)`
- `TlTagDirMapper`：`selectDirList(Long libraryId)`、`selectDirById`、`insertDir`、`updateDir`、`deleteDirById`、`countTagByDirId(Long dirId)`
- `TlTagMapper`：`selectTagList(TlTag q)`、`selectTagById`、`selectTagByFieldName(@Param("libraryId") Long libraryId, @Param("fieldName") String fieldName)`、`insertTag`、`insertTagBatch(List<TlTag>)`、`updateTag`、`updateTagStatusBatch(@Param("ids") Long[] ids, @Param("status") String status)`、`moveTagBatch(@Param("ids") Long[] ids, @Param("dirId") Long dirId)`、`deleteTagByLibraryIds(Long[] libraryIds)`、`countOnlineByLibraryId(Long libraryId)`（删除校验用）
- `TlAuditLogMapper`：`insertAuditLog`、`selectAuditLogList(TlAuditLog q)`
- 另在 `TlTagLibraryMapper` 加元数据查询：`List<MetaColumnVO> selectTableColumns(String tableName)`（SQL：`select column_name as columnName, data_type as dataType, column_comment as columnComment from information_schema.columns where table_schema = database() and table_name = #{tableName} order by ordinal_position`）和 `List<String> selectBusinessTables()`（`select table_name from information_schema.tables where table_schema = database() and table_type='BASE TABLE' and table_name not like 'sys_%' and table_name not like 'qrtz_%' and table_name not like 'dp_%' and table_name not like 'tl_%' and table_name not like 'gen_%'`，新建弹窗选表用）。

- [ ] **Step 2: 4 个 XML**

照抄 `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceMapper.xml` 的骨架（resultMap + sql 片段 + CRUD）。关键点：

1. `selectLibraryList` 联表统计（卡片数据源）：

```xml
<select id="selectLibraryList" parameterType="TlTagLibrary" resultMap="TlTagLibraryResult">
    select l.*,
           coalesce(s.tag_count, 0)     as tag_count,
           coalesce(s.online_count, 0)  as online_count,
           coalesce(s.offline_count, 0) as offline_count,
           coalesce(s.pending_count, 0) as pending_count
    from tl_tag_library l
    left join (
        select library_id,
               count(*) as tag_count,
               sum(case when status = '2' then 1 else 0 end) as online_count,
               sum(case when status = '3' then 1 else 0 end) as offline_count,
               sum(case when status in ('0','1') then 1 else 0 end) as pending_count
        from tl_tag where del_flag = '0' group by library_id
    ) s on s.library_id = l.library_id
    <where>
        l.del_flag = '0'
        <if test="libraryName != null and libraryName != ''"> and (l.library_name like concat('%', #{libraryName}, '%') or l.library_code like concat('%', #{libraryName}, '%')) </if>
        <if test="category != null and category != ''"> and l.category = #{category} </if>
        <if test="tagObject != null and tagObject != ''"> and l.tag_object = #{tagObject} </if>
    </where>
    order by l.library_id
</select>
```

resultMap 中把 `tag_count/online_count/offline_count/pending_count` 映射到 4 个统计字段。

2. 所有查询带 `del_flag = '0'`；删除均为 `update ... set del_flag = '2'`。
3. `updateTagStatusBatch` / `moveTagBatch` 用 `foreach` 拼 `in (...)`，同时 `update_by/update_time` 由 service 层不好逐条赋值，XML 里直接 `update_time = sysdate()`（update_by 由 service 传参或省略，保持简单用 sysdate()）。

- [ ] **Step 3: 编译 + Commit**

Run: `mvn compile -pl ruoyi-taglibrary -am -q` → BUILD SUCCESS（XML 语法错要等启动才暴露，Task 9 联调兜底）

```bash
git add ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/mapper/ ruoyi-taglibrary/src/main/resources/mapper/
git commit -m "feat: 标签库模块mapper接口与XML"
```

---

### Task 5: Service 层（含元数据同步与状态机）

**Files:**
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/service/ITlTagLibraryService.java` + `impl/TlTagLibraryServiceImpl.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/service/ITlTagDirService.java` + `impl/TlTagDirServiceImpl.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/service/ITlTagService.java` + `impl/TlTagServiceImpl.java`

- [ ] **Step 1: `TlTagLibraryServiceImpl`**

照抄 `DpDataSourceServiceImpl` 的注入/`SecurityUtils.getUsername()` 用法。方法：

```java
List<TlTagLibrary> selectLibraryList(TlTagLibrary q);
TlTagLibrary selectLibraryById(Long id);
List<String> listBusinessTables();
int insertLibrary(TlTagLibrary library);   // 事务：校验code唯一→insert→建默认目录→syncFields（草稿快照）
int updateLibrary(TlTagLibrary library);
int deleteLibraryByIds(Long[] ids);        // 校验：status in (1,2) 拒绝；含已上线标签拒绝；级联删目录+标签（逻辑删）
int syncFields(Long libraryId);            // 增量同步，返回新增快照数
int submit(Long id);                       // 草稿/已下线→待审批 + audit_log(提交)
int audit(Long id, boolean pass, String comment); // 待审批→已上线/回草稿 + audit_log(通过/驳回)
int offline(Long id);                      // 已上线→已下线 + audit_log(下线)
```

关键实现：

1. **状态机守卫**：每次流转先 `selectLibraryById` 校验当前状态合法，非法抛 `ServiceException("当前状态不允许该操作")`。`submit` 允许 0/3；`audit` 仅 1；`offline` 仅 2。
2. **audit_log 写入**（submit/audit/offline 共用私有方法）：`action` 分别为 提交/通过/驳回/下线，`applyBy` = 操作人；audit 动作时 `auditBy` = 操作人、`auditTime` = now、`auditComment` 入参。驳回时 `toStatus` = '0'（草稿）。（注：规格 §3.5 文字写"驳回→原状态"，此处有意采用其状态图口径"驳回→草稿"——实现更简单且与图示一致，不再改回。）
3. **syncFields(Long libraryId)**（核心，完整逻辑）：
   - `selectLibraryById` 取 `sourceTable`，为空抛异常；
   - `mapper.selectTableColumns(sourceTable)`，结果为空抛 `ServiceException("源表不存在或无字段")`；
   - 查询该库现有 `field_name` 集合；
   - 对新列构造 `TlTag`：`dirId` = 默认目录 id（`parent_id=0` 且 `dir_name='默认目录'` 的第一条，没有则建）、`tagName` = comment 非空取 comment 否则 fieldName、`dataType`、`tagType` = 按下方规则推断、`createWay='同步'`、`status='0'`、`version=1`、`createBy` = 当前用户；
   - `insertTagBatch`，返回新增数。
4. **tag_type 推断规则**（私有静态方法）：
   - dataType ∈ {date, datetime, timestamp, time, year} → `日期型`
   - dataType ∈ {tinyint} 且 (comment 含 "标志"/"是否" 或 column 长度=1) → `布尔型`
   - dataType ∈ {int, bigint, smallint, decimal, float, double, numeric, mediumint} → `数值型`
   - comment 含 "/" 或 "（" 且 dataType 为 char/varchar → `选项型`
   - 其余 → `文本型`
5. `insertLibrary` 用 `@Transactional`：先 `selectLibraryByCode` 查重（重复抛 `ServiceException("标签库编码已存在")`）；insert 后建"默认目录"；若 `sourceTable` 非空则调 `syncFields`。

- [ ] **Step 2: `TlTagDirServiceImpl`**

`selectDirList(libraryId)`、`insertDir`、`updateDir`、`deleteDirById`（`countTagByDirId > 0` 抛 `ServiceException("目录下存在标签，不能删除")`）。

- [ ] **Step 3: `TlTagServiceImpl`**

```java
List<TlTag> selectTagList(TlTag q);
TlTag selectTagById(Long id);
List<Map<String,Object>> buildTree(Long libraryId, String tab); // tab: online/offline
int updateTag(TlTag tag);          // version+1；fieldName/dataType 不可改
int moveTag(Long[] tagIds, Long dirId);
int submit(Long[] ids);            // 批量，逐条校验状态 0/3，写 audit_log
int audit(Long[] ids, boolean pass, String comment);
int offline(Long[] ids);
```

**buildTree**（标签管理页左侧树数据源）：
- 库信息（`selectLibraryById`）为根节点；
- `selectDirList(libraryId)` 为二层节点；
- `selectTagList`（`tab=online` → `status='2'`；`tab=offline` → `status in ('0','1','3')`）挂到对应 dir 下；
- 节点 Map 结构：`{id: "dir-5"/"tag-9", label, count, tagType, status, children: []}`；根节点 `{id:"lib-1", label: 库名, count: 标签总数}`；每个 dir 的 count = 其下过滤后标签数。

- [ ] **Step 4: 编译 + Commit**

Run: `mvn compile -pl ruoyi-taglibrary -am -q` → BUILD SUCCESS

```bash
git add ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/service/
git commit -m "feat: 标签库模块service层（同步/状态机/审批留痕）"
```

---

### Task 6: Controller 层

**Files:**
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/controller/TlTagLibraryController.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/controller/TlTagDirController.java`
- Create: `ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/controller/TlTagController.java`

- [ ] **Step 1: `TlTagLibraryController`**（风格照抄 `DpDatasetController`，完整端点清单）

```java
@RestController
@RequestMapping("/taglibrary/library")
public class TlTagLibraryController extends BaseController {

    @Autowired
    private ITlTagLibraryService libraryService;

    /** 标签库分页列表（含卡片统计） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:list')")
    @GetMapping("/list")
    public TableDataInfo list(TlTagLibrary query) {
        startPage();
        return getDataTable(libraryService.selectLibraryList(query));
    }

    /** 可选业务表列表（新建弹窗选表） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
    @GetMapping("/tables")
    public AjaxResult tables() {
        return success(libraryService.listBusinessTables());
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
    @GetMapping("/{libraryId}")
    public AjaxResult getInfo(@PathVariable Long libraryId) {
        return success(libraryService.selectLibraryById(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:add')")
    @PostMapping
    public AjaxResult add(@RequestBody TlTagLibrary library) {
        return toAjax(libraryService.insertLibrary(library));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody TlTagLibrary library) {
        return toAjax(libraryService.updateLibrary(library));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:remove')")
    @DeleteMapping("/{libraryIds}")
    public AjaxResult remove(@PathVariable Long[] libraryIds) {
        return toAjax(libraryService.deleteLibraryByIds(libraryIds));
    }

    /** 增量同步源表字段 */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:sync')")
    @PostMapping("/sync/{libraryId}")
    public AjaxResult sync(@PathVariable Long libraryId) {
        return success("新增 " + libraryService.syncFields(libraryId) + " 个字段快照");
    }

    /** 提交审批（草稿/已下线→待审批） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:submit')")
    @PostMapping("/submit/{libraryId}")
    public AjaxResult submit(@PathVariable Long libraryId) {
        return toAjax(libraryService.submit(libraryId));
    }

    /** 审批（通过→已上线 / 驳回→草稿） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:audit')")
    @PostMapping("/audit")
    public AjaxResult audit(@RequestBody AuditRequest request) {
        return toAjax(libraryService.audit(request.getIds()[0], request.getPass(), request.getAuditComment()));
    }

    /** 下线（已上线→已下线） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:offline')")
    @PostMapping("/offline/{libraryId}")
    public AjaxResult offline(@PathVariable Long libraryId) {
        return toAjax(libraryService.offline(libraryId));
    }
}
```

（ServiceException 由全局异常处理器转 error AjaxResult，与 databroker 一致，无需 try-catch。）

- [ ] **Step 2: `TlTagDirController`** → `/taglibrary/dir`

`GET /list?libraryId=`（`dir:list`）、`POST /`（`dir:add`）、`PUT /`（`dir:edit`）、`DELETE /{dirId}`（`dir:remove`）。

- [ ] **Step 3: `TlTagController`** → `/taglibrary/tag`

```java
@PreAuthorize("@ss.hasPermi('taglibrary:tag:list')")
@GetMapping("/tree")                                    // 左侧树
public AjaxResult tree(@RequestParam Long libraryId, @RequestParam(defaultValue = "online") String tab)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:list')")
@GetMapping("/list")                                    // 字段管理抽屉的分页列表
public TableDataInfo list(TlTag query)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:query')")
@GetMapping("/{tagId}")                                 // 详情
public AjaxResult getInfo(@PathVariable Long tagId)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:edit')")
@PutMapping                                             // 编辑（version+1）
public AjaxResult edit(@RequestBody TlTag tag)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:move')")
@PutMapping("/move")                                    // 批量移动目录
public AjaxResult move(@RequestBody MoveRequest request)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:submit')")
@PostMapping("/submit")                                 // 批量提交审批
public AjaxResult submit(@RequestBody AuditRequest request)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:audit')")
@PostMapping("/audit")
public AjaxResult audit(@RequestBody AuditRequest request)

@PreAuthorize("@ss.hasPermi('taglibrary:tag:offline')")
@PostMapping("/offline")
public AjaxResult offline(@RequestBody AuditRequest request)

/** 审批日志（库/标签共用：bizType=library|tag） */
@PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
@GetMapping("/auditLogs")
public TableDataInfo auditLogs(TlAuditLog query)  // startPage + getDataTable
```

- [ ] **Step 4: 全量编译 + Commit**

Run: `mvn clean package -DskipTests -q` → BUILD SUCCESS

```bash
git add ruoyi-taglibrary/src/main/java/com/ruoyi/taglibrary/controller/
git commit -m "feat: 标签库模块controller层"
```

---

### Task 7: 后端接口冒烟验证

**Files:** 无新增（仅运行）

前置：MySQL 已执行 Task 2 两个 SQL；Redis 已启动；若 `sql/seed/ind_tag_data.sql` 的 `ind_tag_data` 表不存在则先导入。

- [ ] **Step 1: 启动后端**

Run: `java -jar ruoyi-admin/target/ruoyi-admin.jar`（推荐，Task 6 已 package 出 jar；若用 `mvn spring-boot:run -pl ruoyi-admin`，需先 `mvn install -DskipTests -q` 把新模块装进本地仓库，否则依赖解析失败），后台运行。
Expected: 启动日志无 mapper XML 解析错误，端口 8080。

- [ ] **Step 2: 登录拿 token**

```bash
curl -s -X POST http://localhost:8080/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

Expected: 返回 `token`（若启用了验证码，先调 `/captchaImage` 或临时在配置里关闭验证码 `sys.account.captchaEnabled=false`）。记下 `Authorization: Bearer <token>`。

- [ ] **Step 3: 逐接口冒烟（按依赖顺序）**

```bash
# 1. 新建标签库（关联 ind_tag_data，自动同步字段）
curl -s -X POST http://localhost:8080/taglibrary/library -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"libraryName":"客户标签库","libraryCode":"CUS_001","category":"客户维度","tagObject":"客户","sourceTable":"ind_tag_data","ownerName":"admin"}'
# Expected: code 200；DB 中 tl_tag 生成 ~70 行快照（select count(*) from tl_tag where library_id=100;）

# 2. 列表（卡片统计）
curl -s "http://localhost:8080/taglibrary/library/list?pageNum=1&pageSize=10" -H "Authorization: Bearer $TOKEN"
# Expected: rows[0] 含 tagCount/onlineCount/offlineCount/pendingCount

# 3. 标签树
curl -s "http://localhost:8080/taglibrary/tag/tree?libraryId=100&tab=offline" -H "Authorization: Bearer $TOKEN"
# Expected: 根 lib-100 下有"默认目录"，目录下挂标签节点（此时全部在 offline tab，因为都是草稿）

# 4. 标签提交审批 + 审批通过
curl -s -X POST http://localhost:8080/taglibrary/tag/submit -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"ids":[100,101]}'
curl -s -X POST http://localhost:8080/taglibrary/tag/audit -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"ids":[100,101],"pass":true,"auditComment":"同意"}'
# Expected: 两标签 status='2'，tl_audit_log 各有 提交/通过 两条记录

# 5. 库提交审批 + 通过 + 下线
curl -s -X POST http://localhost:8080/taglibrary/library/submit/100 -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8080/taglibrary/library/audit -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"ids":[100],"pass":true}'
curl -s -X POST http://localhost:8080/taglibrary/library/offline/100 -H "Authorization: Bearer $TOKEN"
# Expected: 库 status 1→2→3；非法流转（如对草稿库 offline）返回 AjaxResult body {"code":500,"msg":"当前状态不允许该操作"}
# 注意：RuoYi 全局异常处理返回 HTTP 200 + body code=500，不是 HTTP 500，别误判为后端异常

# 6. 删除校验：库含已上线标签时删除应报错
curl -s -X DELETE http://localhost:8080/taglibrary/library/100 -H "Authorization: Bearer $TOKEN"
# Expected: 报错"库内存在已上线标签"；先把标签下线/驳回后再删可成功
```

- [ ] **Step 4: 记录验证结果（不写文件，向用户汇报即可），Stop 后端进程**

- [ ] **Step 5: Commit（若有联调中修复的代码）**

```bash
git add -A ruoyi-taglibrary
git commit -m "fix: 标签库后端联调修复"   # 无修复则跳过
```

---

### Task 8: 前端 API 模块

**Files:**
- Create: `ruoyi-ui/src/api/taglibrary/library.js`
- Create: `ruoyi-ui/src/api/taglibrary/dir.js`
- Create: `ruoyi-ui/src/api/taglibrary/tag.js`

- [ ] **Step 1: 三个 api 文件**（风格照抄 `ruoyi-ui/src/api/databroker/datasource.js`，`import request from '@/utils/request'`）

`library.js` 导出：`listLibrary(query)` GET `/taglibrary/library/list`；`listBusinessTables()` GET `/taglibrary/library/tables`；`getLibrary(id)`；`addLibrary(data)` POST；`updateLibrary(data)` PUT；`delLibrary(ids)` DELETE `/taglibrary/library/${ids}`；`syncLibrary(id)` POST `/taglibrary/library/sync/${id}`；`submitLibrary(id)` POST `/taglibrary/library/submit/${id}`；`auditLibrary(data)` POST `/taglibrary/library/audit`；`offlineLibrary(id)` POST `/taglibrary/library/offline/${id}`；`listAuditLogs(query)` GET `/taglibrary/tag/auditLogs`。

`dir.js` 导出：`listDir(libraryId)`、`addDir(data)`、`updateDir(data)`、`delDir(dirId)`。

`tag.js` 导出：`tagTree(libraryId, tab)` GET `/taglibrary/tag/tree`；`listTag(query)`；`getTag(tagId)`；`updateTag(data)`；`moveTag(data)` PUT `/taglibrary/tag/move`；`submitTag(data)`、`auditTag(data)`、`offlineTag(data)` POST 对应路径。

- [ ] **Step 2: Commit**

```bash
git add ruoyi-ui/src/api/taglibrary/
git commit -m "feat: 标签库前端api模块"
```

---

### Task 9: 标签库管理页（卡片列表）`ruoyi-ui/src/views/taglibrary/list/index.vue`

**Files:**
- Create: `ruoyi-ui/src/views/taglibrary/list/index.vue`

整体布局与交互照抄 `ruoyi-ui/src/views/databroker/datasource/index.vue` 的页面骨架（`data` 里 `loading/queryParams/total`、方法里 `getList/handleXxx/submitForm` 命名、`v-hasPermi` 指令、字典用 `<dict-tag>` + `dicts: ['tag_object','tag_library_category']`）。

- [ ] **Step 1: 页面骨架与工具栏**

- `data`：`libraryList: []`、`viewMode: 'card'`、`queryParams: { pageNum:1, pageSize:12, libraryName:'', category:'', tagObject:'' }`、`dicts: ['tag_object', 'tag_library_category']`。
- 工具栏一行：`+ 新建标签库`（`type="primary"`，`v-hasPermi="['taglibrary:library:add']"`）｜右侧：`el-input` 搜索（v-model `queryParams.libraryName`，单个输入同时匹配名称或编码——后端 XML 已按 `or` 处理，@change 查询）+ 两个 `el-select`（标签对象、分类，options 来自字典，`clearable`）+ 视图切换两个 `el-button`（卡片 `el-icon-menu` / 列表 `el-icon-tickets`，小尺寸 button-group，激活态高亮）。
- 列表模式兜底：直接复用 RuoYi 标准 `el-table`（列：名称/编码/分类/标签对象/负责人/更新时间/统计/操作），保证 `viewMode='list'` 可用即可，不精修样式。

- [ ] **Step 2: 卡片网格**

`el-row :gutter="16"` + 每卡片 `el-col :span="8"`（一行 3 张，参考截图2 版式）。卡片 `el-card shadow="hover"` 内容：

```
第一行：libraryName（加粗）+ 右侧状态 dict-tag（草稿/待审批/已上线/已下线，自建 map：{0:info,1:warning,2:success,3:danger}，因 status 非字典）
第二行：所属分类：category | 标签对象：tagObject
第三行：负责人：ownerName | 更新时间：updateTime
第四行：上线 onlineCount（大号数字）｜待发布 pendingCount ｜下线 offlineCount（三列均分）
第五行：关联宽表：sourceTable（弱化小字）
底部分割线 + 两个按钮（见 Step 3）
```

- [ ] **Step 3: 卡片底部双按钮（核心微调）**

```html
<div class="card-footer">
  <el-button type="text" icon="el-icon-price-tag"
    @click="goTagManage(row)">标签管理</el-button>
  <el-dropdown trigger="click" @command="cmd => handleMore(cmd, row)">
    <el-button type="text">更多<i class="el-icon-arrow-down el-icon--right"/></el-button>
    <el-dropdown-menu slot="dropdown">
      <el-dropdown-item command="fields" icon="el-icon-set-up">字段管理</el-dropdown-item>
      <el-dropdown-item v-if="row.status==='0'||row.status==='3'" command="submit" icon="el-icon-upload2">提交上线</el-dropdown-item>
      <el-dropdown-item v-if="row.status==='2'" command="offline" icon="el-icon-download">下线</el-dropdown-item>
      <el-dropdown-item command="audit" icon="el-icon-s-check">审批管理</el-dropdown-item>
      <el-dropdown-item command="remove" icon="el-icon-delete" divided>删除标签库</el-dropdown-item>
    </el-dropdown-menu>
  </el-dropdown>
</div>
```

```js
goTagManage(row) { this.$router.push({ path: '/taglibrary/tags', query: { libraryId: row.libraryId } }) },
handleMore(cmd, row) {
  if (cmd === 'fields') this.openFieldDrawer(row)
  else if (cmd === 'submit') this.$confirm('提交后将进入审批流，确认提交上线？').then(() => submitLibrary(row.libraryId)).then(() => { this.$modal.msgSuccess('已提交审批'); this.getList() })
  else if (cmd === 'offline') this.$confirm('确认下线该标签库？').then(() => offlineLibrary(row.libraryId)).then(() => { this.$modal.msgSuccess('已下线'); this.getList() })
  else if (cmd === 'audit') this.openAuditDialog(row)
  else if (cmd === 'remove') this.$confirm('确认删除标签库"' + row.libraryName + '"？', '警告', { type: 'warning' }).then(() => delLibrary(row.libraryId)).then(() => { this.$modal.msgSuccess('删除成功'); this.getList() })
}
```

权限：dropdown 各 item 外层包 `v-hasPermi`（如 `<el-dropdown-item v-hasPermi="['taglibrary:library:remove']" ...>`）。

- [ ] **Step 4: 新建/编辑弹窗**

`el-dialog`，表单项：`libraryName`（必填）、`libraryCode`（必填，编辑时 disabled）、`tagObject`（字典 select，必填）、`category`（字典 select）、`ownerName`、`sourceTable`（select，options 来自 `listBusinessTables()`，新建必填、编辑 disabled；默认选项含 `ind_tag_data`）、`remark`。提交：`addLibrary`/`updateLibrary` → 成功后提示"已创建并同步 N 个字段快照"（后端 add 返回影响行数即可，提示用 msgSuccess 简化为"创建成功，字段已同步"）。

- [ ] **Step 5: 字段管理抽屉（"更多→字段管理"）**

`el-drawer size="60%"`：内嵌标准 RuoYi 表格（`listTag({libraryId, pageNum, pageSize})` 分页），列：字段名 fieldName、标签名 tagName（可编辑弹窗）、目录（select 选项来自 `listDir`）、类型 tagType（`<dict-tag :options="dict.type.tag_type">`）、状态（map 同卡片）、操作（编辑：弹窗改 tagName/dirId/tagType/businessCaliber/techCaliber/validPeriod/updateCycle，提交 `updateTag`）。顶部一个"同步字段"按钮（`syncLibrary`）。`dicts` 追加 `'tag_type','tag_update_cycle'`。

- [ ] **Step 6: 审批管理弹窗（"更多→审批管理"）**

`el-dialog width="700px"`：上半部分若 `row.status==='1'`（待审批）显示操作区——`el-input type="textarea"` 审批意见 + "通过"（success）/"驳回"（danger）按钮，调 `auditLibrary({ids:[row.libraryId], pass, auditComment})`；下半部分审批记录表格（`listAuditLogs({bizType:'library', bizId:row.libraryId})`，列：动作/变更前/变更后/申请人/审批人/审批时间/意见）。

- [ ] **Step 7: 页面自查**

`cd ruoyi-ui && npm run dev` 启动前端，浏览器打开标签库管理菜单：卡片渲染、搜索/筛选、新建（同步字段）、更多下拉四功能、底部跳转均可用。截图自评与截图2 版式接近。

- [ ] **Step 8: Commit**

```bash
git add ruoyi-ui/src/views/taglibrary/list/
git commit -m "feat: 标签库管理卡片列表页"
```

---

### Task 10: 标签管理页（树+详情）`ruoyi-ui/src/views/taglibrary/tags/index.vue`

**Files:**
- Create: `ruoyi-ui/src/views/taglibrary/tags/index.vue`

- [ ] **Step 1: 页面布局（两栏）**

左侧 `el-col :span="6"`，右侧 `el-col :span="18"`（`el-row :gutter="12"`）。

左侧面板自上而下：
1. 标签库 `el-select`（options 来自 `listLibrary({pageSize:100})`，v-model `currentLibraryId`，@change 重载树）；mounted 时取 `this.$route.query.libraryId`，无则默认列表第一个。
2. 搜索 `el-input`（`filter-node-method` 过滤树节点 label）。
3. `el-tabs` 两个 tab：`上线标签`(name=online) / `下线标签`(name=offline)，@tab-click 重载树。
4. `el-tree`：`:data="treeData"`、`node-key="id"`、`:props="{label:'label',children:'children'}"`、`highlight-current`、@node-click 处理；自定义节点内容：

```html
<span class="custom-tree-node" slot-scope="{ data }">
  <span v-if="data.tagType" class="tag-dot" :style="{background: tagTypeColor(data.tagType)}"></span>
  <span>{{ data.label }}</span>
  <span v-if="data.count !== undefined" class="node-count">[{{ data.count }}]</span>
</span>
```

`tagTypeColor` map：`{选项型:'#67C23A', 布尔型:'#E6A23C', 数值型:'#409EFF', 文本型:'#909399', 日期型:'#F56C6C'}`。树下方放一行图例小字（五种颜色圆点+类型名，对应截图3 底部）。`dicts: ['tag_type','tag_update_cycle']`。

- [ ] **Step 2: 树节点点击行为**

- 点 `tag-*` 节点 → `getTag(id)` 填充右侧详情；
- 点 `dir-*` 节点 → 右侧显示该目录说明或空态（简单实现：不做任何事/显示第一个标签）；
- 树上方（或右键菜单，保持简单用行内小按钮区）提供：新建目录 / 重命名目录 / 删除目录 / 移动标签到目录（弹窗选目录，调 `moveTag`）/ 提交审批 / 下线（对选中标签，按状态显示，`submitTag`/`offlineTag`）。审批操作不在本页（规格约定）。

- [ ] **Step 3: 右侧标签详情（截图3 版式）**

```html
<el-card v-if="tagDetail.tagId">
  <div slot="header">标签详情
    <el-button style="float:right" type="text" v-hasPermi="['taglibrary:tag:edit']" @click="openTagEdit">编辑</el-button>
  </div>
  <el-row>
    <el-col :span="16">
      <!-- 基础信息 -->
      <div class="section-title">▎基础信息</div>
      <el-descriptions :column="3" border size="small">  <!-- 若无 el-descriptions（element-ui 2.15 有），退化用 el-row 三列 label/value 排版 -->
        标签名称 tagName | 数值类型 dataType | 标签类型 <dict-tag tag_type>
        有效日期 validPeriod | 更新周期 updateCycle | 创建方式 createWay
      </el-descriptions>
      <div class="section-title">▎口径信息</div>
      <el-descriptions :column="1" border size="small">
        业务口径 businessCaliber（空显示 /）| 技术口径 techCaliber
      </el-descriptions>
      <div class="section-title">▎技术信息</div>
      <el-descriptions :column="2" border size="small">
        字段配置 fieldName | 源数据表 sourceTable（取库信息）
      </el-descriptions>
    </el-col>
    <el-col :span="8">
      <div class="section-title">▎版本信息</div>
      <el-descriptions :column="1" border size="small">
        所属子库 libraryName | 创建时间 createTime | 创建人 createBy
        版本 V{{version}} | 最近修改人 updateBy | 最近修改时间 updateTime
      </el-descriptions>
    </el-col>
  </el-row>
</el-card>
<el-empty v-else description="请选择左侧标签"/>
```

（`element-ui` 版本若无 `el-descriptions`/`el-empty`，用等价的描述列表/div 空态替代，先查 `ruoyi-ui/package.json` 的 element-ui 版本再定。）

- [ ] **Step 4: 编辑标签弹窗**

字段：tagName（必填）、dirId（select）、tagType（字典 select）、businessCaliber、techCaliber、validPeriod、updateCycle（字典 select）。提交 `updateTag` → 刷新树与详情（版本号由后端 +1）。

- [ ] **Step 5: 页面自查**

两个入口验证：① 菜单"标签管理"直进 → 默认选中第一个库；② 卡片页"标签管理"按钮跳入 → 按 query.libraryId 预选。上线/下线 tab 切换、树数量角标、详情展示、编辑、目录增删、移动目录、提交审批均可用。

- [ ] **Step 6: Commit**

```bash
git add ruoyi-ui/src/views/taglibrary/tags/
git commit -m "feat: 标签管理树与详情页"
```

---

### Task 11: 端到端验收

**Files:** 无（仅运行核对）

- [ ] **Step 1: 全量构建**

Run: `mvn clean package -DskipTests -q` 且 `cd ruoyi-ui && npm run build:prod` 均成功。

- [ ] **Step 2: 按规格第 8 节走查清单（启动前后端，逐项人工确认）**

1. 菜单出现顶级"标签库管理" → 两个子菜单可进入
2. 新建标签库（选 ind_tag_data）→ 卡片出现、字段快照已同步（约 70 个）
3. 搜索 / 标签对象筛选 / 分类筛选 / 卡片-列表切换
4. 卡片"标签管理"按钮 → 跳入标签管理页且预选该库
5. 标签管理页：上线/下线 tab、树、详情、编辑（版本+1）、目录增删、移动目录、批量提交审批
6. 卡片"更多"：字段管理（改中文名/目录/类型）、提交上线→审批管理（通过/驳回+记录）、下线、删除（含已上线标签时删除被拒）
7. 重复同步幂等（再点同步不重复生成快照）

- [ ] **Step 3: 向用户汇报验收结果，逐条列明已通过/未通过项；未通过项修复后复验。**

```bash
git add -A
git commit -m "chore: 标签库管理模块验收修复"   # 有修复才提交
```
