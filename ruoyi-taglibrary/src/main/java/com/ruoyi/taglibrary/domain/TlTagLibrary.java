package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签库对象 tl_tag_library
 *
 * @author ruoyi
 */
public class TlTagLibrary extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 标签库ID */
    private Long libraryId;

    /** 标签库名称 */
    private String libraryName;

    /** 标签库编码 */
    private String libraryCode;

    /** 分类（字典 tag_library_category） */
    private String category;

    /** 标签对象（字典 tag_object） */
    private String tagObject;

    /** 关联数据集ID */
    private Long datasetId;

    /** 负责人 */
    private String ownerName;

    /** 状态（0草稿 1待审批 2已上线 3已下线） */
    private String status;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    /** 标签总数（非表字段，list联表统计回填） */
    private Long tagCount;

    /** 已上线标签数（非表字段，list联表统计回填） */
    private Long onlineCount;

    /** 已下线标签数（非表字段，list联表统计回填） */
    private Long offlineCount;

    /** 待处理标签数（非表字段，list联表统计回填） */
    private Long pendingCount;

    /** 关联数据集名称（非表字段，联表回填） */
    private String datasetName;

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getLibraryName() { return libraryName; }
    public void setLibraryName(String libraryName) { this.libraryName = libraryName; }
    public String getLibraryCode() { return libraryCode; }
    public void setLibraryCode(String libraryCode) { this.libraryCode = libraryCode; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }
    public String getTagObject() { return tagObject; }
    public void setTagObject(String tagObject) { this.tagObject = tagObject; }
    public Long getDatasetId() { return datasetId; }
    public void setDatasetId(Long datasetId) { this.datasetId = datasetId; }
    public String getOwnerName() { return ownerName; }
    public void setOwnerName(String ownerName) { this.ownerName = ownerName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }
    public Long getTagCount() { return tagCount; }
    public void setTagCount(Long tagCount) { this.tagCount = tagCount; }
    public Long getOnlineCount() { return onlineCount; }
    public void setOnlineCount(Long onlineCount) { this.onlineCount = onlineCount; }
    public Long getOfflineCount() { return offlineCount; }
    public void setOfflineCount(Long offlineCount) { this.offlineCount = offlineCount; }
    public Long getPendingCount() { return pendingCount; }
    public void setPendingCount(Long pendingCount) { this.pendingCount = pendingCount; }
    public String getDatasetName() { return datasetName; }
    public void setDatasetName(String datasetName) { this.datasetName = datasetName; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("libraryId", getLibraryId())
            .append("libraryName", getLibraryName())
            .append("libraryCode", getLibraryCode())
            .append("category", getCategory())
            .append("tagObject", getTagObject())
            .append("datasetId", getDatasetId())
            .append("ownerName", getOwnerName())
            .append("status", getStatus())
            .toString();
    }
}
