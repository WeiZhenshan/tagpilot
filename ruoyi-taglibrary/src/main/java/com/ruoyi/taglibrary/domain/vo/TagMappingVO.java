package com.ruoyi.taglibrary.domain.vo;

import com.ruoyi.taglibrary.domain.TlTag;

/**
 * 批量映射列表行（标签信息 + 元数据变更状态合并）
 *
 * @author ruoyi
 */
public class TagMappingVO extends TlTag {
    private static final long serialVersionUID = 1L;

    /** 变更记录ID（无变更时为 null） */
    private Long changeId;

    /** 变更状态（DRAFT草稿 PENDING待审核） */
    private String changeStatus;

    /** 变更申请人 */
    private String applyBy;

    /** 变更后快照（JSON，仅五个可改字段） */
    private String afterJson;

    /** 是否本人草稿（草稿存在且申请人=当前用户） */
    private Boolean ownDraft;

    public Long getChangeId() { return changeId; }
    public void setChangeId(Long changeId) { this.changeId = changeId; }
    public String getChangeStatus() { return changeStatus; }
    public void setChangeStatus(String changeStatus) { this.changeStatus = changeStatus; }
    public String getApplyBy() { return applyBy; }
    public void setApplyBy(String applyBy) { this.applyBy = applyBy; }
    public String getAfterJson() { return afterJson; }
    public void setAfterJson(String afterJson) { this.afterJson = afterJson; }
    public Boolean getOwnDraft() { return ownDraft; }
    public void setOwnDraft(Boolean ownDraft) { this.ownDraft = ownDraft; }
}
