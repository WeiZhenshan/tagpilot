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
