package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;

/**
 * 审批/状态流转请求（submit/audit/offline 复用）
 *
 * @author ruoyi
 */
public class AuditRequest implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 批量对象ID */
    private Long[] ids;

    /** audit 用：true通过 false驳回 */
    private Boolean pass;

    /** 审批意见 */
    private String auditComment;

    public Long[] getIds() { return ids; }
    public void setIds(Long[] ids) { this.ids = ids; }
    public Boolean getPass() { return pass; }
    public void setPass(Boolean pass) { this.pass = pass; }
    public String getAuditComment() { return auditComment; }
    public void setAuditComment(String auditComment) { this.auditComment = auditComment; }
}
