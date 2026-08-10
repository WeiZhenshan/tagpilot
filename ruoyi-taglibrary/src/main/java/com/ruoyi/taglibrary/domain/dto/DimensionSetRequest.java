package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;
import java.util.List;

/**
 * 默认码表覆盖保存请求体
 *
 * @author ruoyi
 */
public class DimensionSetRequest implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 维表ID数组（顺序即显示顺序，空数组表示清空） */
    private List<Long> dimensionIds;

    public List<Long> getDimensionIds() { return dimensionIds; }
    public void setDimensionIds(List<Long> dimensionIds) { this.dimensionIds = dimensionIds; }
}
