package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

public class TsCatalogSnapshot extends BaseEntity {
    private static final long serialVersionUID = 1L;
    private String snapshotId;
    private Long libraryId;
    private Integer snapshotNo;
    private Integer tagCount;
    private Integer conceptCount;
    private Integer aliasCount;
    private Integer codeValueCount;
    private String contentHash;
    private String fileSha256;
    public String getFileSha256() { return fileSha256; }
    public void setFileSha256(String value) { fileSha256 = value; }
    private String storageUri;
    private String schemaVersion;
    private String status;
    private String sourceManifest;
    private String qualityReport;
    private String publishBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date publishTime;
    private String jsonl;

    public String getSnapshotId() { return snapshotId; }
    public void setSnapshotId(String snapshotId) { this.snapshotId = snapshotId; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public Integer getSnapshotNo() { return snapshotNo; }
    public void setSnapshotNo(Integer snapshotNo) { this.snapshotNo = snapshotNo; }
    public Integer getTagCount() { return tagCount; }
    public void setTagCount(Integer tagCount) { this.tagCount = tagCount; }
    public Integer getConceptCount() { return conceptCount; }
    public void setConceptCount(Integer conceptCount) { this.conceptCount = conceptCount; }
    public Integer getAliasCount() { return aliasCount; }
    public void setAliasCount(Integer aliasCount) { this.aliasCount = aliasCount; }
    public Integer getCodeValueCount() { return codeValueCount; }
    public void setCodeValueCount(Integer codeValueCount) { this.codeValueCount = codeValueCount; }
    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }
    public String getStorageUri() { return storageUri; }
    public void setStorageUri(String storageUri) { this.storageUri = storageUri; }
    public String getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(String schemaVersion) { this.schemaVersion = schemaVersion; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getSourceManifest() { return sourceManifest; }
    public void setSourceManifest(String sourceManifest) { this.sourceManifest = sourceManifest; }
    public String getQualityReport() { return qualityReport; }
    public void setQualityReport(String qualityReport) { this.qualityReport = qualityReport; }
    public String getPublishBy() { return publishBy; }
    public void setPublishBy(String publishBy) { this.publishBy = publishBy; }
    public Date getPublishTime() { return publishTime; }
    public void setPublishTime(Date publishTime) { this.publishTime = publishTime; }
    public String getJsonl() { return jsonl; }
    public void setJsonl(String jsonl) { this.jsonl = jsonl; }
}
