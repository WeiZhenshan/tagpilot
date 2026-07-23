package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签目录对象 tl_tag_dir
 *
 * @author ruoyi
 */
public class TlTagDir extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 目录ID */
    private Long dirId;

    /** 所属标签库ID */
    private Long libraryId;

    /** 父目录ID */
    private Long parentId;

    /** 目录名称 */
    private String dirName;

    /** 显示顺序 */
    private Integer orderNum;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    public Long getDirId() { return dirId; }
    public void setDirId(Long dirId) { this.dirId = dirId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public Long getParentId() { return parentId; }
    public void setParentId(Long parentId) { this.parentId = parentId; }
    public String getDirName() { return dirName; }
    public void setDirName(String dirName) { this.dirName = dirName; }
    public Integer getOrderNum() { return orderNum; }
    public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("dirId", getDirId())
            .append("libraryId", getLibraryId())
            .append("parentId", getParentId())
            .append("dirName", getDirName())
            .append("orderNum", getOrderNum())
            .toString();
    }
}
