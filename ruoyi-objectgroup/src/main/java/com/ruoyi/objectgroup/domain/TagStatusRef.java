package com.ruoyi.objectgroup.domain;

/**
 * 标签状态快照（对象群统一校验用：发布状态 + 来源状态 + 类型）
 */
public class TagStatusRef {

    private Long tagId;
    private String fieldName;
    private String tagName;
    private String tagType;
    private String dataType;
    /** 发布状态：0待上线 1上线审核中 2已上线 3已下线 4待完善 */
    private String status;
    /** 来源状态：AVAILABLE 可用 / MISSING 来源缺失 / CHANGED 来源变更待确认 */
    private String sourceStatus;

    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
    public String getTagType() { return tagType; }
    public void setTagType(String tagType) { this.tagType = tagType; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getSourceStatus() { return sourceStatus; }
    public void setSourceStatus(String sourceStatus) { this.sourceStatus = sourceStatus; }
}
