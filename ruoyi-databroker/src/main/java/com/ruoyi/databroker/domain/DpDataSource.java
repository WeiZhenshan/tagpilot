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
    private Integer orderNum;
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
    public Integer getOrderNum() { return orderNum; }
    public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }
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
