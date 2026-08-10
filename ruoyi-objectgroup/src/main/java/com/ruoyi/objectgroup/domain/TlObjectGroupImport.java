package com.ruoyi.objectgroup.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 对象群导入值对象 tl_object_group_import
 *
 * @author ruoyi
 */
public class TlObjectGroupImport extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 导入ID */
    private Long importId;

    /** 导入批次号（UUID） */
    private String importBatch;

    /** 归属对象群ID（保存后回填） */
    private Long groupId;

    /** 客户号字段名 */
    private String fieldName;

    /** 客户号值 */
    private String value;

    public Long getImportId() { return importId; }
    public void setImportId(Long importId) { this.importId = importId; }
    public String getImportBatch() { return importBatch; }
    public void setImportBatch(String importBatch) { this.importBatch = importBatch; }
    public Long getGroupId() { return groupId; }
    public void setGroupId(Long groupId) { this.groupId = groupId; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getValue() { return value; }
    public void setValue(String value) { this.value = value; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("importId", getImportId())
            .append("importBatch", getImportBatch())
            .append("groupId", getGroupId())
            .append("value", getValue())
            .toString();
    }
}
