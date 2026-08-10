package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;

/**
 * 元数据变更草稿行（批量映射保存用，仅允许五个可改字段）
 *
 * @author ruoyi
 */
public class MetadataChangeDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 标签ID */
    private Long tagId;

    /** 标签中文名 */
    private String tagName;

    /** 标签类型（字典 tag_type） */
    private String tagType;

    /** 所属目录ID */
    private Long dirId;

    /** 技术口径 */
    private String techCaliber;

    /** 业务口径 */
    private String businessCaliber;

    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
    public String getTagType() { return tagType; }
    public void setTagType(String tagType) { this.tagType = tagType; }
    public Long getDirId() { return dirId; }
    public void setDirId(Long dirId) { this.dirId = dirId; }
    public String getTechCaliber() { return techCaliber; }
    public void setTechCaliber(String techCaliber) { this.techCaliber = techCaliber; }
    public String getBusinessCaliber() { return businessCaliber; }
    public void setBusinessCaliber(String businessCaliber) { this.businessCaliber = businessCaliber; }
}
