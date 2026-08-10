package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;

/**
 * 元数据变更提交/审核请求（submit/audit 复用）
 *
 * @author ruoyi
 */
public class MetadataChangeRequest implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 批量变更ID */
    private Long[] changeIds;

    /** audit 用：true通过 false驳回 */
    private Boolean pass;

    /** 审核意见 */
    private String auditComment;

    public Long[] getChangeIds() { return changeIds; }
    public void setChangeIds(Long[] changeIds) { this.changeIds = changeIds; }
    public Boolean getPass() { return pass; }
    public void setPass(Boolean pass) { this.pass = pass; }
    public String getAuditComment() { return auditComment; }
    public void setAuditComment(String auditComment) { this.auditComment = auditComment; }
}
