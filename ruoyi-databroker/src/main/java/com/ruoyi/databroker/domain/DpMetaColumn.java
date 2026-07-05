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
