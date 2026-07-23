package com.ruoyi.databroker.domain.dto;

/**
 * 发布版本请求体：{versionName, releaseNote, setDefault}
 */
public class PublishRequest {
    private String versionName;
    private String releaseNote;
    private Boolean setDefault;

    public String getVersionName() { return versionName; }
    public void setVersionName(String versionName) { this.versionName = versionName; }
    public String getReleaseNote() { return releaseNote; }
    public void setReleaseNote(String releaseNote) { this.releaseNote = releaseNote; }
    public Boolean getSetDefault() { return setDefault; }
    public void setSetDefault(Boolean setDefault) { this.setDefault = setDefault; }
}
