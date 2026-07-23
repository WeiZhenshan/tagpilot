package com.ruoyi.databroker.domain;

import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 数据集输出字段（dp_dataset_field 无审计列，不继承 BaseEntity）
 */
public class DpDatasetField {
    private Long fieldId;
    private Long versionId;
    private String fieldAlias;
    private String fieldName;
    private Long sourceTableId;
    private Long sourceColumnId;
    private String dataType;
    private String expressionJson;
    private String isObjectKey;
    private String sensitivityLevel;
    private String maskRule;
    private String enabled;
    private Integer orderNum;

    // getters and setters
    public Long getFieldId() { return fieldId; }
    public void setFieldId(Long fieldId) { this.fieldId = fieldId; }
    public Long getVersionId() { return versionId; }
    public void setVersionId(Long versionId) { this.versionId = versionId; }
    public String getFieldAlias() { return fieldAlias; }
    public void setFieldAlias(String fieldAlias) { this.fieldAlias = fieldAlias; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public Long getSourceTableId() { return sourceTableId; }
    public void setSourceTableId(Long sourceTableId) { this.sourceTableId = sourceTableId; }
    public Long getSourceColumnId() { return sourceColumnId; }
    public void setSourceColumnId(Long sourceColumnId) { this.sourceColumnId = sourceColumnId; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getExpressionJson() { return expressionJson; }
    public void setExpressionJson(String expressionJson) { this.expressionJson = expressionJson; }
    public String getIsObjectKey() { return isObjectKey; }
    public void setIsObjectKey(String isObjectKey) { this.isObjectKey = isObjectKey; }
    public String getSensitivityLevel() { return sensitivityLevel; }
    public void setSensitivityLevel(String sensitivityLevel) { this.sensitivityLevel = sensitivityLevel; }
    public String getMaskRule() { return maskRule; }
    public void setMaskRule(String maskRule) { this.maskRule = maskRule; }
    public String getEnabled() { return enabled; }
    public void setEnabled(String enabled) { this.enabled = enabled; }
    public Integer getOrderNum() { return orderNum; }
    public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("fieldId", getFieldId())
            .append("versionId", getVersionId())
            .append("fieldAlias", getFieldAlias())
            .append("fieldName", getFieldName())
            .toString();
    }
}
