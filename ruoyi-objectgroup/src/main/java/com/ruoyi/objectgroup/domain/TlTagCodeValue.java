package com.ruoyi.objectgroup.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签码值对象 tl_tag_code_value
 *
 * @author ruoyi
 */
public class TlTagCodeValue extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 码值ID */
    private Long valueId;

    /** 所属标签库ID */
    private Long libraryId;

    /** 标签名称（英文，源字段名） */
    private String fieldName;

    /** 标签名称（中文） */
    private String tagName;

    /** 标签码值（宽表存储值） */
    private String code;

    /** 码值定义（显示值） */
    private String codeDefinition;

    /** 码值排序 */
    private Integer orderNum;

    public Long getValueId() { return valueId; }
    public void setValueId(Long valueId) { this.valueId = valueId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }
    public String getCodeDefinition() { return codeDefinition; }
    public void setCodeDefinition(String codeDefinition) { this.codeDefinition = codeDefinition; }
    public Integer getOrderNum() { return orderNum; }
    public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("valueId", getValueId())
            .append("libraryId", getLibraryId())
            .append("fieldName", getFieldName())
            .append("code", getCode())
            .append("codeDefinition", getCodeDefinition())
            .toString();
    }
}
