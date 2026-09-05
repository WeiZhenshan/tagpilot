package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签元数据变更对象 tl_tag_metadata_change
 *
 * @author ruoyi
 */
public class TlTagMetadataChange extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 变更ID */
    private Long changeId;

    /** 标签库ID */
    private Long libraryId;

    /** 标签ID */
    private Long tagId;

    /** 创建草稿时的 tl_tag.version */
    private Integer baseVersion;

    /** 变更类型（FIRST首次建档 METADATA元数据修改 SOURCE来源变更确认） */
    private String changeType;

    /** 变更前快照（JSON，仅五个可改字段） */
    private String beforeJson;

    /** 变更后快照（JSON，仅五个可改字段） */
    private String afterJson;

    /** 变更前来源快照JSON（已确认来源，无已确认则为 null） */
    private String sourceBefore;

    /** 变更后来源快照JSON（申请时的观测来源） */
    private String sourceAfter;

    /** 草稿修订号（保存草稿递增，提交/审核校验） */
    private Integer revision;

    /** 状态（DRAFT草稿 PENDING待审核 APPROVED已通过 REJECTED已驳回） */
    private String status;

    /** 申请人 */
    private String applyBy;

    /** 提交时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date submitTime;

    /** 审核人 */
    private String auditBy;

    /** 审核时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date auditTime;

    /** 审核意见 */
    private String auditComment;

    /** 源字段名（联表展示字段，非表列） */
    private String fieldName;

    /** 标签名称（联表展示字段，非表列） */
    private String tagName;

    /** 标签库名称（联表展示字段，非表列） */
    private String libraryName;

    /** 变更字段摘要（before/after 差异字段中文名，非表列） */
    private String changedFields;

    public Long getChangeId() { return changeId; }
    public void setChangeId(Long changeId) { this.changeId = changeId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public Integer getBaseVersion() { return baseVersion; }
    public void setBaseVersion(Integer baseVersion) { this.baseVersion = baseVersion; }
    public String getChangeType() { return changeType; }
    public void setChangeType(String changeType) { this.changeType = changeType; }
    public String getBeforeJson() { return beforeJson; }
    public void setBeforeJson(String beforeJson) { this.beforeJson = beforeJson; }
    public String getAfterJson() { return afterJson; }
    public void setAfterJson(String afterJson) { this.afterJson = afterJson; }
    public String getSourceBefore() { return sourceBefore; }
    public void setSourceBefore(String sourceBefore) { this.sourceBefore = sourceBefore; }
    public String getSourceAfter() { return sourceAfter; }
    public void setSourceAfter(String sourceAfter) { this.sourceAfter = sourceAfter; }
    public Integer getRevision() { return revision; }
    public void setRevision(Integer revision) { this.revision = revision; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getApplyBy() { return applyBy; }
    public void setApplyBy(String applyBy) { this.applyBy = applyBy; }
    public Date getSubmitTime() { return submitTime; }
    public void setSubmitTime(Date submitTime) { this.submitTime = submitTime; }
    public String getAuditBy() { return auditBy; }
    public void setAuditBy(String auditBy) { this.auditBy = auditBy; }
    public Date getAuditTime() { return auditTime; }
    public void setAuditTime(Date auditTime) { this.auditTime = auditTime; }
    public String getAuditComment() { return auditComment; }
    public void setAuditComment(String auditComment) { this.auditComment = auditComment; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
    public String getLibraryName() { return libraryName; }
    public void setLibraryName(String libraryName) { this.libraryName = libraryName; }
    public String getChangedFields() { return changedFields; }
    public void setChangedFields(String changedFields) { this.changedFields = changedFields; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("changeId", getChangeId())
            .append("libraryId", getLibraryId())
            .append("tagId", getTagId())
            .append("baseVersion", getBaseVersion())
            .append("status", getStatus())
            .append("applyBy", getApplyBy())
            .append("submitTime", getSubmitTime())
            .append("auditBy", getAuditBy())
            .append("auditTime", getAuditTime())
            .toString();
    }
}
