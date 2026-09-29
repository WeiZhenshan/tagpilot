package com.ruoyi.taglibrary.domain.dto;

import java.util.Map;

/**
 * Skill 试运行请求
 *
 * <p>前端只提交客群与运行参数，成员名单（member_ids）由 Java 侧解析客群规则后补齐，
 * 不接受前端直接传入成员列表，避免越权圈人。</p>
 */
public class SkillRunRequest {

    /** 客群ID（tl_object_group.group_id） */
    private Long groupId;

    /** 基准类型（可选，缺省用 Manifest default_benchmark） */
    private String benchmarkType;

    /** 数据日期（可选，yyyy-MM-dd，缺省今天） */
    private String asOfDate;

    /** Skill 自定义参数（可选，由 Python 侧白名单校验） */
    private Map<String, Object> params;

    public Long getGroupId() { return groupId; }
    public void setGroupId(Long groupId) { this.groupId = groupId; }
    public String getBenchmarkType() { return benchmarkType; }
    public void setBenchmarkType(String benchmarkType) { this.benchmarkType = benchmarkType; }
    public String getAsOfDate() { return asOfDate; }
    public void setAsOfDate(String asOfDate) { this.asOfDate = asOfDate; }
    public Map<String, Object> getParams() { return params; }
    public void setParams(Map<String, Object> params) { this.params = params; }
}
