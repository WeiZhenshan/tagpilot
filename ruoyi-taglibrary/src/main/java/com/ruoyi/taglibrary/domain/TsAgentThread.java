package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;

/** 用户圈选任务；业务载荷加密存储。 */
public class TsAgentThread extends BaseEntity {
    private String threadId, title, archived, pinned, payload;
    private Long userId, libraryId, rowVersion;
    public String getThreadId() { return threadId; }
    public void setThreadId(String v) { threadId=v; }
    public String getTitle() { return title; }
    public void setTitle(String v) { title=v; }
    public String getArchived() { return archived; }
    public void setArchived(String v) { archived=v; }
    public String getPinned() { return pinned; }
    public void setPinned(String v) { pinned=v; }
    public String getPayload() { return payload; }
    public void setPayload(String v) { payload=v; }
    public Long getUserId() { return userId; }
    public void setUserId(Long v) { userId=v; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long v) { libraryId=v; }
    public Long getRowVersion() { return rowVersion; }
    public void setRowVersion(Long v) { rowVersion=v; }
}
