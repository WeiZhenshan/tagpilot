package com.ruoyi.taglibrary.domain.dto;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * rule_init 草稿导入结果
 */
public class BootstrapImportResult {
    private Long libraryId;
    private int importedTagCount;
    private int importedCodeCount;
    private int importedConceptCount;
    private int skippedReviewedCount;
    private List<Map<String, Object>> rejected = new ArrayList<Map<String, Object>>();

    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public int getImportedTagCount() { return importedTagCount; }
    public void setImportedTagCount(int importedTagCount) { this.importedTagCount = importedTagCount; }
    public int getImportedCodeCount() { return importedCodeCount; }
    public void setImportedCodeCount(int importedCodeCount) { this.importedCodeCount = importedCodeCount; }
    public int getImportedConceptCount() { return importedConceptCount; }
    public void setImportedConceptCount(int importedConceptCount) { this.importedConceptCount = importedConceptCount; }
    public int getSkippedReviewedCount() { return skippedReviewedCount; }
    public void setSkippedReviewedCount(int skippedReviewedCount) { this.skippedReviewedCount = skippedReviewedCount; }
    public List<Map<String, Object>> getRejected() { return rejected; }
    public void setRejected(List<Map<String, Object>> rejected) { this.rejected = rejected; }
}
