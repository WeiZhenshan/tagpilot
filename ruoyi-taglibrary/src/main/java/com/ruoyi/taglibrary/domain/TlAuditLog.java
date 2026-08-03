package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签审批日志对象 tl_audit_log
 *
 * @author ruoyi
 */
public class TlAuditLog extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 日志ID */
    private Long logId;

    /** 业务类型（library/tag） */
    private String bizType;

    /** 业务对象ID */
    private Long bizId;

    /** 业务对象名称（库名/标签名，join 展示字段，非表列） */
    private String bizName;

    /** 动作（提交/通过/驳回/上线/下线） */
    private String action;

    /** 变更前状态 */
    private String fromStatus;

    /** 变更后状态 */
    private String toStatus;

    /** 申请人 */
    private String applyBy;

    /** 审批人 */
    private String auditBy;

    /** 审批时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date auditTime;

    /** 审批意见 */
    private String auditComment;

    public Long getLogId() { return logId; }
    public void setLogId(Long logId) { this.logId = logId; }
    public String getBizType() { return bizType; }
    public void setBizType(String bizType) { this.bizType = bizType; }
    public Long getBizId() { return bizId; }
    public void setBizId(Long bizId) { this.bizId = bizId; }
    public String getBizName() { return bizName; }
    public void setBizName(String bizName) { this.bizName = bizName; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getFromStatus() { return fromStatus; }
    public void setFromStatus(String fromStatus) { this.fromStatus = fromStatus; }
    public String getToStatus() { return toStatus; }
    public void setToStatus(String toStatus) { this.toStatus = toStatus; }
    public String getApplyBy() { return applyBy; }
    public void setApplyBy(String applyBy) { this.applyBy = applyBy; }
    public String getAuditBy() { return auditBy; }
    public void setAuditBy(String auditBy) { this.auditBy = auditBy; }
    public Date getAuditTime() { return auditTime; }
    public void setAuditTime(Date auditTime) { this.auditTime = auditTime; }
    public String getAuditComment() { return auditComment; }
    public void setAuditComment(String auditComment) { this.auditComment = auditComment; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("logId", getLogId())
            .append("bizType", getBizType())
            .append("bizId", getBizId())
            .append("action", getAction())
            .append("fromStatus", getFromStatus())
            .append("toStatus", getToStatus())
            .append("applyBy", getApplyBy())
            .append("auditBy", getAuditBy())
            .append("auditTime", getAuditTime())
            .toString();
    }
}
