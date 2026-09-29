package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 洞察Skill运行记录 tl_skill_run
 *
 * <p>Skill 的执行权威在 Python（tagpilot-agent），本表仅在治理侧留存关键字段，
 * 用于权限化的运行历史查询与审计取证。</p>
 */
public class TlSkillRun extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 运行ID（主键，Python 侧生成） */
    private String runId;

    /** 技能ID */
    private String skillId;

    /** 技能版本 */
    private String skillVersion;

    /** 客群ID（兼容 bigint，统一按字符串保存） */
    private String audienceId;

    /** 客群名称快照 */
    private String audienceName;

    /** 客群成员数 */
    private Integer customerCount;

    /** 运行状态：succeeded / blocked / failed */
    private String status;

    /** 被阻断原因（中文） */
    private String blockedReason;

    /** 执行耗时（毫秒） */
    private Long durationMs;

    /** 操作人ID */
    private String operatorId;

    /** 操作人名称 */
    private String operatorName;

    /** 链路追踪ID */
    private String traceId;

    public String getRunId() { return runId; }
    public void setRunId(String runId) { this.runId = runId; }
    public String getSkillId() { return skillId; }
    public void setSkillId(String skillId) { this.skillId = skillId; }
    public String getSkillVersion() { return skillVersion; }
    public void setSkillVersion(String skillVersion) { this.skillVersion = skillVersion; }
    public String getAudienceId() { return audienceId; }
    public void setAudienceId(String audienceId) { this.audienceId = audienceId; }
    public String getAudienceName() { return audienceName; }
    public void setAudienceName(String audienceName) { this.audienceName = audienceName; }
    public Integer getCustomerCount() { return customerCount; }
    public void setCustomerCount(Integer customerCount) { this.customerCount = customerCount; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getBlockedReason() { return blockedReason; }
    public void setBlockedReason(String blockedReason) { this.blockedReason = blockedReason; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public String getOperatorId() { return operatorId; }
    public void setOperatorId(String operatorId) { this.operatorId = operatorId; }
    public String getOperatorName() { return operatorName; }
    public void setOperatorName(String operatorName) { this.operatorName = operatorName; }
    public String getTraceId() { return traceId; }
    public void setTraceId(String traceId) { this.traceId = traceId; }
}
