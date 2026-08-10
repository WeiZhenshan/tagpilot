package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;

/**
 * 引用了某维表的标签库（维表详情抽屉"已关联标签库"用）
 *
 * @author ruoyi
 */
public class DimensionLibraryVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 标签库ID */
    private Long libraryId;

    /** 标签库名称 */
    private String libraryName;

    /** 状态（0草稿 1待审批 2已上线 3已下线） */
    private String status;

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getLibraryName() { return libraryName; }
    public void setLibraryName(String libraryName) { this.libraryName = libraryName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
