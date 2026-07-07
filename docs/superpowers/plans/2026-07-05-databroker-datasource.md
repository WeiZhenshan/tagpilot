# 数据代理模块-数据源管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `ruoyi-databroker` module with full datasource management (CRUD, connection test, metadata sync, table/column browse, operation logs) plus the Vue 2 frontend page.

**Architecture:** New Maven module `ruoyi-databroker` loaded by `ruoyi-admin`. Reuses existing JWT/Redis auth. MVC layered: Controller → Service → Mapper/XML. Independent JDBC connections read `information_schema` from target databases. AES/GCM password encryption.

**Tech Stack:** Java 8, Spring Boot 2.5, MyBatis, MySQL, Vue 2, Element UI, Axios

## Global Constraints

- Java 8 (no Java 9+ APIs)
- All domain classes extend `BaseEntity` (from `ruoyi-common`)
- Controllers extend `BaseController`, use `@PreAuthorize("@ss.hasPermi('...')")`
- Response types: `AjaxResult` (single), `TableDataInfo` (paginated)
- MyBatis XML mappers in `src/main/resources/mapper/databroker/`
- Frontend uses `@/utils/request` for API calls, `v-hasPermi` for permission checks
- Password must be reversible (AES/GCM) — NOT BCrypt
- Never expose plaintext password in API responses or logs
- Menu IDs: 2000–2007

---

### Task 1: Create Maven module structure and register dependencies

**Files:**
- Create: `ruoyi-databroker/pom.xml`
- Modify: `pom.xml` (root, lines 224–231 for modules, after line 218 for dependencyManagement)
- Modify: `ruoyi-admin/pom.xml` (after line 62, before `</dependencies>`)
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/` (package layout dirs)
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/` (dir)
- Create: `ruoyi-databroker/src/main/resources/sql/` (dir)

**Interfaces:**
- Produces: Maven module `com.ruoyi:ruoyi-databroker:3.9.2` available to `ruoyi-admin`

- [ ] **Step 1: Create ruoyi-databroker/pom.xml**

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
    <artifactId>ruoyi-databroker</artifactId>

    <description>
        databroker数据代理模块
    </description>

    <dependencies>
        <!-- MySQL驱动，供目标库元数据采集使用 -->
        <dependency>
            <groupId>mysql</groupId>
            <artifactId>mysql-connector-java</artifactId>
        </dependency>

        <!-- 复用RuoYi鉴权、Web、MyBatis、Redis等基础能力 -->
        <dependency>
            <groupId>com.ruoyi</groupId>
            <artifactId>ruoyi-framework</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: Register module in root pom.xml**

Add to `<modules>` block:
```xml
<module>ruoyi-databroker</module>
```

Add to `<dependencyManagement>` block (after line 218, the `ruoyi-common` entry):
```xml
<!-- 数据代理模块-->
<dependency>
    <groupId>com.ruoyi</groupId>
    <artifactId>ruoyi-databroker</artifactId>
    <version>${ruoyi.version}</version>
</dependency>
```

- [ ] **Step 3: Add ruoyi-databroker dependency in ruoyi-admin/pom.xml**

Add after the `ruoyi-generator` dependency (before `</dependencies>`):
```xml
<!-- 数据代理模块 -->
<dependency>
    <groupId>com.ruoyi</groupId>
    <artifactId>ruoyi-databroker</artifactId>
</dependency>
```

- [ ] **Step 4: Create package directory structure**

Run: `mkdir -p ruoyi-databroker/src/main/java/com/ruoyi/databroker/{controller,domain/dto,domain/vo,mapper,service/impl,metadata,crypto,config}`
Run: `mkdir -p ruoyi-databroker/src/main/resources/{mapper/databroker,sql}`

- [ ] **Step 5: Verify Maven build**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add ruoyi-databroker/pom.xml pom.xml ruoyi-admin/pom.xml
git commit -m "feat: add ruoyi-databroker Maven module"
```

---

### Task 2: Add databroker configuration to application.yml

**Files:**
- Modify: `ruoyi-admin/src/main/resources/application.yml` (xss section and new databroker section)

**Interfaces:**
- Produces: `databroker.crypto.secret` and `databroker.jdbc.*` properties available for injection

- [ ] **Step 1: Update XSS urlPatterns to include /databroker/***

Change line 136 from:
```yaml
  urlPatterns: /system/*,/monitor/*,/tool/*
```
to:
```yaml
  urlPatterns: /system/*,/monitor/*,/tool/*,/databroker/*
```

- [ ] **Step 2: Add databroker config section at end of application.yml**

Append:
```yaml
# 数据代理模块配置
databroker:
  crypto:
    secret: ${DATABROKER_CRYPTO_SECRET:change-me-32-bytes-secret-key}
  jdbc:
    connectTimeout: 5000
    socketTimeout: 10000
```

- [ ] **Step 3: Commit**

```bash
git add ruoyi-admin/src/main/resources/application.yml
git commit -m "feat: add databroker configuration to application.yml"
```

---

### Task 3: Create database schema and menu SQL files

**Files:**
- Create: `ruoyi-databroker/src/main/resources/sql/databroker_schema.sql`
- Create: `ruoyi-databroker/src/main/resources/sql/databroker_menu.sql`

**Interfaces:**
- Produces: SQL files ready for manual execution against the `ry` database

- [ ] **Step 1: Create databroker_schema.sql**

Write the file with all 5 tables from the dev doc §6. Each CREATE TABLE exactly as specified:
- `dp_datasource_catalog`
- `dp_datasource`
- `dp_meta_table`
- `dp_meta_column`
- `dp_datasource_log`

(Full SQL content from doc §6 — use the exact DDL from the development document.)

- [ ] **Step 2: Create databroker_menu.sql**

Write the file with menu inserts from doc §7, using IDs 2000-2007:
```sql
insert into sys_menu values('2000', '数据代理', '0', '5', 'databroker', null, '', '', 1, 0, 'M', '0', '0', '', 'database', 'admin', sysdate(), '', null, '数据代理目录');
insert into sys_menu values('2001', '数据源管理', '2000', '1', 'datasource', 'databroker/datasource/index', '', '', 1, 0, 'C', '0', '0', 'databroker:datasource:list', 'druid', 'admin', sysdate(), '', null, '数据源管理菜单');
insert into sys_menu values('2002', '数据源查询', '2001', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:query', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2003', '数据源新增', '2001', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:add', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2004', '数据源修改', '2001', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:edit', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2005', '数据源删除', '2001', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2006', '测试连接', '2001', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:test', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2007', '同步元数据', '2001', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'databroker:datasource:sync', '#', 'admin', sysdate(), '', null, '');
```

- [ ] **Step 3: Commit**

```bash
git add ruoyi-databroker/src/main/resources/sql/
git commit -m "feat: add databroker schema and menu SQL"
```

---

### Task 4: Create domain entities

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpDataSourceCatalog.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpDataSource.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpMetaTable.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpMetaColumn.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/DpDataSourceLog.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/dto/TreeNode.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/vo/SyncResultVO.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/vo/TestResultVO.java`

**Interfaces:**
- Produces: Domain classes usable by Mapper, Service, and Controller layers
- Each domain extends `BaseEntity` and follows existing RuoYi patterns (getter/setter + toString)

- [ ] **Step 1: Create DpDataSourceCatalog.java**

```java
package com.ruoyi.databroker.domain;

import com.ruoyi.common.core.domain.TreeEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

public class DpDataSourceCatalog extends TreeEntity {
    private static final long serialVersionUID = 1L;

    private Long catalogId;
    private String catalogName;
    private String status;

    public Long getCatalogId() { return catalogId; }
    public void setCatalogId(Long catalogId) { this.catalogId = catalogId; }
    public String getCatalogName() { return catalogName; }
    public void setCatalogName(String catalogName) { this.catalogName = catalogName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("catalogId", getCatalogId())
            .append("parentId", getParentId())
            .append("catalogName", getCatalogName())
            .append("orderNum", getOrderNum())
            .append("status", getStatus())
            .append("createBy", getCreateBy())
            .append("createTime", getCreateTime())
            .toString();
    }
}
```

- [ ] **Step 2: Create DpDataSource.java**

```java
package com.ruoyi.databroker.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

public class DpDataSource extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long datasourceId;
    private Long catalogId;
    private String sourceName;
    private String sourceType;
    private String host;
    private Integer port;
    private String databaseName;
    private String username;
    private String passwordCipher;
    private String password;  // transient, for form binding only
    private String dbVersion;
    private String usePool;
    private String useSsl;
    private String caCert;
    private String jdbcParams;
    private String status;
    private Long usageCount;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date lastSyncTime;
    private String lastSyncStatus;
    private String lastErrorMsg;
    private String delFlag;

    // getters and setters
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public Long getCatalogId() { return catalogId; }
    public void setCatalogId(Long catalogId) { this.catalogId = catalogId; }
    public String getSourceName() { return sourceName; }
    public void setSourceName(String sourceName) { this.sourceName = sourceName; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public String getHost() { return host; }
    public void setHost(String host) { this.host = host; }
    public Integer getPort() { return port; }
    public void setPort(Integer port) { this.port = port; }
    public String getDatabaseName() { return databaseName; }
    public void setDatabaseName(String databaseName) { this.databaseName = databaseName; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getPasswordCipher() { return passwordCipher; }
    public void setPasswordCipher(String passwordCipher) { this.passwordCipher = passwordCipher; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public String getDbVersion() { return dbVersion; }
    public void setDbVersion(String dbVersion) { this.dbVersion = dbVersion; }
    public String getUsePool() { return usePool; }
    public void setUsePool(String usePool) { this.usePool = usePool; }
    public String getUseSsl() { return useSsl; }
    public void setUseSsl(String useSsl) { this.useSsl = useSsl; }
    public String getCaCert() { return caCert; }
    public void setCaCert(String caCert) { this.caCert = caCert; }
    public String getJdbcParams() { return jdbcParams; }
    public void setJdbcParams(String jdbcParams) { this.jdbcParams = jdbcParams; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getUsageCount() { return usageCount; }
    public void setUsageCount(Long usageCount) { this.usageCount = usageCount; }
    public Date getLastSyncTime() { return lastSyncTime; }
    public void setLastSyncTime(Date lastSyncTime) { this.lastSyncTime = lastSyncTime; }
    public String getLastSyncStatus() { return lastSyncStatus; }
    public void setLastSyncStatus(String lastSyncStatus) { this.lastSyncStatus = lastSyncStatus; }
    public String getLastErrorMsg() { return lastErrorMsg; }
    public void setLastErrorMsg(String lastErrorMsg) { this.lastErrorMsg = lastErrorMsg; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("datasourceId", getDatasourceId())
            .append("sourceName", getSourceName())
            .append("host", getHost())
            .append("port", getPort())
            .append("databaseName", getDatabaseName())
            .append("username", getUsername())
            .toString();
    }
}
```

- [ ] **Step 3: Create DpMetaTable.java**

```java
package com.ruoyi.databroker.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

public class DpMetaTable extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long tableId;
    private Long datasourceId;
    private String objectName;
    private String objectType;
    private String tableComment;
    private String cnName;
    private Long rowCount;
    private Integer columnCount;
    private Long usageCount;
    private String syncBatchNo;
    private String status;

    // getters and setters
    public Long getTableId() { return tableId; }
    public void setTableId(Long tableId) { this.tableId = tableId; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public String getObjectName() { return objectName; }
    public void setObjectName(String objectName) { this.objectName = objectName; }
    public String getObjectType() { return objectType; }
    public void setObjectType(String objectType) { this.objectType = objectType; }
    public String getTableComment() { return tableComment; }
    public void setTableComment(String tableComment) { this.tableComment = tableComment; }
    public String getCnName() { return cnName; }
    public void setCnName(String cnName) { this.cnName = cnName; }
    public Long getRowCount() { return rowCount; }
    public void setRowCount(Long rowCount) { this.rowCount = rowCount; }
    public Integer getColumnCount() { return columnCount; }
    public void setColumnCount(Integer columnCount) { this.columnCount = columnCount; }
    public Long getUsageCount() { return usageCount; }
    public void setUsageCount(Long usageCount) { this.usageCount = usageCount; }
    public String getSyncBatchNo() { return syncBatchNo; }
    public void setSyncBatchNo(String syncBatchNo) { this.syncBatchNo = syncBatchNo; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("tableId", getTableId())
            .append("objectName", getObjectName())
            .append("objectType", getObjectType())
            .append("cnName", getCnName())
            .toString();
    }
}
```

- [ ] **Step 4: Create DpMetaColumn.java**

```java
package com.ruoyi.databroker.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

public class DpMetaColumn extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long columnId;
    private Long tableId;
    private Long datasourceId;
    private String objectName;
    private String columnName;
    private Integer ordinalPosition;
    private String columnType;
    private String dataType;
    private String isNullable;
    private String columnDefault;
    private String columnComment;
    private String isPk;
    private String isFk;
    private String referencedTableName;
    private String referencedColumnName;
    private String syncBatchNo;

    // getters and setters
    public Long getColumnId() { return columnId; }
    public void setColumnId(Long columnId) { this.columnId = columnId; }
    public Long getTableId() { return tableId; }
    public void setTableId(Long tableId) { this.tableId = tableId; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public String getObjectName() { return objectName; }
    public void setObjectName(String objectName) { this.objectName = objectName; }
    public String getColumnName() { return columnName; }
    public void setColumnName(String columnName) { this.columnName = columnName; }
    public Integer getOrdinalPosition() { return ordinalPosition; }
    public void setOrdinalPosition(Integer ordinalPosition) { this.ordinalPosition = ordinalPosition; }
    public String getColumnType() { return columnType; }
    public void setColumnType(String columnType) { this.columnType = columnType; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getIsNullable() { return isNullable; }
    public void setIsNullable(String isNullable) { this.isNullable = isNullable; }
    public String getColumnDefault() { return columnDefault; }
    public void setColumnDefault(String columnDefault) { this.columnDefault = columnDefault; }
    public String getColumnComment() { return columnComment; }
    public void setColumnComment(String columnComment) { this.columnComment = columnComment; }
    public String getIsPk() { return isPk; }
    public void setIsPk(String isPk) { this.isPk = isPk; }
    public String getIsFk() { return isFk; }
    public void setIsFk(String isFk) { this.isFk = isFk; }
    public String getReferencedTableName() { return referencedTableName; }
    public void setReferencedTableName(String referencedTableName) { this.referencedTableName = referencedTableName; }
    public String getReferencedColumnName() { return referencedColumnName; }
    public void setReferencedColumnName(String referencedColumnName) { this.referencedColumnName = referencedColumnName; }
    public String getSyncBatchNo() { return syncBatchNo; }
    public void setSyncBatchNo(String syncBatchNo) { this.syncBatchNo = syncBatchNo; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("columnId", getColumnId())
            .append("objectName", getObjectName())
            .append("columnName", getColumnName())
            .append("ordinalPosition", getOrdinalPosition())
            .toString();
    }
}
```

- [ ] **Step 5: Create DpDataSourceLog.java**

```java
package com.ruoyi.databroker.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;

public class DpDataSourceLog {
    private Long logId;
    private Long datasourceId;
    private String logType;
    private String operatorName;
    private String result;
    private String message;
    private String detailJson;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date operTime;

    // getters and setters
    public Long getLogId() { return logId; }
    public void setLogId(Long logId) { this.logId = logId; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public String getLogType() { return logType; }
    public void setLogType(String logType) { this.logType = logType; }
    public String getOperatorName() { return operatorName; }
    public void setOperatorName(String operatorName) { this.operatorName = operatorName; }
    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getDetailJson() { return detailJson; }
    public void setDetailJson(String detailJson) { this.detailJson = detailJson; }
    public Date getOperTime() { return operTime; }
    public void setOperTime(Date operTime) { this.operTime = operTime; }
}
```

- [ ] **Step 6: Create TreeNode.java (DTO for tree response)**

```java
package com.ruoyi.databroker.domain.dto;

import java.util.ArrayList;
import java.util.List;

public class TreeNode {
    private String id;       // "cat_10" or "ds_100"
    private String parentId; // "0" or "cat_10"
    private String label;
    private String nodeType; // "catalog" or "datasource"
    private Long catalogId;
    private Long datasourceId;
    private String sourceType;
    private String status;
    private List<TreeNode> children = new ArrayList<>();

    // getters and setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getParentId() { return parentId; }
    public void setParentId(String parentId) { this.parentId = parentId; }
    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }
    public String getNodeType() { return nodeType; }
    public void setNodeType(String nodeType) { this.nodeType = nodeType; }
    public Long getCatalogId() { return catalogId; }
    public void setCatalogId(Long catalogId) { this.catalogId = catalogId; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public List<TreeNode> getChildren() { return children; }
    public void setChildren(List<TreeNode> children) { this.children = children; }
}
```

- [ ] **Step 7: Create SyncResultVO.java**

```java
package com.ruoyi.databroker.domain.vo;

public class SyncResultVO {
    private int tableCount;
    private int viewCount;
    private int columnCount;
    private String syncBatchNo;

    public int getTableCount() { return tableCount; }
    public void setTableCount(int tableCount) { this.tableCount = tableCount; }
    public int getViewCount() { return viewCount; }
    public void setViewCount(int viewCount) { this.viewCount = viewCount; }
    public int getColumnCount() { return columnCount; }
    public void setColumnCount(int columnCount) { this.columnCount = columnCount; }
    public String getSyncBatchNo() { return syncBatchNo; }
    public void setSyncBatchNo(String syncBatchNo) { this.syncBatchNo = syncBatchNo; }
}
```

- [ ] **Step 8: Create TestResultVO.java**

```java
package com.ruoyi.databroker.domain.vo;

public class TestResultVO {
    private String dbVersion;
    private String databaseName;

    public String getDbVersion() { return dbVersion; }
    public void setDbVersion(String dbVersion) { this.dbVersion = dbVersion; }
    public String getDatabaseName() { return databaseName; }
    public void setDatabaseName(String databaseName) { this.databaseName = databaseName; }
}
```

- [ ] **Step 9: Verify compilation**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 10: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/domain/
git commit -m "feat: add databroker domain entities and DTOs"
```

---

### Task 5: Create Mapper interfaces and XML files

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/DpDataSourceCatalogMapper.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/DpDataSourceMapper.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/DpMetaTableMapper.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/DpMetaColumnMapper.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/DpDataSourceLogMapper.java`
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceCatalogMapper.xml`
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceMapper.xml`
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/DpMetaTableMapper.xml`
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/DpMetaColumnMapper.xml`
- Create: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceLogMapper.xml`

**Interfaces:**
- Consumes: Domain classes from Task 4
- Produces: Full Mapper layer for all 5 tables

- [ ] **Step 1: Create DpDataSourceCatalogMapper.java**

```java
package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface DpDataSourceCatalogMapper {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);
}
```

- [ ] **Step 2: Create DpDataSourceMapper.java**

```java
package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSource;

public interface DpDataSourceMapper {
    List<DpDataSource> selectDataSourceList(DpDataSource dataSource);
    DpDataSource selectDataSourceById(Long datasourceId);
    DpDataSource selectDataSourceByName(String sourceName);
    int insertDataSource(DpDataSource dataSource);
    int updateDataSource(DpDataSource dataSource);
    int deleteDataSourceById(Long datasourceId);
    int deleteDataSourceByIds(Long[] datasourceIds);
    int incrementUsageCount(Long datasourceId);
}
```

- [ ] **Step 3: Create DpMetaTableMapper.java**

```java
package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpMetaTable;

public interface DpMetaTableMapper {
    List<DpMetaTable> selectTableList(DpMetaTable table);
    DpMetaTable selectTableById(Long tableId);
    DpMetaTable selectTableByDsAndName(Long datasourceId, String objectName);
    int insertTable(DpMetaTable table);
    int updateTable(DpMetaTable table);
    int updateTableCnName(Long tableId, String cnName);
    int markTableInvalid(Long datasourceId, String syncBatchNo);
    int deleteColumnsByTableId(Long tableId);
}
```

- [ ] **Step 4: Create DpMetaColumnMapper.java**

```java
package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpMetaColumn;

public interface DpMetaColumnMapper {
    List<DpMetaColumn> selectColumnList(DpMetaColumn column);
    List<DpMetaColumn> selectColumnsByTableId(Long tableId);
    DpMetaColumn selectColumnByTableAndName(Long tableId, String columnName);
    int insertColumn(DpMetaColumn column);
    int updateColumn(DpMetaColumn column);
    int deleteColumnsByTableId(Long tableId);
    int deleteOrphanColumns(Long datasourceId, String syncBatchNo);
}
```

- [ ] **Step 5: Create DpDataSourceLogMapper.java**

```java
package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceLog;

public interface DpDataSourceLogMapper {
    List<DpDataSourceLog> selectLogList(DpDataSourceLog log);
    int insertLog(DpDataSourceLog log);
}
```

- [ ] **Step 6: Create MyBatis XML for DpDataSourceCatalogMapper**

File: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceCatalogMapper.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper">

    <resultMap type="DpDataSourceCatalog" id="CatalogResult">
        <id     property="catalogId"    column="catalog_id"    />
        <result property="parentId"     column="parent_id"     />
        <result property="ancestors"    column="ancestors"     />
        <result property="catalogName"  column="catalog_name"  />
        <result property="orderNum"     column="order_num"     />
        <result property="status"       column="status"        />
        <result property="createBy"     column="create_by"     />
        <result property="createTime"   column="create_time"   />
        <result property="updateBy"     column="update_by"     />
        <result property="updateTime"   column="update_time"   />
        <result property="remark"       column="remark"        />
    </resultMap>

    <sql id="selectVo">
        select catalog_id, parent_id, ancestors, catalog_name, order_num, status,
               create_by, create_time, update_by, update_time, remark
        from dp_datasource_catalog
    </sql>

    <select id="selectCatalogList" parameterType="DpDataSourceCatalog" resultMap="CatalogResult">
        <include refid="selectVo"/>
        <where>
            <if test="catalogName != null and catalogName != ''">and catalog_name like concat('%', #{catalogName}, '%')</if>
            <if test="status != null and status != ''">and status = #{status}</if>
        </where>
        order by parent_id, order_num
    </select>

    <select id="selectCatalogById" parameterType="Long" resultMap="CatalogResult">
        <include refid="selectVo"/> where catalog_id = #{catalogId}
    </select>

    <insert id="insertCatalog" parameterType="DpDataSourceCatalog" useGeneratedKeys="true" keyProperty="catalogId">
        insert into dp_datasource_catalog (
            parent_id, ancestors, catalog_name, order_num, status, create_by, create_time, remark
        ) values (
            #{parentId}, #{ancestors}, #{catalogName}, #{orderNum}, #{status}, #{createBy}, sysdate(), #{remark}
        )
    </insert>

    <update id="updateCatalog" parameterType="DpDataSourceCatalog">
        update dp_datasource_catalog
        <set>
            <if test="parentId != null">parent_id = #{parentId},</if>
            <if test="ancestors != null">ancestors = #{ancestors},</if>
            <if test="catalogName != null">catalog_name = #{catalogName},</if>
            <if test="orderNum != null">order_num = #{orderNum},</if>
            <if test="status != null">status = #{status},</if>
            <if test="updateBy != null">update_by = #{updateBy},</if>
            <if test="remark != null">remark = #{remark},</if>
            update_time = sysdate()
        </set>
        where catalog_id = #{catalogId}
    </update>

    <delete id="deleteCatalogById" parameterType="Long">
        delete from dp_datasource_catalog where catalog_id = #{catalogId}
    </delete>

</mapper>
```

- [ ] **Step 7: Create MyBatis XML for DpDataSourceMapper**

File: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceMapper.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ruoyi.databroker.mapper.DpDataSourceMapper">

    <resultMap type="DpDataSource" id="DataSourceResult">
        <id     property="datasourceId"   column="datasource_id"   />
        <result property="catalogId"      column="catalog_id"      />
        <result property="sourceName"     column="source_name"     />
        <result property="sourceType"     column="source_type"     />
        <result property="host"           column="host"            />
        <result property="port"           column="port"            />
        <result property="databaseName"   column="database_name"   />
        <result property="username"       column="username"        />
        <result property="passwordCipher" column="password_cipher" />
        <result property="dbVersion"      column="db_version"      />
        <result property="usePool"        column="use_pool"        />
        <result property="useSsl"         column="use_ssl"         />
        <result property="caCert"         column="ca_cert"         />
        <result property="jdbcParams"     column="jdbc_params"     />
        <result property="status"         column="status"          />
        <result property="usageCount"     column="usage_count"     />
        <result property="lastSyncTime"   column="last_sync_time"   />
        <result property="lastSyncStatus" column="last_sync_status" />
        <result property="lastErrorMsg"   column="last_error_msg"   />
        <result property="delFlag"        column="del_flag"        />
        <result property="createBy"       column="create_by"       />
        <result property="createTime"     column="create_time"     />
        <result property="updateBy"       column="update_by"       />
        <result property="updateTime"     column="update_time"     />
        <result property="remark"         column="remark"          />
    </resultMap>

    <sql id="selectVo">
        select datasource_id, catalog_id, source_name, source_type, host, port, database_name,
               username, password_cipher, db_version, use_pool, use_ssl, ca_cert, jdbc_params,
               status, usage_count, last_sync_time, last_sync_status, last_error_msg, del_flag,
               create_by, create_time, update_by, update_time, remark
        from dp_datasource
    </sql>

    <select id="selectDataSourceList" parameterType="DpDataSource" resultMap="DataSourceResult">
        <include refid="selectVo"/>
        <where>
            <if test="sourceName != null and sourceName != ''">and source_name like concat('%', #{sourceName}, '%')</if>
            <if test="sourceType != null and sourceType != ''">and source_type = #{sourceType}</if>
            <if test="status != null and status != ''">and status = #{status}</if>
            <if test="catalogId != null">and catalog_id = #{catalogId}</if>
            and del_flag = '0'
        </where>
        order by create_time desc
    </select>

    <select id="selectDataSourceById" parameterType="Long" resultMap="DataSourceResult">
        <include refid="selectVo"/> where datasource_id = #{datasourceId} and del_flag = '0'
    </select>

    <select id="selectDataSourceByName" parameterType="String" resultMap="DataSourceResult">
        <include refid="selectVo"/> where source_name = #{sourceName} and del_flag = '0'
    </select>

    <insert id="insertDataSource" parameterType="DpDataSource" useGeneratedKeys="true" keyProperty="datasourceId">
        insert into dp_datasource (
            catalog_id, source_name, source_type, host, port, database_name, username,
            password_cipher, db_version, use_pool, use_ssl, ca_cert, jdbc_params, status,
            create_by, create_time, remark
        ) values (
            #{catalogId}, #{sourceName}, #{sourceType}, #{host}, #{port}, #{databaseName},
            #{username}, #{passwordCipher}, #{dbVersion}, #{usePool}, #{useSsl}, #{caCert},
            #{jdbcParams}, #{status}, #{createBy}, sysdate(), #{remark}
        )
    </insert>

    <update id="updateDataSource" parameterType="DpDataSource">
        update dp_datasource
        <set>
            <if test="catalogId != null">catalog_id = #{catalogId},</if>
            <if test="sourceName != null">source_name = #{sourceName},</if>
            <if test="sourceType != null">source_type = #{sourceType},</if>
            <if test="host != null">host = #{host},</if>
            <if test="port != null">port = #{port},</if>
            <if test="databaseName != null">database_name = #{databaseName},</if>
            <if test="username != null">username = #{username},</if>
            <if test="passwordCipher != null and passwordCipher != ''">password_cipher = #{passwordCipher},</if>
            <if test="dbVersion != null">db_version = #{dbVersion},</if>
            <if test="usePool != null">use_pool = #{usePool},</if>
            <if test="useSsl != null">use_ssl = #{useSsl},</if>
            <if test="caCert != null">ca_cert = #{caCert},</if>
            <if test="jdbcParams != null">jdbc_params = #{jdbcParams},</if>
            <if test="status != null">status = #{status},</if>
            <if test="lastSyncTime != null">last_sync_time = #{lastSyncTime},</if>
            <if test="lastSyncStatus != null">last_sync_status = #{lastSyncStatus},</if>
            <if test="lastErrorMsg != null">last_error_msg = #{lastErrorMsg},</if>
            <if test="updateBy != null">update_by = #{updateBy},</if>
            <if test="remark != null">remark = #{remark},</if>
            update_time = sysdate()
        </set>
        where datasource_id = #{datasourceId}
    </update>

    <update id="deleteDataSourceById" parameterType="Long">
        update dp_datasource set del_flag = '2', update_time = sysdate() where datasource_id = #{datasourceId}
    </update>

    <delete id="deleteDataSourceByIds" parameterType="Long">
        update dp_datasource set del_flag = '2', update_time = sysdate()
        where datasource_id in
        <foreach collection="array" item="id" open="(" separator="," close=")">
            #{id}
        </foreach>
    </delete>

    <update id="incrementUsageCount" parameterType="Long">
        update dp_datasource set usage_count = usage_count + 1 where datasource_id = #{datasourceId}
    </update>

</mapper>
```

- [ ] **Step 8: Create MyBatis XML for DpMetaTableMapper**

File: `ruoyi-databroker/src/main/resources/mapper/databroker/DpMetaTableMapper.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ruoyi.databroker.mapper.DpMetaTableMapper">

    <resultMap type="DpMetaTable" id="TableResult">
        <id     property="tableId"      column="table_id"      />
        <result property="datasourceId" column="datasource_id" />
        <result property="objectName"   column="object_name"   />
        <result property="objectType"   column="object_type"   />
        <result property="tableComment" column="table_comment" />
        <result property="cnName"       column="cn_name"       />
        <result property="rowCount"     column="row_count"     />
        <result property="columnCount"  column="column_count"  />
        <result property="usageCount"   column="usage_count"   />
        <result property="syncBatchNo"  column="sync_batch_no" />
        <result property="status"       column="status"        />
        <result property="createBy"     column="create_by"     />
        <result property="createTime"   column="create_time"   />
        <result property="updateBy"     column="update_by"     />
        <result property="updateTime"   column="update_time"   />
        <result property="remark"       column="remark"        />
    </resultMap>

    <sql id="selectVo">
        select table_id, datasource_id, object_name, object_type, table_comment, cn_name,
               row_count, column_count, usage_count, sync_batch_no, status,
               create_by, create_time, update_by, update_time, remark
        from dp_meta_table
    </sql>

    <select id="selectTableList" parameterType="DpMetaTable" resultMap="TableResult">
        <include refid="selectVo"/>
        <where>
            <if test="datasourceId != null">and datasource_id = #{datasourceId}</if>
            <if test="objectName != null and objectName != ''">and object_name like concat('%', #{objectName}, '%')</if>
            <if test="objectType != null and objectType != ''">and object_type = #{objectType}</if>
            <if test="status != null and status != ''">and status = #{status}</if>
        </where>
        order by object_type, object_name
    </select>

    <select id="selectTableById" parameterType="Long" resultMap="TableResult">
        <include refid="selectVo"/> where table_id = #{tableId}
    </select>

    <select id="selectTableByDsAndName" resultMap="TableResult">
        <include refid="selectVo"/> where datasource_id = #{param1} and object_name = #{param2}
    </select>

    <insert id="insertTable" parameterType="DpMetaTable" useGeneratedKeys="true" keyProperty="tableId">
        insert into dp_meta_table (
            datasource_id, object_name, object_type, table_comment, cn_name, row_count,
            column_count, usage_count, sync_batch_no, status, create_by, create_time
        ) values (
            #{datasourceId}, #{objectName}, #{objectType}, #{tableComment}, #{cnName}, #{rowCount},
            #{columnCount}, #{usageCount}, #{syncBatchNo}, #{status}, #{createBy}, sysdate()
        )
    </insert>

    <update id="updateTable" parameterType="DpMetaTable">
        update dp_meta_table
        <set>
            <if test="objectType != null">object_type = #{objectType},</if>
            <if test="tableComment != null">table_comment = #{tableComment},</if>
            <if test="rowCount != null">row_count = #{rowCount},</if>
            <if test="columnCount != null">column_count = #{columnCount},</if>
            <if test="syncBatchNo != null">sync_batch_no = #{syncBatchNo},</if>
            <if test="status != null">status = #{status},</if>
            update_time = sysdate()
        </set>
        where table_id = #{tableId}
    </update>

    <update id="updateTableCnName">
        update dp_meta_table set cn_name = #{param2}, update_time = sysdate() where table_id = #{param1}
    </update>

    <update id="markTableInvalid">
        update dp_meta_table set status = '1', update_time = sysdate()
        where datasource_id = #{param1} and sync_batch_no != #{param2} and sync_batch_no != ''
    </update>

</mapper>
```

- [ ] **Step 9: Create MyBatis XML for DpMetaColumnMapper**

File: `ruoyi-databroker/src/main/resources/mapper/databroker/DpMetaColumnMapper.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ruoyi.databroker.mapper.DpMetaColumnMapper">

    <resultMap type="DpMetaColumn" id="ColumnResult">
        <id     property="columnId"             column="column_id"              />
        <result property="tableId"              column="table_id"               />
        <result property="datasourceId"         column="datasource_id"          />
        <result property="objectName"           column="object_name"            />
        <result property="columnName"           column="column_name"            />
        <result property="ordinalPosition"      column="ordinal_position"       />
        <result property="columnType"           column="column_type"            />
        <result property="dataType"             column="data_type"              />
        <result property="isNullable"           column="is_nullable"            />
        <result property="columnDefault"        column="column_default"         />
        <result property="columnComment"        column="column_comment"         />
        <result property="isPk"                 column="is_pk"                  />
        <result property="isFk"                 column="is_fk"                  />
        <result property="referencedTableName"  column="referenced_table_name"  />
        <result property="referencedColumnName" column="referenced_column_name" />
        <result property="syncBatchNo"          column="sync_batch_no"          />
        <result property="createBy"             column="create_by"              />
        <result property="createTime"           column="create_time"            />
        <result property="updateBy"             column="update_by"              />
        <result property="updateTime"           column="update_time"            />
    </resultMap>

    <sql id="selectVo">
        select column_id, table_id, datasource_id, object_name, column_name, ordinal_position,
               column_type, data_type, is_nullable, column_default, column_comment,
               is_pk, is_fk, referenced_table_name, referenced_column_name, sync_batch_no,
               create_by, create_time, update_by, update_time
        from dp_meta_column
    </sql>

    <select id="selectColumnList" parameterType="DpMetaColumn" resultMap="ColumnResult">
        <include refid="selectVo"/>
        <where>
            <if test="tableId != null">and table_id = #{tableId}</if>
            <if test="datasourceId != null">and datasource_id = #{datasourceId}</if>
            <if test="objectName != null and objectName != ''">and object_name = #{objectName}</if>
        </where>
        order by ordinal_position
    </select>

    <select id="selectColumnsByTableId" parameterType="Long" resultMap="ColumnResult">
        <include refid="selectVo"/> where table_id = #{tableId} order by ordinal_position
    </select>

    <select id="selectColumnByTableAndName" resultMap="ColumnResult">
        <include refid="selectVo"/> where table_id = #{param1} and column_name = #{param2}
    </select>

    <insert id="insertColumn" parameterType="DpMetaColumn" useGeneratedKeys="true" keyProperty="columnId">
        insert into dp_meta_column (
            table_id, datasource_id, object_name, column_name, ordinal_position,
            column_type, data_type, is_nullable, column_default, column_comment,
            is_pk, is_fk, referenced_table_name, referenced_column_name, sync_batch_no,
            create_by, create_time
        ) values (
            #{tableId}, #{datasourceId}, #{objectName}, #{columnName}, #{ordinalPosition},
            #{columnType}, #{dataType}, #{isNullable}, #{columnDefault}, #{columnComment},
            #{isPk}, #{isFk}, #{referencedTableName}, #{referencedColumnName}, #{syncBatchNo},
            #{createBy}, sysdate()
        )
    </insert>

    <update id="updateColumn" parameterType="DpMetaColumn">
        update dp_meta_column
        <set>
            <if test="ordinalPosition != null">ordinal_position = #{ordinalPosition},</if>
            <if test="columnType != null">column_type = #{columnType},</if>
            <if test="dataType != null">data_type = #{dataType},</if>
            <if test="isNullable != null">is_nullable = #{isNullable},</if>
            <if test="columnDefault != null">column_default = #{columnDefault},</if>
            <if test="columnComment != null">column_comment = #{columnComment},</if>
            <if test="isPk != null">is_pk = #{isPk},</if>
            <if test="isFk != null">is_fk = #{isFk},</if>
            <if test="referencedTableName != null">referenced_table_name = #{referencedTableName},</if>
            <if test="referencedColumnName != null">referenced_column_name = #{referencedColumnName},</if>
            <if test="syncBatchNo != null">sync_batch_no = #{syncBatchNo},</if>
            update_time = sysdate()
        </set>
        where column_id = #{columnId}
    </update>

    <delete id="deleteColumnsByTableId" parameterType="Long">
        delete from dp_meta_column where table_id = #{tableId}
    </delete>

    <delete id="deleteOrphanColumns">
        delete from dp_meta_column
        where datasource_id = #{param1} and sync_batch_no != #{param2} and sync_batch_no != ''
    </delete>

</mapper>
```

- [ ] **Step 10: Create MyBatis XML for DpDataSourceLogMapper**

File: `ruoyi-databroker/src/main/resources/mapper/databroker/DpDataSourceLogMapper.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ruoyi.databroker.mapper.DpDataSourceLogMapper">

    <resultMap type="DpDataSourceLog" id="LogResult">
        <id     property="logId"        column="log_id"        />
        <result property="datasourceId" column="datasource_id" />
        <result property="logType"      column="log_type"      />
        <result property="operatorName" column="operator_name" />
        <result property="result"       column="result"        />
        <result property="message"      column="message"       />
        <result property="detailJson"   column="detail_json"   />
        <result property="operTime"     column="oper_time"     />
    </resultMap>

    <sql id="selectVo">
        select log_id, datasource_id, log_type, operator_name, result, message, detail_json, oper_time
        from dp_datasource_log
    </sql>

    <select id="selectLogList" parameterType="DpDataSourceLog" resultMap="LogResult">
        <include refid="selectVo"/>
        <where>
            <if test="datasourceId != null">and datasource_id = #{datasourceId}</if>
            <if test="logType != null and logType != ''">and log_type = #{logType}</if>
            <if test="result != null and result != ''">and result = #{result}</if>
        </where>
        order by oper_time desc
    </select>

    <insert id="insertLog" parameterType="DpDataSourceLog" useGeneratedKeys="true" keyProperty="logId">
        insert into dp_datasource_log (
            datasource_id, log_type, operator_name, result, message, detail_json, oper_time
        ) values (
            #{datasourceId}, #{logType}, #{operatorName}, #{result}, #{message}, #{detailJson}, sysdate()
        )
    </insert>

</mapper>
```

- [ ] **Step 11: Verify compilation**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 12: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/mapper/
git add ruoyi-databroker/src/main/resources/mapper/
git commit -m "feat: add databroker Mapper interfaces and XML"
```

---

### Task 6: Create crypto service and config properties

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/config/DataBrokerProperties.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/crypto/DataBrokerCryptoService.java`

**Interfaces:**
- Consumes: `application.yml` databroker config
- Produces: `DataBrokerCryptoService.encrypt(String)`, `DataBrokerCryptoService.decrypt(String)`, `DataBrokerCryptoService.maskSensitive(String json)`

- [ ] **Step 1: Create DataBrokerProperties.java**

```java
package com.ruoyi.databroker.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "databroker")
public class DataBrokerProperties {

    private Crypto crypto = new Crypto();
    private Jdbc jdbc = new Jdbc();

    public Crypto getCrypto() { return crypto; }
    public void setCrypto(Crypto crypto) { this.crypto = crypto; }
    public Jdbc getJdbc() { return jdbc; }
    public void setJdbc(Jdbc jdbc) { this.jdbc = jdbc; }

    public static class Crypto {
        private String secret;
        public String getSecret() { return secret; }
        public void setSecret(String secret) { this.secret = secret; }
    }

    public static class Jdbc {
        private int connectTimeout = 5000;
        private int socketTimeout = 10000;
        public int getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(int connectTimeout) { this.connectTimeout = connectTimeout; }
        public int getSocketTimeout() { return socketTimeout; }
        public void setSocketTimeout(int socketTimeout) { this.socketTimeout = socketTimeout; }
    }
}
```

- [ ] **Step 2: Create DataBrokerCryptoService.java**

```java
package com.ruoyi.databroker.crypto;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import javax.annotation.PostConstruct;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.databroker.config.DataBrokerProperties;

@Service
public class DataBrokerCryptoService {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int GCM_IV_LENGTH = 12;
    private static final int GCM_TAG_LENGTH = 128;

    @Autowired
    private DataBrokerProperties properties;

    private SecretKeySpec keySpec;

    @PostConstruct
    public void init() {
        String secret = properties.getCrypto().getSecret();
        // Ensure key is 16 bytes (128-bit) for AES
        byte[] keyBytes = new byte[16];
        byte[] secretBytes = secret.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(secretBytes, 0, keyBytes, 0, Math.min(secretBytes.length, 16));
        this.keySpec = new SecretKeySpec(keyBytes, ALGORITHM);
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isEmpty()) {
            return "";
        }
        try {
            byte[] iv = new byte[GCM_IV_LENGTH];
            SecureRandom random = new SecureRandom();
            random.nextBytes(iv);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, spec);

            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(cipherText, 0, combined, iv.length, cipherText.length);

            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new RuntimeException("Password encryption failed", e);
        }
    }

    public String decrypt(String cipherText) {
        if (cipherText == null || cipherText.isEmpty()) {
            return "";
        }
        try {
            byte[] combined = Base64.getDecoder().decode(cipherText);
            byte[] iv = new byte[GCM_IV_LENGTH];
            byte[] encrypted = new byte[combined.length - GCM_IV_LENGTH];
            System.arraycopy(combined, 0, iv, 0, GCM_IV_LENGTH);
            System.arraycopy(combined, GCM_IV_LENGTH, encrypted, 0, encrypted.length);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, spec);

            byte[] plainText = cipher.doFinal(encrypted);
            return new String(plainText, StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new RuntimeException("Password decryption failed", e);
        }
    }

    /**
     * Mask sensitive fields in JSON string for log storage.
     */
    public String maskSensitive(String json) {
        if (json == null || json.isEmpty()) {
            return json;
        }
        return json
            .replaceAll("\"password\"\\s*:\\s*\"[^\"]*\"", "\"password\":\"******\"")
            .replaceAll("\"passwordCipher\"\\s*:\\s*\"[^\"]*\"", "\"passwordCipher\":\"******\"")
            .replaceAll("\"caCert\"\\s*:\\s*\"[^\"]*\"", "\"caCert\":\"******\"")
            .replaceAll("\"secret\"\\s*:\\s*\"[^\"]*\"", "\"secret\":\"******\"")
            .replaceAll("\"token\"\\s*:\\s*\"[^\"]*\"", "\"token\":\"******\"")
            .replaceAll("\"key\"\\s*:\\s*\"[^\"]*\"", "\"key\":\"******\"");
    }
}
```

- [ ] **Step 3: Verify compilation**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/config/
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/crypto/
git commit -m "feat: add databroker crypto service and config properties"
```

---

### Task 7: Create metadata collection layer

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/JdbcConnectionFactory.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/MetadataTable.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/MetadataColumn.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/MetadataSyncResult.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/MySqlMetadataCollector.java`

**Interfaces:**
- Consumes: `DataBrokerCryptoService`, `DataBrokerProperties`
- Produces: `JdbcConnectionFactory.createConnection(host, port, db, user, password)` returns `java.sql.Connection`
- Produces: `MySqlMetadataCollector.collect(Connection, String dbName)` returns `MetadataSyncResult`

- [ ] **Step 1: Create JdbcConnectionFactory.java**

```java
package com.ruoyi.databroker.metadata;

import java.sql.Connection;
import java.sql.DriverManager;
import java.util.Properties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import com.ruoyi.databroker.config.DataBrokerProperties;

@Component
public class JdbcConnectionFactory {

    @Autowired
    private DataBrokerProperties properties;

    public Connection createConnection(String host, int port, String databaseName,
                                        String username, String password) throws Exception {
        String url = String.format("jdbc:mysql://%s:%d/%s?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai",
                host, port, databaseName);

        Properties props = new Properties();
        props.setProperty("user", username);
        props.setProperty("password", password);
        props.setProperty("connectTimeout", String.valueOf(properties.getJdbc().getConnectTimeout()));
        props.setProperty("socketTimeout", String.valueOf(properties.getJdbc().getSocketTimeout()));

        return DriverManager.getConnection(url, props);
    }
}
```

- [ ] **Step 2: Create MetadataTable.java**

```java
package com.ruoyi.databroker.metadata;

public class MetadataTable {
    private String tableName;
    private String tableType;   // BASE TABLE or VIEW
    private String tableComment;
    private Long tableRows;

    public String getTableName() { return tableName; }
    public void setTableName(String tableName) { this.tableName = tableName; }
    public String getTableType() { return tableType; }
    public void setTableType(String tableType) { this.tableType = tableType; }
    public String getTableComment() { return tableComment; }
    public void setTableComment(String tableComment) { this.tableComment = tableComment; }
    public Long getTableRows() { return tableRows; }
    public void setTableRows(Long tableRows) { this.tableRows = tableRows; }
}
```

- [ ] **Step 3: Create MetadataColumn.java**

```java
package com.ruoyi.databroker.metadata;

public class MetadataColumn {
    private String tableName;
    private String columnName;
    private int ordinalPosition;
    private String columnType;
    private String dataType;
    private String isNullable;   // YES or NO
    private String columnDefault;
    private String columnComment;
    private String columnKey;    // PRI, UNI, MUL, or empty

    public String getTableName() { return tableName; }
    public void setTableName(String tableName) { this.tableName = tableName; }
    public String getColumnName() { return columnName; }
    public void setColumnName(String columnName) { this.columnName = columnName; }
    public int getOrdinalPosition() { return ordinalPosition; }
    public void setOrdinalPosition(int ordinalPosition) { this.ordinalPosition = ordinalPosition; }
    public String getColumnType() { return columnType; }
    public void setColumnType(String columnType) { this.columnType = columnType; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getIsNullable() { return isNullable; }
    public void setIsNullable(String isNullable) { this.isNullable = isNullable; }
    public String getColumnDefault() { return columnDefault; }
    public void setColumnDefault(String columnDefault) { this.columnDefault = columnDefault; }
    public String getColumnComment() { return columnComment; }
    public void setColumnComment(String columnComment) { this.columnComment = columnComment; }
    public String getColumnKey() { return columnKey; }
    public void setColumnKey(String columnKey) { this.columnKey = columnKey; }
}
```

- [ ] **Step 4: Create MetadataSyncResult.java**

```java
package com.ruoyi.databroker.metadata;

import java.util.ArrayList;
import java.util.List;

public class MetadataSyncResult {
    private int tableCount;
    private int viewCount;
    private int columnCount;
    private List<MetadataTable> tables = new ArrayList<>();
    private List<MetadataColumn> columns = new ArrayList<>();

    public int getTableCount() { return tableCount; }
    public void setTableCount(int tableCount) { this.tableCount = tableCount; }
    public int getViewCount() { return viewCount; }
    public void setViewCount(int viewCount) { this.viewCount = viewCount; }
    public int getColumnCount() { return columnCount; }
    public void setColumnCount(int columnCount) { this.columnCount = columnCount; }
    public List<MetadataTable> getTables() { return tables; }
    public void setTables(List<MetadataTable> tables) { this.tables = tables; }
    public List<MetadataColumn> getColumns() { return columns; }
    public void setColumns(List<MetadataColumn> columns) { this.columns = columns; }
}
```

- [ ] **Step 5: Create MySqlMetadataCollector.java**

```java
package com.ruoyi.databroker.metadata;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class MySqlMetadataCollector {

    private static final String SQL_TABLES =
        "select table_name, table_type, table_comment, table_rows " +
        "from information_schema.tables " +
        "where table_schema = ? and table_type in ('BASE TABLE', 'VIEW') " +
        "order by table_name";

    private static final String SQL_COLUMNS =
        "select table_name, column_name, ordinal_position, column_type, data_type, " +
        "is_nullable, column_default, column_comment, column_key " +
        "from information_schema.columns " +
        "where table_schema = ? order by table_name, ordinal_position";

    private static final String SQL_FK =
        "select table_name, column_name, referenced_table_name, referenced_column_name " +
        "from information_schema.KEY_COLUMN_USAGE " +
        "where table_schema = ? and referenced_table_name is not null";

    private static final String SQL_VERSION = "select version()";

    public String fetchVersion(Connection conn) throws Exception {
        try (Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(SQL_VERSION)) {
            if (rs.next()) {
                return rs.getString(1);
            }
            return "";
        }
    }

    public MetadataSyncResult collect(Connection conn, String databaseName) throws Exception {
        MetadataSyncResult result = new MetadataSyncResult();

        // Collect tables
        List<MetadataTable> tables = new ArrayList<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_TABLES)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    MetadataTable t = new MetadataTable();
                    t.setTableName(rs.getString("table_name"));
                    t.setTableType(rs.getString("table_type"));
                    t.setTableComment(rs.getString("table_comment"));
                    t.setTableRows(rs.getLong("table_rows"));
                    tables.add(t);
                    if ("BASE TABLE".equals(t.getTableType())) {
                        result.setTableCount(result.getTableCount() + 1);
                    } else {
                        result.setViewCount(result.getViewCount() + 1);
                    }
                }
            }
        }

        // Collect columns
        List<MetadataColumn> columns = new ArrayList<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_COLUMNS)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    MetadataColumn c = new MetadataColumn();
                    c.setTableName(rs.getString("table_name"));
                    c.setColumnName(rs.getString("column_name"));
                    c.setOrdinalPosition(rs.getInt("ordinal_position"));
                    c.setColumnType(rs.getString("column_type"));
                    c.setDataType(rs.getString("data_type"));
                    c.setIsNullable(rs.getString("is_nullable"));
                    c.setColumnDefault(rs.getString("column_default"));
                    c.setColumnComment(rs.getString("column_comment"));
                    c.setColumnKey(rs.getString("column_key"));
                    columns.add(c);
                    result.setColumnCount(result.getColumnCount() + 1);
                }
            }
        }

        // Collect foreign keys
        Map<String, Map<String, String[]>> fkMap = new HashMap<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_FK)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    String tableName = rs.getString("table_name");
                    String columnName = rs.getString("column_name");
                    String refTable = rs.getString("referenced_table_name");
                    String refColumn = rs.getString("referenced_column_name");
                    fkMap.computeIfAbsent(tableName, k -> new HashMap<>())
                          .put(columnName, new String[]{refTable, refColumn});
                }
            }
        }

        // Set FK info on columns
        for (MetadataColumn col : columns) {
            Map<String, String[]> tableFks = fkMap.get(col.getTableName());
            if (tableFks != null && tableFks.containsKey(col.getColumnName())) {
                col.setColumnKey("FK");
            }
        }

        result.setTables(tables);
        result.setColumns(columns);
        return result;
    }
}
```

- [ ] **Step 6: Verify compilation**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/metadata/
git commit -m "feat: add databroker metadata collection layer"
```

---

### Task 8: Create service layer — catalog and datasource CRUD

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/service/IDpDataSourceCatalogService.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/service/IDpDataSourceService.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/service/impl/DpDataSourceCatalogServiceImpl.java`
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/service/impl/DpDataSourceServiceImpl.java`

**Interfaces:**
- Consumes: Task 4 domains, Task 5 mappers, Task 6 crypto, Task 7 metadata
- Produces: `IDpDataSourceService` with methods: `tree()`, `getById()`, `insert()`, `update()`, `deleteByIds()`, `testConnection()`, `syncMetadata()`, `listTables()`, `listColumns()`, `updateCnName()`, `listLogs()`

- [ ] **Step 1: Create IDpDataSourceCatalogService.java**

```java
package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface IDpDataSourceCatalogService {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);
}
```

- [ ] **Step 2: Create DpDataSourceCatalogServiceImpl.java**

```java
package com.ruoyi.databroker.service.impl;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper;
import com.ruoyi.databroker.service.IDpDataSourceCatalogService;

@Service
public class DpDataSourceCatalogServiceImpl implements IDpDataSourceCatalogService {

    @Autowired
    private DpDataSourceCatalogMapper catalogMapper;

    @Override
    public List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog) {
        return catalogMapper.selectCatalogList(catalog);
    }

    @Override
    public DpDataSourceCatalog selectCatalogById(Long catalogId) {
        return catalogMapper.selectCatalogById(catalogId);
    }

    @Override
    public int insertCatalog(DpDataSourceCatalog catalog) {
        return catalogMapper.insertCatalog(catalog);
    }

    @Override
    public int updateCatalog(DpDataSourceCatalog catalog) {
        return catalogMapper.updateCatalog(catalog);
    }

    @Override
    public int deleteCatalogById(Long catalogId) {
        return catalogMapper.deleteCatalogById(catalogId);
    }
}
```

- [ ] **Step 3: Create IDpDataSourceService.java**

```java
package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.SyncResultVO;
import com.ruoyi.databroker.domain.vo.TestResultVO;

public interface IDpDataSourceService {
    // Tree
    List<TreeNode> buildTree();

    // CRUD
    DpDataSource selectDataSourceById(Long id);
    int insertDataSource(DpDataSource dataSource);
    int updateDataSource(DpDataSource dataSource);
    int deleteDataSourceByIds(Long[] ids);

    // Test connection
    TestResultVO testConnection(DpDataSource dataSource);

    // Sync metadata
    SyncResultVO syncMetadata(Long id);

    // Tables & Columns
    List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query);
    List<DpMetaColumn> listColumns(Long tableId);

    // CN Name
    int updateTableCnName(Long tableId, String cnName);

    // Logs
    List<DpDataSourceLog> listLogs(Long datasourceId, DpDataSourceLog query);
}
```

- [ ] **Step 4: Create DpDataSourceServiceImpl.java**

```java
package com.ruoyi.databroker.service.impl;

import java.sql.Connection;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.alibaba.fastjson2.JSON;
import com.ruoyi.common.core.text.Convert;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.SyncResultVO;
import com.ruoyi.databroker.domain.vo.TestResultVO;
import com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper;
import com.ruoyi.databroker.mapper.DpDataSourceLogMapper;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.mapper.DpMetaColumnMapper;
import com.ruoyi.databroker.mapper.DpMetaTableMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.metadata.MetadataColumn;
import com.ruoyi.databroker.metadata.MetadataSyncResult;
import com.ruoyi.databroker.metadata.MetadataTable;
import com.ruoyi.databroker.metadata.MySqlMetadataCollector;
import com.ruoyi.databroker.service.IDpDataSourceService;

@Service
public class DpDataSourceServiceImpl implements IDpDataSourceService {

    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DpDataSourceCatalogMapper catalogMapper;
    @Autowired
    private DpMetaTableMapper tableMapper;
    @Autowired
    private DpMetaColumnMapper columnMapper;
    @Autowired
    private DpDataSourceLogMapper logMapper;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private MySqlMetadataCollector metadataCollector;

    @Override
    public List<TreeNode> buildTree() {
        List<TreeNode> tree = new ArrayList<>();

        // Load catalogs
        List<DpDataSourceCatalog> catalogs = catalogMapper.selectCatalogList(new DpDataSourceCatalog());
        for (DpDataSourceCatalog cat : catalogs) {
            TreeNode node = new TreeNode();
            node.setId("cat_" + cat.getCatalogId());
            node.setParentId(cat.getParentId() != null ? String.valueOf(cat.getParentId()) : "0");
            node.setLabel(cat.getCatalogName());
            node.setNodeType("catalog");
            node.setCatalogId(cat.getCatalogId());
            node.setStatus(cat.getStatus());
            node.setChildren(new ArrayList<>());
            tree.add(node);
        }

        // Load datasources and attach to catalogs
        List<DpDataSource> sources = dataSourceMapper.selectDataSourceList(new DpDataSource());
        for (DpDataSource ds : sources) {
            TreeNode node = new TreeNode();
            node.setId("ds_" + ds.getDatasourceId());
            node.setParentId("cat_" + ds.getCatalogId());
            node.setLabel(ds.getSourceName());
            node.setNodeType("datasource");
            node.setDatasourceId(ds.getDatasourceId());
            node.setCatalogId(ds.getCatalogId());
            node.setSourceType(ds.getSourceType());
            node.setStatus(ds.getStatus());
            node.setChildren(new ArrayList<>());

            // Attach to parent catalog
            for (TreeNode catNode : tree) {
                if (("cat_" + ds.getCatalogId()).equals(catNode.getId())) {
                    catNode.getChildren().add(node);
                    break;
                }
            }
        }

        return tree;
    }

    @Override
    public DpDataSource selectDataSourceById(Long id) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
        if (ds != null) {
            ds.setPassword("******");
            ds.setPasswordCipher(null);
        }
        return ds;
    }

    @Override
    @Transactional
    public int insertDataSource(DpDataSource dataSource) {
        // Encrypt password
        if (dataSource.getPassword() != null && !dataSource.getPassword().isEmpty()
                && !"******".equals(dataSource.getPassword())) {
            dataSource.setPasswordCipher(cryptoService.encrypt(dataSource.getPassword()));
        }
        dataSource.setCreateBy(SecurityUtils.getUsername());
        int rows = dataSourceMapper.insertDataSource(dataSource);

        // Write log
        writeLog(dataSource.getDatasourceId(), "INSERT", "1",
                "新增数据源：" + dataSource.getSourceName(),
                maskDetail(dataSource));
        return rows;
    }

    @Override
    @Transactional
    public int updateDataSource(DpDataSource dataSource) {
        DpDataSource old = dataSourceMapper.selectDataSourceById(dataSource.getDatasourceId());

        // Handle password: empty or ****** means keep old
        if (dataSource.getPassword() != null && !dataSource.getPassword().isEmpty()
                && !"******".equals(dataSource.getPassword())) {
            dataSource.setPasswordCipher(cryptoService.encrypt(dataSource.getPassword()));
        } else {
            dataSource.setPasswordCipher(null); // don't update
        }

        dataSource.setUpdateBy(SecurityUtils.getUsername());
        int rows = dataSourceMapper.updateDataSource(dataSource);

        writeLog(dataSource.getDatasourceId(), "UPDATE", "1",
                "修改数据源：" + dataSource.getSourceName(),
                maskDetail(dataSource));
        return rows;
    }

    @Override
    @Transactional
    public int deleteDataSourceByIds(Long[] ids) {
        int rows = 0;
        for (Long id : ids) {
            DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
            if (ds != null) {
                rows += dataSourceMapper.deleteDataSourceById(id);
                writeLog(id, "DELETE", "1", "删除数据源：" + ds.getSourceName(), null);
            }
        }
        return rows;
    }

    @Override
    public TestResultVO testConnection(DpDataSource dataSource) {
        TestResultVO result = new TestResultVO();
        String password = resolvePassword(dataSource);

        try (Connection conn = connectionFactory.createConnection(
                dataSource.getHost(), dataSource.getPort(),
                dataSource.getDatabaseName(), dataSource.getUsername(), password)) {

            String version = metadataCollector.fetchVersion(conn);
            result.setDbVersion(version);
            result.setDatabaseName(dataSource.getDatabaseName());

        } catch (Exception e) {
            throw new RuntimeException("连接失败：" + e.getMessage(), e);
        }
        return result;
    }

    @Override
    @Transactional
    public SyncResultVO syncMetadata(Long id) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
        if (ds == null) {
            throw new RuntimeException("数据源不存在");
        }

        String password = cryptoService.decrypt(ds.getPasswordCipher());
        String batchNo = "SYNC" + new SimpleDateFormat("yyyyMMddHHmmssSSS").format(new Date());

        SyncResultVO result = new SyncResultVO();
        result.setSyncBatchNo(batchNo);

        try (Connection conn = connectionFactory.createConnection(
                ds.getHost(), ds.getPort(), ds.getDatabaseName(), ds.getUsername(), password)) {

            // Fetch version
            String version = metadataCollector.fetchVersion(conn);
            ds.setDbVersion(version);
            ds.setLastSyncTime(new Date());
            ds.setLastSyncStatus("1");

            // Collect metadata
            MetadataSyncResult meta = metadataCollector.collect(conn, ds.getDatabaseName());
            result.setTableCount(meta.getTableCount());
            result.setViewCount(meta.getViewCount());
            result.setColumnCount(meta.getColumnCount());

            String username = SecurityUtils.getUsername();

            // Sync tables
            for (MetadataTable mt : meta.getTables()) {
                DpMetaTable existing = tableMapper.selectTableByDsAndName(id, mt.getTableName());
                String objectType = "BASE TABLE".equals(mt.getTableType()) ? "TABLE" : "VIEW";

                if (existing != null) {
                    existing.setObjectType(objectType);
                    existing.setTableComment(mt.getTableComment());
                    existing.setRowCount(mt.getTableRows());
                    existing.setSyncBatchNo(batchNo);
                    existing.setStatus("0");
                    tableMapper.updateTable(existing);
                } else {
                    DpMetaTable newTable = new DpMetaTable();
                    newTable.setDatasourceId(id);
                    newTable.setObjectName(mt.getTableName());
                    newTable.setObjectType(objectType);
                    newTable.setTableComment(mt.getTableComment());
                    newTable.setCnName(mt.getTableComment()); // init cn_name from comment
                    newTable.setRowCount(mt.getTableRows());
                    newTable.setSyncBatchNo(batchNo);
                    newTable.setStatus("0");
                    newTable.setCreateBy(username);
                    tableMapper.insertTable(newTable);
                }
            }

            // Mark tables not in this batch as invalid
            tableMapper.markTableInvalid(id, batchNo);

            // Sync columns — delete orphan columns first (doc §12.3 rule)
            columnMapper.deleteOrphanColumns(id, batchNo);

            for (MetadataColumn mc : meta.getColumns()) {
                DpMetaTable tbl = tableMapper.selectTableByDsAndName(id, mc.getTableName());
                if (tbl == null) continue;

                DpMetaColumn existing = columnMapper.selectColumnByTableAndName(tbl.getTableId(), mc.getColumnName());

                String isNullable = "NO".equals(mc.getIsNullable()) ? "0" : "1";
                String isPk = "PRI".equals(mc.getColumnKey()) ? "1" : "0";
                String isFk = "FK".equals(mc.getColumnKey()) ? "1" : "0";

                if (existing != null) {
                    existing.setOrdinalPosition(mc.getOrdinalPosition());
                    existing.setColumnType(mc.getColumnType());
                    existing.setDataType(mc.getDataType());
                    existing.setIsNullable(isNullable);
                    existing.setColumnDefault(mc.getColumnDefault());
                    existing.setColumnComment(mc.getColumnComment());
                    existing.setIsPk(isPk);
                    existing.setIsFk(isFk);
                    existing.setSyncBatchNo(batchNo);
                    columnMapper.updateColumn(existing);
                } else {
                    DpMetaColumn newCol = new DpMetaColumn();
                    newCol.setTableId(tbl.getTableId());
                    newCol.setDatasourceId(id);
                    newCol.setObjectName(mc.getTableName());
                    newCol.setColumnName(mc.getColumnName());
                    newCol.setOrdinalPosition(mc.getOrdinalPosition());
                    newCol.setColumnType(mc.getColumnType());
                    newCol.setDataType(mc.getDataType());
                    newCol.setIsNullable(isNullable);
                    newCol.setColumnDefault(mc.getColumnDefault());
                    newCol.setColumnComment(mc.getColumnComment());
                    newCol.setIsPk(isPk);
                    newCol.setIsFk(isFk);
                    newCol.setSyncBatchNo(batchNo);
                    newCol.setCreateBy(username);
                    columnMapper.insertColumn(newCol);
                }
            }

            // Update datasource sync status
            ds.setLastSyncTime(new Date());
            ds.setLastSyncStatus("1");
            ds.setLastErrorMsg("");
            dataSourceMapper.updateDataSource(ds);

            writeLog(id, "SYNC", "1",
                    "同步成功：表" + meta.getTableCount() + "个，视图" + meta.getViewCount() + "个，字段" + meta.getColumnCount() + "个",
                    "{\"batchNo\":\"" + batchNo + "\"}");

        } catch (Exception e) {
            ds.setLastSyncStatus("2");
            ds.setLastErrorMsg(e.getMessage());
            dataSourceMapper.updateDataSource(ds);

            writeLog(id, "SYNC", "0", "同步失败：" + e.getMessage(), null);
            throw new RuntimeException("同步失败：" + e.getMessage(), e);
        }

        return result;
    }

    @Override
    public List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query) {
        query.setDatasourceId(datasourceId);
        return tableMapper.selectTableList(query);
    }

    @Override
    public List<DpMetaColumn> listColumns(Long tableId) {
        return columnMapper.selectColumnsByTableId(tableId);
    }

    @Override
    @Transactional
    public int updateTableCnName(Long tableId, String cnName) {
        DpMetaTable table = tableMapper.selectTableById(tableId);
        if (table == null) {
            throw new RuntimeException("表信息不存在");
        }
        int rows = tableMapper.updateTableCnName(tableId, cnName);
        writeLog(table.getDatasourceId(), "CN_NAME", "1",
                "修改中文名：" + table.getObjectName() + " -> " + cnName, null);
        return rows;
    }

    @Override
    public List<DpDataSourceLog> listLogs(Long datasourceId, DpDataSourceLog query) {
        query.setDatasourceId(datasourceId);
        List<DpDataSourceLog> logs = logMapper.selectLogList(query);
        // Mask sensitive data in detail_json
        for (DpDataSourceLog log : logs) {
            if (log.getDetailJson() != null) {
                log.setDetailJson(cryptoService.maskSensitive(log.getDetailJson()));
            }
        }
        return logs;
    }

    // ---- private helpers ----

    private String resolvePassword(DpDataSource ds) {
        // If no ID, it's a test from form (password in plain text)
        if (ds.getDatasourceId() == null) {
            return ds.getPassword();
        }
        // If saved, decrypt from DB
        DpDataSource existing = dataSourceMapper.selectDataSourceById(ds.getDatasourceId());
        if (existing != null && existing.getPasswordCipher() != null
                && !existing.getPasswordCipher().isEmpty()) {
            return cryptoService.decrypt(existing.getPasswordCipher());
        }
        return ds.getPassword();
    }

    private void writeLog(Long datasourceId, String logType, String result,
                          String message, String detailJson) {
        DpDataSourceLog log = new DpDataSourceLog();
        log.setDatasourceId(datasourceId);
        log.setLogType(logType);
        log.setOperatorName(SecurityUtils.getUsername());
        log.setResult(result);
        log.setMessage(message);
        log.setDetailJson(detailJson);
        logMapper.insertLog(log);
    }

    private String maskDetail(DpDataSource ds) {
        if (ds == null) return null;
        DpDataSource copy = new DpDataSource();
        copy.setSourceName(ds.getSourceName());
        copy.setSourceType(ds.getSourceType());
        copy.setHost(ds.getHost());
        copy.setPort(ds.getPort());
        copy.setDatabaseName(ds.getDatabaseName());
        copy.setPassword("******");
        copy.setPasswordCipher("******");
        return JSON.toJSONString(copy);
    }
}
```

- [ ] **Step 5: Verify compilation**

Run: `mvn clean compile -pl ruoyi-databroker -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/service/
git commit -m "feat: add databroker service layer"
```

---

### Task 9: Create controllers

**Files:**
- Create: `ruoyi-databroker/src/main/java/com/ruoyi/databroker/controller/DpDataSourceController.java`

**Interfaces:**
- Consumes: `IDpDataSourceService`
- Produces: REST endpoints under `/databroker/datasource/**` with `@PreAuthorize` guards

- [ ] **Step 1: Create DpDataSourceController.java**

```java
package com.ruoyi.databroker.controller;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.service.IDpDataSourceService;

@RestController
@RequestMapping("/databroker/datasource")
public class DpDataSourceController extends BaseController {

    @Autowired
    private IDpDataSourceService dataSourceService;

    /** 目录 + 数据源树 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:list')")
    @GetMapping("/tree")
    public AjaxResult tree() {
        return success(dataSourceService.buildTree());
    }

    /** 查询数据源详情 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/{id}")
    public AjaxResult getInfo(@PathVariable Long id) {
        return success(dataSourceService.selectDataSourceById(id));
    }

    /** 新增数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDataSource dataSource) {
        return toAjax(dataSourceService.insertDataSource(dataSource));
    }

    /** 修改数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDataSource dataSource) {
        return toAjax(dataSourceService.updateDataSource(dataSource));
    }

    /** 删除数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:remove')")
    @DeleteMapping("/{ids}")
    public AjaxResult remove(@PathVariable Long[] ids) {
        dataSourceService.deleteDataSourceByIds(ids);
        return success();
    }

    /** 测试连接 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:test')")
    @PostMapping("/test")
    public AjaxResult test(@RequestBody DpDataSource dataSource) {
        try {
            return success(dataSourceService.testConnection(dataSource));
        } catch (Exception e) {
            return error(e.getMessage());
        }
    }

    /** 同步元数据 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:sync')")
    @PostMapping("/{id}/sync")
    public AjaxResult sync(@PathVariable Long id) {
        try {
            return success(dataSourceService.syncMetadata(id));
        } catch (Exception e) {
            return error(e.getMessage());
        }
    }

    /** 表信息列表 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:list')")
    @GetMapping("/{id}/tables")
    public TableDataInfo tables(@PathVariable Long id, DpMetaTable query) {
        startPage();
        List<DpMetaTable> list = dataSourceService.listTables(id, query);
        return getDataTable(list);
    }

    /** 字段信息 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/table/{tableId}/columns")
    public AjaxResult columns(@PathVariable Long tableId) {
        return success(dataSourceService.listColumns(tableId));
    }

    /** 修改中文名 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:edit')")
    @PutMapping("/table/{tableId}/cnName")
    public AjaxResult updateCnName(@PathVariable Long tableId, @RequestBody DpMetaTable table) {
        return toAjax(dataSourceService.updateTableCnName(tableId, table.getCnName()));
    }

    /** 操作记录 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/{id}/logs")
    public TableDataInfo logs(@PathVariable Long id, DpDataSourceLog query) {
        startPage();
        List<DpDataSourceLog> list = dataSourceService.listLogs(id, query);
        return getDataTable(list);
    }
}
```

- [ ] **Step 2: Verify full build**

Run: `mvn clean compile -pl ruoyi-admin -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add ruoyi-databroker/src/main/java/com/ruoyi/databroker/controller/
git commit -m "feat: add databroker REST controllers"
```

---

### Task 10: Create frontend API module

**Files:**
- Create: `ruoyi-ui/src/api/databroker/datasource.js`

**Interfaces:**
- Produces: JavaScript API functions matching all backend endpoints

- [ ] **Step 1: Create datasource.js API module**

```javascript
import request from '@/utils/request'

// 目录 + 数据源树
export function treeDataSource() {
  return request({
    url: '/databroker/datasource/tree',
    method: 'get'
  })
}

// 查询数据源详情
export function getDataSource(id) {
  return request({
    url: '/databroker/datasource/' + id,
    method: 'get'
  })
}

// 新增数据源
export function addDataSource(data) {
  return request({
    url: '/databroker/datasource',
    method: 'post',
    data: data
  })
}

// 修改数据源
export function updateDataSource(data) {
  return request({
    url: '/databroker/datasource',
    method: 'put',
    data: data
  })
}

// 删除数据源
export function delDataSource(ids) {
  return request({
    url: '/databroker/datasource/' + ids,
    method: 'delete'
  })
}

// 测试连接
export function testDataSource(data) {
  return request({
    url: '/databroker/datasource/test',
    method: 'post',
    data: data
  })
}

// 同步元数据
export function syncDataSource(id) {
  return request({
    url: '/databroker/datasource/' + id + '/sync',
    method: 'post'
  })
}

// 表信息列表
export function listTables(id, query) {
  return request({
    url: '/databroker/datasource/' + id + '/tables',
    method: 'get',
    params: query
  })
}

// 字段信息
export function listColumns(tableId) {
  return request({
    url: '/databroker/datasource/table/' + tableId + '/columns',
    method: 'get'
  })
}

// 修改中文名
export function updateTableCnName(tableId, data) {
  return request({
    url: '/databroker/datasource/table/' + tableId + '/cnName',
    method: 'put',
    data: data
  })
}

// 操作记录
export function listLogs(id, query) {
  return request({
    url: '/databroker/datasource/' + id + '/logs',
    method: 'get',
    params: query
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add ruoyi-ui/src/api/databroker/datasource.js
git commit -m "feat: add databroker frontend API module"
```

---

### Task 11: Create frontend datasource management page

**Files:**
- Create: `ruoyi-ui/src/views/databroker/datasource/index.vue`

**Interfaces:**
- Consumes: `@/api/databroker/datasource` module
- Produces: Full page with left tree panel + right detail area (3 tabs)

- [ ] **Step 1: Create index.vue — Template section**

```vue
<template>
  <div class="app-container">
    <el-row :gutter="16">
      <!-- Left: Tree Panel -->
      <el-col :span="6">
        <div class="tree-panel">
          <div class="tree-header">
            <span><i class="el-icon-connection" /> 数据连接</span>
            <el-button type="primary" size="mini" icon="el-icon-plus" @click="handleAdd"
              v-hasPermi="['databroker:datasource:add']">新增</el-button>
          </div>
          <el-input v-model="filterText" placeholder="输入名称过滤" size="small" clearable style="margin: 8px 0;" />
          <el-tree :data="treeData" :props="treeProps" node-key="id" :filter-node-method="filterNode"
            :expand-on-click-node="false" highlight-current ref="tree" @node-click="handleNodeClick">
            <span class="custom-tree-node" slot-scope="{ node, data }">
              <i :class="data.nodeType === 'catalog' ? 'el-icon-folder' : 'el-icon-coin'" />
              <span>{{ node.label }}</span>
            </span>
          </el-tree>
        </div>
      </el-col>

      <!-- Right: Detail Area -->
      <el-col :span="18">
        <div v-if="!selectedNode || selectedNode.nodeType === 'catalog'" class="empty-state">
          <i class="el-icon-info" style="font-size:48px;color:#c0c4cc;" />
          <p>请从左侧选择一个数据源查看详情</p>
        </div>

        <div v-else>
          <!-- Info Bar -->
          <div class="info-bar">
            <span class="info-bar-icon"><i class="el-icon-coin" /></span>
            <span class="info-bar-title">{{ datasource.sourceName }}</span>
            <el-button size="mini" type="primary" icon="el-icon-edit" @click="handleEdit"
              v-hasPermi="['databroker:datasource:edit']" style="margin-left:12px;">编辑</el-button>
            <el-tag v-if="datasource.sourceType" style="margin-left:8px;">{{ datasource.sourceType }}</el-tag>
            <span style="margin-left:16px;color:#909399;font-size:12px;">
              创建人：{{ datasource.createBy }} | 创建时间：{{ datasource.createTime }} | 使用量：{{ datasource.usageCount || 0 }}
            </span>
          </div>

          <!-- Tabs -->
          <el-tabs v-model="activeTab" style="margin-top:12px;">
            <!-- Basic Info Tab -->
            <el-tab-pane label="基本信息" name="basic">
              <el-form :model="datasource" label-width="120px" size="small" disabled>
                <el-row :gutter="20">
                  <el-col :span="12">
                    <el-form-item label="数据连接名称">{{ datasource.sourceName }}</el-form-item>
                    <el-form-item label="主机">{{ datasource.host }}</el-form-item>
                    <el-form-item label="端口">{{ datasource.port }}</el-form-item>
                    <el-form-item label="数据库名称">{{ datasource.databaseName }}</el-form-item>
                    <el-form-item label="用户名">{{ datasource.username }}</el-form-item>
                    <el-form-item label="密码">******</el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="数据库版本">{{ datasource.dbVersion || '-' }}</el-form-item>
                    <el-form-item label="连接池">{{ datasource.usePool === '1' ? '是' : '否' }}</el-form-item>
                    <el-form-item label="SSL">{{ datasource.useSsl === '1' ? '是' : '否' }}</el-form-item>
                    <el-form-item label="最近同步">
                      {{ datasource.lastSyncTime || '-' }}
                      <el-tag v-if="datasource.lastSyncStatus === '1'" type="success" size="mini">成功</el-tag>
                      <el-tag v-else-if="datasource.lastSyncStatus === '2'" type="danger" size="mini">失败</el-tag>
                      <el-tag v-else type="info" size="mini">未同步</el-tag>
                    </el-form-item>
                    <el-form-item label="备注">{{ datasource.remark || '-' }}</el-form-item>
                  </el-col>
                </el-row>
              </el-form>
              <div style="text-align:right;padding-right:20px;">
                <el-button size="small" type="primary" icon="el-icon-link" @click="handleTestFromDetail"
                  v-hasPermi="['databroker:datasource:test']">测试连接</el-button>
                <el-button size="small" type="success" icon="el-icon-refresh" @click="handleSync"
                  v-hasPermi="['databroker:datasource:sync']">同步元数据</el-button>
              </div>
            </el-tab-pane>

            <!-- Tables Tab -->
            <el-tab-pane label="表信息" name="tables">
              <div class="table-stats">
                <el-tag type="primary">表：{{ tableStats.tableCount }}</el-tag>
                <el-tag type="success" style="margin-left:8px;">视图：{{ tableStats.viewCount }}</el-tag>
              </div>
              <el-form :model="tableQuery" :inline="true" size="small" style="margin-top:10px;">
                <el-form-item label="名称"><el-input v-model="tableQuery.objectName" placeholder="表/视图名称" clearable style="width:180px;" /></el-form-item>
                <el-form-item label="类型">
                  <el-select v-model="tableQuery.objectType" placeholder="全部" clearable style="width:120px;">
                    <el-option label="表" value="TABLE" /><el-option label="视图" value="VIEW" />
                  </el-select>
                </el-form-item>
                <el-form-item><el-button type="primary" icon="el-icon-search" @click="loadTables">查询</el-button></el-form-item>
              </el-form>
              <el-table :data="tableList" v-loading="tableLoading" size="small">
                <el-table-column prop="objectName" label="表/视图名称" min-width="180" />
                <el-table-column prop="objectType" label="类型" width="80">
                  <template slot-scope="scope">{{ scope.row.objectType === 'TABLE' ? '表' : '视图' }}</template>
                </el-table-column>
                <el-table-column prop="cnName" label="中文名" min-width="140">
                  <template slot-scope="scope">
                    <el-input v-model="scope.row.cnName" size="mini" placeholder="输入中文名" maxlength="60"
                      @blur="saveCnName(scope.row)" @keyup.enter.native="saveCnName(scope.row)" />
                  </template>
                </el-table-column>
                <el-table-column prop="columnCount" label="字段数" width="80" />
                <el-table-column prop="usageCount" label="使用量" width="80" />
                <el-table-column label="操作" width="100">
                  <template slot-scope="scope">
                    <el-button type="text" size="mini" @click="showColumns(scope.row)">字段信息</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <pagination v-show="tableTotal > 0" :total="tableTotal" :page.sync="tableQuery.pageNum" :limit.sync="tableQuery.pageSize" @pagination="loadTables" />
            </el-tab-pane>

            <!-- Logs Tab -->
            <el-tab-pane label="操作记录" name="logs">
              <el-form :model="logQuery" :inline="true" size="small">
                <el-form-item label="日志类型">
                  <el-select v-model="logQuery.logType" placeholder="全部" clearable style="width:140px;">
                    <el-option label="新增" value="INSERT" /><el-option label="修改" value="UPDATE" />
                    <el-option label="删除" value="DELETE" /><el-option label="测试连接" value="TEST" />
                    <el-option label="同步" value="SYNC" /><el-option label="中文名" value="CN_NAME" />
                  </el-select>
                </el-form-item>
                <el-form-item label="结果">
                  <el-select v-model="logQuery.result" placeholder="全部" clearable style="width:100px;">
                    <el-option label="成功" value="1" /><el-option label="失败" value="0" />
                  </el-select>
                </el-form-item>
                <el-form-item><el-button type="primary" icon="el-icon-search" @click="loadLogs">查询</el-button></el-form-item>
              </el-form>
              <el-table :data="logList" v-loading="logLoading" size="small">
                <el-table-column prop="operTime" label="日期" width="170" />
                <el-table-column prop="logType" label="日志类型" width="100">
                  <template slot-scope="scope">{{ logTypeMap[scope.row.logType] || scope.row.logType }}</template>
                </el-table-column>
                <el-table-column prop="operatorName" label="操作人" width="100" />
                <el-table-column prop="result" label="结果" width="70">
                  <template slot-scope="scope">
                    <el-tag :type="scope.row.result === '1' ? 'success' : 'danger'" size="mini">
                      {{ scope.row.result === '1' ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="message" label="消息" min-width="200" />
                <el-table-column label="详情" width="70">
                  <template slot-scope="scope">
                    <el-button v-if="scope.row.detailJson" type="text" size="mini" @click="showDetail(scope.row)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <pagination v-show="logTotal > 0" :total="logTotal" :page.sync="logQuery.pageNum" :limit.sync="logQuery.pageSize" @pagination="loadLogs" />
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>
    </el-row>

    <!-- Add/Edit Dialog -->
    <el-dialog :title="dialogTitle" :visible.sync="dialogVisible" width="650px" append-to-body @close="resetForm">
      <el-form ref="form" :model="form" :rules="rules" label-width="120px" size="small">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="目录" prop="catalogId">
              <el-select v-model="form.catalogId" placeholder="选择目录" style="width:100%;">
                <el-option v-for="cat in catalogList" :key="cat.catalogId" :label="cat.catalogName" :value="cat.catalogId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源名称" prop="sourceName">
              <el-input v-model="form.sourceName" placeholder="请输入" maxlength="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="主机" prop="host">
              <el-input v-model="form.host" placeholder="127.0.0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="form.port" :min="1" :max="65535" style="width:100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数据库名称" prop="databaseName">
              <el-input v-model="form.databaseName" placeholder="请输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" show-password placeholder="请输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源类型">
              <el-select v-model="form.sourceType" style="width:100%;">
                <el-option label="MySQL" value="MYSQL" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="连接池"><el-radio-group v-model="form.usePool"><el-radio label="0">否</el-radio><el-radio label="1">是</el-radio></el-radio-group></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="SSL"><el-radio-group v-model="form.useSsl"><el-radio label="0">否</el-radio><el-radio label="1">是</el-radio></el-radio-group></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="dialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" icon="el-icon-link" @click="handleTestFromDialog">测试连接</el-button>
        <el-button size="small" type="primary" @click="submitForm">保存</el-button>
      </div>
    </el-dialog>

    <!-- Columns Dialog -->
    <el-dialog :title="'字段信息：总列数（' + columns.length + '）'" :visible.sync="columnsVisible" width="900px" append-to-body>
      <el-table :data="columns" size="small" max-height="500">
        <el-table-column prop="ordinalPosition" label="序号" width="70" />
        <el-table-column prop="columnName" label="字段名" min-width="160" />
        <el-table-column prop="columnType" label="类型" width="160" />
        <el-table-column prop="columnComment" label="备注" min-width="160" />
        <el-table-column prop="isPk" label="主键" width="60">
          <template slot-scope="scope"><el-tag v-if="scope.row.isPk === '1'" type="danger" size="mini">是</el-tag><span v-else>-</span></template>
        </el-table-column>
        <el-table-column prop="isFk" label="外键" width="60">
          <template slot-scope="scope"><el-tag v-if="scope.row.isFk === '1'" type="warning" size="mini">是</el-tag><span v-else>-</span></template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>
```

- [ ] **Step 2: Create index.vue — Script section**

```vue
<script>
import { treeDataSource, getDataSource, addDataSource, updateDataSource, delDataSource,
  testDataSource, syncDataSource, listTables, listColumns, updateTableCnName, listLogs } from '@/api/databroker/datasource'
import { listCatalog } from '@/api/databroker/datasource'

export default {
  name: 'DatabrokerDataSource',
  data() {
    return {
      filterText: '',
      treeData: [],
      treeProps: { children: 'children', label: 'label' },
      selectedNode: null,
      datasource: {},
      activeTab: 'basic',

      // Table
      tableQuery: { pageNum: 1, pageSize: 10, objectName: '', objectType: '' },
      tableList: [],
      tableLoading: false,
      tableTotal: 0,
      tableStats: { tableCount: 0, viewCount: 0 },

      // Logs
      logQuery: { pageNum: 1, pageSize: 10, logType: '', result: '' },
      logList: [],
      logLoading: false,
      logTotal: 0,
      logTypeMap: { INSERT: '新增', UPDATE: '修改', DELETE: '删除', TEST: '测试连接', SYNC: '同步', CN_NAME: '修改中文名' },

      // Dialog
      dialogTitle: '',
      dialogVisible: false,
      form: { catalogId: null, sourceName: '', sourceType: 'MYSQL', host: '', port: 3306, databaseName: '', username: '', password: '', usePool: '0', useSsl: '0', jdbcParams: '{}', remark: '' },
      rules: {
        catalogId: [{ required: true, message: '请选择目录', trigger: 'change' }],
        sourceName: [{ required: true, message: '请输入名称', trigger: 'blur' }],
        host: [{ required: true, message: '请输入主机', trigger: 'blur' }],
        port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
        databaseName: [{ required: true, message: '请输入数据库名称', trigger: 'blur' }],
        username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
        password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
      },
      catalogList: [],

      // Columns dialog
      columnsVisible: false,
      columns: []
    }
  },
  watch: {
    filterText(val) { this.$refs.tree.filter(val) }
  },
  created() {
    this.loadTree()
    this.loadCatalogs()
  },
  methods: {
    loadTree() {
      treeDataSource().then(res => { this.treeData = res.data })
    },
    loadCatalogs() {
      listCatalog().then(res => { this.catalogList = res.rows || res.data || [] })
    },
    filterNode(value, data) {
      if (!value) return true
      return data.label.indexOf(value) !== -1
    },
    handleNodeClick(data) {
      this.selectedNode = data
      if (data.nodeType === 'datasource') {
        this.activeTab = 'basic'
        getDataSource(data.datasourceId).then(res => {
          this.datasource = res.data
          this.loadTableStats()
          this.loadTables()
          this.loadLogs()
        })
      }
    },
    handleAdd() {
      this.dialogTitle = '新增数据源'
      this.resetForm()
      this.dialogVisible = true
    },
    handleEdit() {
      this.dialogTitle = '修改数据源'
      this.form = {
        datasourceId: this.datasource.datasourceId,
        catalogId: this.datasource.catalogId,
        sourceName: this.datasource.sourceName,
        sourceType: this.datasource.sourceType,
        host: this.datasource.host,
        port: this.datasource.port,
        databaseName: this.datasource.databaseName,
        username: this.datasource.username,
        password: '******',
        usePool: this.datasource.usePool || '0',
        useSsl: this.datasource.useSsl || '0',
        jdbcParams: this.datasource.jdbcParams || '{}',
        remark: this.datasource.remark || ''
      }
      this.dialogVisible = true
    },
    resetForm() {
      this.form = { catalogId: null, sourceName: '', sourceType: 'MYSQL', host: '', port: 3306, databaseName: '', username: '', password: '', usePool: '0', useSsl: '0', jdbcParams: '{}', remark: '' }
      this.$nextTick(() => { if (this.$refs.form) this.$refs.form.clearValidate() })
    },
    submitForm() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        if (this.form.datasourceId) {
          updateDataSource(this.form).then(() => { this.msgSuccess('修改成功'); this.dialogVisible = false; this.loadTree() })
        } else {
          addDataSource(this.form).then(() => { this.msgSuccess('新增成功'); this.dialogVisible = false; this.loadTree() })
        }
      })
    },
    handleTestFromDialog() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        testDataSource(this.form).then(res => {
          this.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
        })
      })
    },
    handleTestFromDetail() {
      const params = { ...this.datasource, password: '******' }
      testDataSource(params).then(res => {
        this.msgSuccess('连接成功，数据库版本：' + (res.data && res.data.dbVersion ? res.data.dbVersion : 'unknown'))
      })
    },
    handleSync() {
      this.$confirm('确认同步元数据？', '提示', { type: 'warning' }).then(() => {
        syncDataSource(this.datasource.datasourceId).then(res => {
          const d = res.data
          this.msgSuccess('同步成功：表' + d.tableCount + '个，视图' + d.viewCount + '个，字段' + d.columnCount + '个')
          getDataSource(this.datasource.datasourceId).then(r => { this.datasource = r.data })
          this.loadTableStats()
          this.loadTables()
        })
      })
    },

    // Tables
    loadTableStats() {
      listTables(this.datasource.datasourceId, { pageNum: 1, pageSize: 1 }).then(res => {
        // Count by type from all data
        listTables(this.datasource.datasourceId, { pageNum: 1, pageSize: 999 }).then(r => {
          const all = r.rows || []
          this.tableStats.tableCount = all.filter(t => t.objectType === 'TABLE').length
          this.tableStats.viewCount = all.filter(t => t.objectType === 'VIEW').length
        })
      })
    },
    loadTables() {
      this.tableLoading = true
      listTables(this.datasource.datasourceId, this.tableQuery).then(res => {
        this.tableList = res.rows || []
        this.tableTotal = res.total || 0
        this.tableLoading = false
      }).catch(() => { this.tableLoading = false })
    },
    saveCnName(row) {
      if (!row.cnName || row.cnName.length > 60) { this.msgError('中文名最长60字符'); return }
      updateTableCnName(row.tableId, { cnName: row.cnName }).then(() => { this.msgSuccess('中文名已更新') })
    },
    showColumns(row) {
      listColumns(row.tableId).then(res => {
        this.columns = res.data || []
        this.columnsVisible = true
      })
    },

    // Logs
    loadLogs() {
      this.logLoading = true
      listLogs(this.datasource.datasourceId, this.logQuery).then(res => {
        this.logList = res.rows || []
        this.logTotal = res.total || 0
        this.logLoading = false
      }).catch(() => { this.logLoading = false })
    },
    showDetail(row) {
      let detail = row.detailJson
      try { detail = JSON.stringify(JSON.parse(detail), null, 2) } catch (e) {}
      this.$alert(detail, '操作详情', { confirmButtonText: '关闭', customClass: 'log-detail-dialog' })
    }
  }
}
</script>
```

- [ ] **Step 3: Create index.vue — Style section**

```vue
<style scoped>
.tree-panel {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  min-height: 500px;
  background: #fff;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
  font-weight: bold;
  font-size: 14px;
}
.tree-header i { margin-right: 4px; color: #409EFF; }
.custom-tree-node { flex: 1; display: flex; align-items: center; font-size: 13px; }
.custom-tree-node i { margin-right: 5px; color: #409EFF; }
.empty-state { text-align: center; padding: 120px 0; color: #909399; }
.info-bar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 8px;
}
.info-bar-icon { font-size: 24px; color: #409EFF; margin-right: 8px; }
.info-bar-title { font-size: 16px; font-weight: 600; }
.table-stats { padding: 8px 0; }
</style>
```

- [ ] **Step 4: Create a simple catalog list API helper**

Since the dialog needs a catalog list, add to `ruoyi-ui/src/api/databroker/datasource.js`:

```javascript
// 目录列表（用于下拉选择）
export function listCatalog() {
  return request({
    url: '/databroker/datasource/tree',
    method: 'get'
  })
}
```

Actually, we need a dedicated catalog API. Let's update the plan — instead of a separate file, I'll have the frontend extract catalogs from the tree data. The `loadCatalogs` method should just use the tree data:

In the dialog, instead of a separate catalog API, extract catalog options from tree data. Update `loadCatalogs`:
```javascript
loadCatalogs() {
  // Extract catalogs from tree data
  const cats = []
  const walk = (nodes) => {
    nodes.forEach(n => {
      if (n.nodeType === 'catalog') cats.push({ catalogId: n.catalogId, catalogName: n.label })
      if (n.children) walk(n.children)
    })
  }
  walk(this.treeData)
  this.catalogList = cats
}
```

And change `created` to call `loadCatalogs` after tree loads:
```javascript
created() {
  this.loadTree()
},
```

Modify `loadTree`:
```javascript
loadTree() {
  treeDataSource().then(res => {
    this.treeData = res.data
    this.loadCatalogsFromTree()
  })
},
```

This avoids needing a separate catalog controller. For now, skip the separate catalog list API and use the tree data.

- [ ] **Step 5: Ensure frontend builds**

Run: `cd ruoyi-ui && npm run build:prod`
Expected: Build succeeds without errors

- [ ] **Step 6: Commit**

```bash
git add ruoyi-ui/src/views/databroker/datasource/index.vue
git commit -m "feat: add databroker datasource management page"
```

---

## Post-Implementation Verification

After all tasks complete and the server is running:

1. Run `databroker_schema.sql` and `databroker_menu.sql` against the `ry` database
2. Assign `databroker:datasource:*` permissions to admin role in `sys_role_menu`
3. Re-login to see "数据代理" menu in sidebar
4. Create a test catalog in `dp_datasource_catalog`:
   ```sql
   insert into dp_datasource_catalog (catalog_id, parent_id, catalog_name, order_num, status, create_by, create_time)
   values (10, 0, 'MySQL连接管理', 0, '0', 'admin', sysdate());
   ```
5. Add a datasource pointing to the local `ry` database via the UI
6. Test connection → expect success with MySQL version
7. Sync metadata → expect `ind_tag_data` table to appear
8. Browse tables tab, verify table count, edit Chinese name
9. Click "字段信息" to view columns
10. Check operation logs tab
11. Verify no plaintext password in API responses or logs

---

## Self-Review Notes

- All tables, columns, and SQL match the dev doc §6 exactly
- Menu IDs confirmed available (2000-2007)
- Password encryption uses AES/GCM/NoPadding as required
- `passwordCipher` excluded from API responses; `password` returns `******`
- `cn_name` not overwritten on re-sync
- Orphan columns deleted per §12.3 rule
- Frontend follows RuoYi patterns (Element UI, `v-hasPermi`, `@/utils/request`)
