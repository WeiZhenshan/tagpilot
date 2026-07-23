package com.ruoyi.taglibrary.domain.dto;

import java.io.Serializable;

/**
 * 批量移动目录请求
 *
 * @author ruoyi
 */
public class MoveRequest implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 批量标签ID */
    private Long[] tagIds;

    /** 目标目录ID */
    private Long dirId;

    public Long[] getTagIds() { return tagIds; }
    public void setTagIds(Long[] tagIds) { this.tagIds = tagIds; }
    public Long getDirId() { return dirId; }
    public void setDirId(Long dirId) { this.dirId = dirId; }
}
