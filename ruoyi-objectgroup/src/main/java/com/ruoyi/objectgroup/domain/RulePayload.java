package com.ruoyi.objectgroup.domain;

import java.util.List;

/**
 * 规则载荷（rule_json 的反序列化对象）
 */
public class RulePayload {

    /** 规则结构版本 */
    private Integer schemaVersion;

    /** 客户号字段名（别名） */
    private String objectKeyField;

    /** 规则保存/生成时的数据集版本ID（运行期用于版本漂移告警） */
    private Long datasetVersionId;

    /** 条件行 */
    private List<Condition> conditions;

    /** 预览列（样例预览拖入的标签列） */
    private List<PreviewColumn> previewColumns;

    public static class Condition {
        private String conditionId;
        private String connector;      // AND / OR
        private Integer openParen;     // 前置括号数
        private Integer closeParen;    // 后置括号数
        private Long tagId;
        private String fieldName;      // 别名
        private String tagName;
        private String tagType;        // 布尔型/选项型/数值型/文本型/日期型/客户号
        private String dataType;       // 源字段数据类型
        private String operator;       // = in between like >= <=
        private List<String> values;
        private String matchType;      // 客户号：exact / like / import
        private String importBatchNo;  // 客户号导入批次
        private Long importedCount;    // 导入条数
        private List<CodeOptionSnapshot> selectedCodeOptions; // schemaVersion 2：已选码值的中文快照（仅展示用，SQL 仍用 values）

        public String getConditionId() { return conditionId; }
        public void setConditionId(String conditionId) { this.conditionId = conditionId; }
        public String getConnector() { return connector; }
        public void setConnector(String connector) { this.connector = connector; }
        public Integer getOpenParen() { return openParen; }
        public void setOpenParen(Integer openParen) { this.openParen = openParen; }
        public Integer getCloseParen() { return closeParen; }
        public void setCloseParen(Integer closeParen) { this.closeParen = closeParen; }
        public Long getTagId() { return tagId; }
        public void setTagId(Long tagId) { this.tagId = tagId; }
        public String getFieldName() { return fieldName; }
        public void setFieldName(String fieldName) { this.fieldName = fieldName; }
        public String getTagName() { return tagName; }
        public void setTagName(String tagName) { this.tagName = tagName; }
        public String getTagType() { return tagType; }
        public void setTagType(String tagType) { this.tagType = tagType; }
        public String getDataType() { return dataType; }
        public void setDataType(String dataType) { this.dataType = dataType; }
        public String getOperator() { return operator; }
        public void setOperator(String operator) { this.operator = operator; }
        public List<String> getValues() { return values; }
        public void setValues(List<String> values) { this.values = values; }
        public String getMatchType() { return matchType; }
        public void setMatchType(String matchType) { this.matchType = matchType; }
        public String getImportBatchNo() { return importBatchNo; }
        public void setImportBatchNo(String importBatchNo) { this.importBatchNo = importBatchNo; }
        public Long getImportedCount() { return importedCount; }
        public void setImportedCount(Long importedCount) { this.importedCount = importedCount; }
        public List<CodeOptionSnapshot> getSelectedCodeOptions() { return selectedCodeOptions; }
        public void setSelectedCodeOptions(List<CodeOptionSnapshot> selectedCodeOptions) { this.selectedCodeOptions = selectedCodeOptions; }
    }

    /** 已选码值快照（schemaVersion 2，rule_json 中保留中文标签用于回显） */
    public static class CodeOptionSnapshot {
        private String code;   // 真实码值
        private String label;  // 码值中文定义快照

        public String getCode() { return code; }
        public void setCode(String code) { this.code = code; }
        public String getLabel() { return label; }
        public void setLabel(String label) { this.label = label; }
    }

    public static class PreviewColumn {
        private Long tagId;
        private String fieldName;
        private String tagName;
        private String dataType;

        public Long getTagId() { return tagId; }
        public void setTagId(Long tagId) { this.tagId = tagId; }
        public String getFieldName() { return fieldName; }
        public void setFieldName(String fieldName) { this.fieldName = fieldName; }
        public String getTagName() { return tagName; }
        public void setTagName(String tagName) { this.tagName = tagName; }
        public String getDataType() { return dataType; }
        public void setDataType(String dataType) { this.dataType = dataType; }
    }

    public Integer getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(Integer schemaVersion) { this.schemaVersion = schemaVersion; }
    public String getObjectKeyField() { return objectKeyField; }
    public void setObjectKeyField(String objectKeyField) { this.objectKeyField = objectKeyField; }
    public Long getDatasetVersionId() { return datasetVersionId; }
    public void setDatasetVersionId(Long datasetVersionId) { this.datasetVersionId = datasetVersionId; }
    public List<Condition> getConditions() { return conditions; }
    public void setConditions(List<Condition> conditions) { this.conditions = conditions; }
    public List<PreviewColumn> getPreviewColumns() { return previewColumns; }
    public void setPreviewColumns(List<PreviewColumn> previewColumns) { this.previewColumns = previewColumns; }
}
