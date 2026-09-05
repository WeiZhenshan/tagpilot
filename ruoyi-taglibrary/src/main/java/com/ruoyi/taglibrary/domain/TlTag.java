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

    /** 状态（0草稿 1待审批 2已上线 3已下线 4待完善） */
    private String status;

    /** 版本号 */
    private Integer version;

    /** 来源数据集版本ID（最近一次同步解析的版本） */
    private Long sourceVersionId;

    /** 来源字段快照JSON */
    private String sourceSnapshot;

    /** 来源指纹（最近同步观察值） */
    private String sourceFingerprint;

    /** 已确认来源指纹（元数据审核通过时写入） */
    private String confirmedFingerprint;

    /** 来源状态（AVAILABLE当前版本可用 MISSING来源缺失 CHANGED来源变更待确认） */
    private String sourceStatus;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    /** 关键字（列表过滤用，匹配标签名/字段名，非表列） */
    private String keyword;

    /** 是否排除待完善标签（标签管理查询用，批量映射不过滤，非表列） */
    private Boolean excludeIncomplete;

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
    public Long getSourceVersionId() { return sourceVersionId; }
    public void setSourceVersionId(Long sourceVersionId) { this.sourceVersionId = sourceVersionId; }
    public String getSourceSnapshot() { return sourceSnapshot; }
    public void setSourceSnapshot(String sourceSnapshot) { this.sourceSnapshot = sourceSnapshot; }
    public String getSourceFingerprint() { return sourceFingerprint; }
    public void setSourceFingerprint(String sourceFingerprint) { this.sourceFingerprint = sourceFingerprint; }
    public String getConfirmedFingerprint() { return confirmedFingerprint; }
    public void setConfirmedFingerprint(String confirmedFingerprint) { this.confirmedFingerprint = confirmedFingerprint; }
    public String getSourceStatus() { return sourceStatus; }
    public void setSourceStatus(String sourceStatus) { this.sourceStatus = sourceStatus; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }
    public String getKeyword() { return keyword; }
    public void setKeyword(String keyword) { this.keyword = keyword; }
    public Boolean getExcludeIncomplete() { return excludeIncomplete; }
    public void setExcludeIncomplete(Boolean excludeIncomplete) { this.excludeIncomplete = excludeIncomplete; }

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
