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
