package com.ruoyi.databroker.domain.dto;

import java.util.List;

/**
 * 保存草稿请求体：{versionId, versionName, tableId, fields[]}
 * fields 元素结构与 definition_json 中一致：{columnId, alias, dataType, enabled, orderNum}
 */
public class SaveDraftRequest {
    private Long versionId;
    private String versionName;
    private Long tableId;
    private List<FieldItem> fields;

    public Long getVersionId() { return versionId; }
    public void setVersionId(Long versionId) { this.versionId = versionId; }
    public String getVersionName() { return versionName; }
    public void setVersionName(String versionName) { this.versionName = versionName; }
    public Long getTableId() { return tableId; }
    public void setTableId(Long tableId) { this.tableId = tableId; }
    public List<FieldItem> getFields() { return fields; }
    public void setFields(List<FieldItem> fields) { this.fields = fields; }

    public static class FieldItem {
        private Long columnId;
        private String alias;
        private String dataType;
        private Boolean enabled;
        private Integer orderNum;

        public Long getColumnId() { return columnId; }
        public void setColumnId(Long columnId) { this.columnId = columnId; }
        public String getAlias() { return alias; }
        public void setAlias(String alias) { this.alias = alias; }
        public String getDataType() { return dataType; }
        public void setDataType(String dataType) { this.dataType = dataType; }
        public Boolean getEnabled() { return enabled; }
        public void setEnabled(Boolean enabled) { this.enabled = enabled; }
        public Integer getOrderNum() { return orderNum; }
        public void setOrderNum(Integer orderNum) { this.orderNum = orderNum; }
    }
}
