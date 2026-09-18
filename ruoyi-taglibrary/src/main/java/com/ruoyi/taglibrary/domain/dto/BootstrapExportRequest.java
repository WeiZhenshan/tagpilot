package com.ruoyi.taglibrary.domain.dto;

import java.util.List;

/**
 * 语义冻结导出请求
 */
public class BootstrapExportRequest {
    private Long libraryId;
    private List<Long> tagIds;
    private List<String> fieldNames;

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public List<Long> getTagIds() { return tagIds; }
    public void setTagIds(List<Long> tagIds) { this.tagIds = tagIds; }
    public List<String> getFieldNames() { return fieldNames; }
    public void setFieldNames(List<String> fieldNames) { this.fieldNames = fieldNames; }
}
