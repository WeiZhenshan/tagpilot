package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;
import java.util.List;

/**
 * 批量保存映射草稿请求
 *
 * @author ruoyi
 */
public class DraftSaveRequest implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 草稿行列表 */
    private List<MetadataChangeDTO> items;

    public List<MetadataChangeDTO> getItems() { return items; }
    public void setItems(List<MetadataChangeDTO> items) { this.items = items; }
}
