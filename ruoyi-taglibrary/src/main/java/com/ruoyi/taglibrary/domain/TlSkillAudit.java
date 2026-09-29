package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 洞察Skill管理动作审计 tl_skill_audit
 *
 * <p>Skill 的发布、下线、废弃、转草稿等治理动作全部留痕：无论 Python 侧成功或失败，
 * 都记录操作人、原因与结果，失败时 result 保存失败原因。</p>
 */
public class TlSkillAudit extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 审计ID */
    private Long auditId;

    /** 技能ID */
    private String skillId;

    /** 技能版本 */
    private String version;

    /** 动作：publish / offline / deprecate / draft */
    private String action;

    /** 操作人ID */
    private String operatorId;

    /** 操作人名称 */
    private String operatorName;

    /** 操作原因 */
    private String reason;

    /** 执行结果（变更后状态或失败原因） */
    private String result;

    public Long getAuditId() { return auditId; }
    public void setAuditId(Long auditId) { this.auditId = auditId; }
    public String getSkillId() { return skillId; }
    public void setSkillId(String skillId) { this.skillId = skillId; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getOperatorId() { return operatorId; }
    public void setOperatorId(String operatorId) { this.operatorId = operatorId; }
    public String getOperatorName() { return operatorName; }
    public void setOperatorName(String operatorName) { this.operatorName = operatorName; }
    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }
    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
}
