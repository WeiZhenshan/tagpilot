package com.ruoyi.taglibrary.domain.dto;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 语义冻结导出结果
 */
public class BootstrapExportResult {
    private Long libraryId;
    private String jsonl;
    private String contentHash;
    private int tagCount;
    private int codeValueCount;
    private int domainCount;
    private List<Map<String, Object>> issues = new ArrayList<Map<String, Object>>();

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getJsonl() { return jsonl; }
    public void setJsonl(String jsonl) { this.jsonl = jsonl; }
    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }
    public int getTagCount() { return tagCount; }
    public void setTagCount(int tagCount) { this.tagCount = tagCount; }
    public int getCodeValueCount() { return codeValueCount; }
    public void setCodeValueCount(int codeValueCount) { this.codeValueCount = codeValueCount; }
    public int getDomainCount() { return domainCount; }
    public void setDomainCount(int domainCount) { this.domainCount = domainCount; }
    public List<Map<String, Object>> getIssues() { return issues; }
    public void setIssues(List<Map<String, Object>> issues) { this.issues = issues; }
}
