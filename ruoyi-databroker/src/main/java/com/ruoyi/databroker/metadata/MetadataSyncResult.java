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
