package com.ruoyi.objectgroup.domain.vo;

/**
 * 码值同步结果
 */
public class CodeValueSyncVO {

    /** 实际同步的码值数量 */
    private int syncedCount;

    /** 宽表去重后码值超过单次同步上限，结果被截断 */
    private boolean truncated;

    public CodeValueSyncVO(int syncedCount, boolean truncated) {
        this.syncedCount = syncedCount;
        this.truncated = truncated;
    }

    public int getSyncedCount() { return syncedCount; }
    public void setSyncedCount(int syncedCount) { this.syncedCount = syncedCount; }
    public boolean isTruncated() { return truncated; }
    public void setTruncated(boolean truncated) { this.truncated = truncated; }
}
