package com.ruoyi.taglibrary.domain.dto;

/**
 * Skill 生命周期状态流转请求
 *
 * <p>动作与目标版本由前端提交，操作人从登录态取，防止伪造。</p>
 */
public class SkillStatusRequest {

    /** 动作：publish / offline / deprecate / draft */
    private String action;

    /** 目标版本（可选，缺省用 Python 侧当前版本） */
    private String version;

    /** 操作原因（必填，用于审计留痕） */
    private String reason;

    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }
}
