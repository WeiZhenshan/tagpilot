package com.ruoyi.databroker.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.alibaba.fastjson2.JSONObject;
import org.junit.jupiter.api.Test;
import com.ruoyi.databroker.domain.vo.DpResolvedField;

/**
 * 来源指纹工具单元测试：指纹对物理表/列/类型/主键敏感，对元数据ID不敏感
 *
 * @author ruoyi
 */
public class DpSourceFingerprintTest {

    private static final String BASE = DpSourceFingerprint.of(101L, "indiv_cust", "cust_no", "varchar(32)", "1");

    @Test
    public void 指纹_32位小写hex() {
        assertEquals(32, BASE.length());
        assertTrue(BASE.matches("[0-9a-f]{32}"));
    }

    @Test
    public void 指纹_表名变化_不同() {
        assertNotEquals(BASE, DpSourceFingerprint.of(101L, "indiv_cust_v2", "cust_no", "varchar(32)", "1"));
    }

    @Test
    public void 指纹_列名变化_不同() {
        assertNotEquals(BASE, DpSourceFingerprint.of(101L, "indiv_cust", "cust_id", "varchar(32)", "1"));
    }

    @Test
    public void 指纹_数据类型变化_不同() {
        assertNotEquals(BASE, DpSourceFingerprint.of(101L, "indiv_cust", "cust_no", "varchar(64)", "1"));
    }

    @Test
    public void 指纹_主键标记变化_不同() {
        assertNotEquals(BASE, DpSourceFingerprint.of(101L, "indiv_cust", "cust_no", "varchar(32)", "0"));
    }

    @Test
    public void 指纹_数据源变化_不同() {
        assertNotEquals(BASE, DpSourceFingerprint.of(102L, "indiv_cust", "cust_no", "varchar(32)", "1"));
    }

    /** 大小写与首尾空白归一后指纹一致；isPk 仅 '1' 视为主键 */
    @Test
    public void 指纹_归一化_稳定() {
        assertEquals(BASE, DpSourceFingerprint.of(101L, " INDIV_CUST ", "CUST_NO", "VARCHAR(32)", "1"));
        assertNotEquals(BASE, DpSourceFingerprint.of(101L, "indiv_cust", "cust_no", "varchar(32)", null));
    }

    /** 指纹只取物理表名/列名等物理信息，元数据ID变化不影响（由 of 的签名保证，这里验证快照携带ID但指纹不消费它） */
    @Test
    public void 快照_携带元数据ID_但指纹与ID无关() {
        DpResolvedField field = buildField();
        String snapshot = DpSourceFingerprint.buildSnapshot(field);
        String fingerprint = DpSourceFingerprint.of(field.getDatasourceId(), field.getTableName(),
                field.getFieldName(), field.getDataType(), field.getIsPk());

        field.setSourceTableId(999L);
        field.setSourceColumnId(888L);
        String fingerprintAfterRescan = DpSourceFingerprint.of(field.getDatasourceId(), field.getTableName(),
                field.getFieldName(), field.getDataType(), field.getIsPk());

        assertEquals(fingerprint, fingerprintAfterRescan);
        JSONObject parsed = DpSourceFingerprint.parseSnapshot(snapshot);
        assertEquals(Long.valueOf(10L), parsed.getLong("tableId"));
        assertEquals(Long.valueOf(20L), parsed.getLong("columnId"));
    }

    @Test
    public void 快照_组装解析往返一致() {
        String snapshot = DpSourceFingerprint.buildSnapshot(buildField());

        JSONObject parsed = DpSourceFingerprint.parseSnapshot(snapshot);
        assertEquals(Long.valueOf(101L), parsed.getLong("datasourceId"));
        assertEquals("indiv_cust", parsed.getString("tableName"));
        assertEquals("cust_no", parsed.getString("columnName"));
        assertEquals("varchar(32)", parsed.getString("dataType"));
        assertEquals("1", parsed.getString("isPk"));
        assertEquals("cust_no", parsed.getString("fieldAlias"));
    }

    @Test
    public void 快照_空或非法JSON_解析返回null() {
        assertNull(DpSourceFingerprint.parseSnapshot(null));
        assertNull(DpSourceFingerprint.parseSnapshot(""));
        assertNull(DpSourceFingerprint.parseSnapshot("not-json"));
    }

    private DpResolvedField buildField() {
        DpResolvedField field = new DpResolvedField();
        field.setFieldId(1L);
        field.setFieldAlias("cust_no");
        field.setFieldName("cust_no");
        field.setDataType("varchar(32)");
        field.setIsPk("1");
        field.setSourceTableId(10L);
        field.setSourceColumnId(20L);
        field.setTableName("indiv_cust");
        field.setDatasourceId(101L);
        return field;
    }
}
