package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;
import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;

/**
 * 标签库同步对账结果（版本信息 + 对账统计）
 *
 * @author ruoyi
 */
public class TagSyncResultVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 标签库ID */
    private Long libraryId;

    /** 实际同步的数据集版本ID */
    private Long versionId;

    /** 版本号 */
    private Integer versionNo;

    /** 版本名称 */
    private String versionName;

    /** 版本选择原因 */
    private String reason;

    /** 新增标签数 */
    private Integer addedCount;

    /** 新标记来源缺失数 */
    private Integer missingCount;

    /** 恢复可用数 */
    private Integer restoredCount;

    /** 新标记来源变更数 */
    private Integer changedCount;

    /** 同步时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date syncTime;

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public Long getVersionId() { return versionId; }
    public void setVersionId(Long versionId) { this.versionId = versionId; }
    public Integer getVersionNo() { return versionNo; }
    public void setVersionNo(Integer versionNo) { this.versionNo = versionNo; }
    public String getVersionName() { return versionName; }
    public void setVersionName(String versionName) { this.versionName = versionName; }
    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }
    public Integer getAddedCount() { return addedCount; }
    public void setAddedCount(Integer addedCount) { this.addedCount = addedCount; }
    public Integer getMissingCount() { return missingCount; }
    public void setMissingCount(Integer missingCount) { this.missingCount = missingCount; }
    public Integer getRestoredCount() { return restoredCount; }
    public void setRestoredCount(Integer restoredCount) { this.restoredCount = restoredCount; }
    public Integer getChangedCount() { return changedCount; }
    public void setChangedCount(Integer changedCount) { this.changedCount = changedCount; }
    public Date getSyncTime() { return syncTime; }
    public void setSyncTime(Date syncTime) { this.syncTime = syncTime; }
}
