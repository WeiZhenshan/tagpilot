package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签对象 tl_tag
 *
 * @author ruoyi
 */
public class TlTag extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 标签ID */
    private Long tagId;

    /** 所属标签库ID */
    private Long libraryId;

    /** 所属标签库名称（列表展示字段，非表列） */
    private String libraryName;

    /** 所属目录ID */
    private Long dirId;

    /** 源字段名 */
    private String fieldName;

    /** 标签中文名 */
    private String tagName;

    /** 源字段数据类型 */
    private String dataType;

    /** 标签类型（字典 tag_type） */
    private String tagType;

    /** 是否对象键（0否 1是，源字段主键标记） */
    private String isObjectKey;

    /** 业务口径 */
    private String businessCaliber;

    /** 技术口径 */
    private String techCaliber;

    /** 有效日期 */
    private String validPeriod;

    /** 更新周期（字典 tag_update_cycle） */
    private String updateCycle;

    /** 创建方式（同步/自建） */
    private String createWay;

    /** 状态（0草稿 1待审批 2已上线 3已下线） */
    private String status;

    /** 版本号 */
    private Integer version;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getLibraryName() { return libraryName; }
    public void setLibraryName(String libraryName) { this.libraryName = libraryName; }
    public Long getDirId() { return dirId; }
    public void setDirId(Long dirId) { this.dirId = dirId; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getTagType() { return tagType; }
    public void setTagType(String tagType) { this.tagType = tagType; }
    public String getIsObjectKey() { return isObjectKey; }
    public void setIsObjectKey(String isObjectKey) { this.isObjectKey = isObjectKey; }
    public String getBusinessCaliber() { return businessCaliber; }
    public void setBusinessCaliber(String businessCaliber) { this.businessCaliber = businessCaliber; }
    public String getTechCaliber() { return techCaliber; }
    public void setTechCaliber(String techCaliber) { this.techCaliber = techCaliber; }
    public String getValidPeriod() { return validPeriod; }
    public void setValidPeriod(String validPeriod) { this.validPeriod = validPeriod; }
    public String getUpdateCycle() { return updateCycle; }
    public void setUpdateCycle(String updateCycle) { this.updateCycle = updateCycle; }
    public String getCreateWay() { return createWay; }
    public void setCreateWay(String createWay) { this.createWay = createWay; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Integer getVersion() { return version; }
    public void setVersion(Integer version) { this.version = version; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("tagId", getTagId())
            .append("libraryId", getLibraryId())
            .append("dirId", getDirId())
            .append("fieldName", getFieldName())
            .append("tagName", getTagName())
            .append("dataType", getDataType())
            .append("tagType", getTagType())
            .append("status", getStatus())
            .append("version", getVersion())
            .toString();
    }
}
