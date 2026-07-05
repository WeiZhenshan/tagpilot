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
