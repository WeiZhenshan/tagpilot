package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 标签库默认码表关系对象 tl_tag_library_dimension
 * 全部记录共同构成标签库的默认码表集合
 *
 * @author ruoyi
 */
public class TlTagLibraryDimension extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 关系ID */
    private Long relationId;

    /** 标签库ID */
    private Long libraryId;

    /** 维表ID（dp_dimension_table.dimension_id） */
    private Long dimensionId;

    /** 显示顺序 */
    private Integer orderNum;

    public Long getRelationId() { return relationId; }
    public void setRelationId(Long relationId) { this.relationId = relationId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public Long getDimensionId() { return dimensionId; }
    public void setDimensionId(Long dimensionId) { this.dimensionId = dimensionId; }
    public Integer getOrderNum() { return orderNum; }
    public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("relationId", getRelationId())
            .append("libraryId", getLibraryId())
            .append("dimensionId", getDimensionId())
            .append("orderNum", getOrderNum())
            .toString();
    }
}
