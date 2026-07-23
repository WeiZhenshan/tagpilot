package com.ruoyi.databroker.domain.vo;

import java.util.List;
import java.util.Map;

/**
 * 数据预览结果：{columns:[{name,dataType}], rows:[{alias:value}]}
 */
public class PreviewResultVO {
    private List<PreviewColumn> columns;
    private List<Map<String, Object>> rows;

    public List<PreviewColumn> getColumns() { return columns; }
    public void setColumns(List<PreviewColumn> columns) { this.columns = columns; }
    public List<Map<String, Object>> getRows() { return rows; }
    public void setRows(List<Map<String, Object>> rows) { this.rows = rows; }

    public static class PreviewColumn {
        private String name;
        private String dataType;

        public PreviewColumn() {
        }

        public PreviewColumn(String name, String dataType) {
            this.name = name;
            this.dataType = dataType;
        }

        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
        public String getDataType() { return dataType; }
        public void setDataType(String dataType) { this.dataType = dataType; }
    }
}
