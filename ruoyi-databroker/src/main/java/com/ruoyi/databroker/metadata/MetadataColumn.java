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
