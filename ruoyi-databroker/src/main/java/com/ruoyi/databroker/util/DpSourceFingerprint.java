package com.ruoyi.databroker.util;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.common.utils.sign.Md5Utils;
import com.ruoyi.databroker.domain.vo.DpResolvedField;

/**
 * 来源指纹与快照工具。
 * 指纹由 数据源ID|物理表名|物理列名|数据类型|主键标记 拼接取 MD5（32位小写hex），
 * 刻意使用物理表名/列名而非元数据ID，避免元数据重采导致误判来源变更。
 *
 * @author ruoyi
 */
public final class DpSourceFingerprint {

    private DpSourceFingerprint() {
    }

    /** 计算来源指纹（32位小写hex），各分量做去空白/小写归一，空值按空串处理 */
    public static String of(Long datasourceId, String tableName, String columnName, String dataType, String isPk) {
        String raw = String.join("|",
                datasourceId == null ? "" : datasourceId.toString(),
                norm(tableName), norm(columnName), norm(dataType), normPk(isPk));
        return Md5Utils.hash(raw);
    }

    /**
     * 组装来源快照JSON，字段约定：
     * datasourceId、tableId、tableName、columnId、columnName、dataType、isPk、fieldAlias
     */
    public static String buildSnapshot(DpResolvedField field) {
        JSONObject snapshot = new JSONObject();
        snapshot.put("datasourceId", field.getDatasourceId());
        snapshot.put("tableId", field.getSourceTableId());
        snapshot.put("tableName", field.getTableName());
        snapshot.put("columnId", field.getSourceColumnId());
        snapshot.put("columnName", field.getFieldName());
        snapshot.put("dataType", field.getDataType());
        snapshot.put("isPk", normPk(field.getIsPk()));
        snapshot.put("fieldAlias", field.getFieldAlias());
        return snapshot.toJSONString();
    }

    /** 解析来源快照JSON，空串/非法JSON 返回 null */
    public static JSONObject parseSnapshot(String snapshot) {
        if (StringUtils.isEmpty(snapshot)) {
            return null;
        }
        try {
            return JSON.parseObject(snapshot);
        } catch (Exception e) {
            return null;
        }
    }

    private static String norm(String s) {
        return s == null ? "" : s.trim().toLowerCase();
    }

    private static String normPk(String isPk) {
        return "1".equals(isPk) ? "1" : "0";
    }
}
