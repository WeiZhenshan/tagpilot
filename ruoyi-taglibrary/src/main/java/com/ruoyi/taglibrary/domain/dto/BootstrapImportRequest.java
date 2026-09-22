package com.ruoyi.taglibrary.domain.dto;

/**
 * rule_init 草稿导入请求
 */
public class BootstrapImportRequest {
    private Long libraryId;
    /** rule_init_result.jsonl 全文 */
    private String jsonl;

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getJsonl() { return jsonl; }
    public void setJsonl(String jsonl) { this.jsonl = jsonl; }
}
