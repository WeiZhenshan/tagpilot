package com.ruoyi.objectgroup.service.impl;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

import java.util.Collections;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;

/**
 * RuleSqlBuilder 单元测试：客户号导入条件必须生成临时表 join 而非巨型 IN
 */
@ExtendWith(MockitoExtension.class)
class RuleSqlBuilderTest {

    private static final Long LIBRARY_ID = 3L;
    private static final String BATCH = "0123456789abcdef0123456789abcdef";

    @Mock
    private TlObjectGroupExtMapper extMapper;

    private RuleSqlBuilder builder;

    @BeforeEach
    void setUp() {
        builder = new RuleSqlBuilder();
        ReflectionTestUtils.setField(builder, "extMapper", extMapper);
        ReflectionTestUtils.setField(builder, "objectMapper", new ObjectMapper());
    }

    private void mockOnlineVersion() {
        when(extMapper.selectOnlineVersionId(LIBRARY_ID)).thenReturn(10L);
        when(extMapper.selectVersionDefinitionJson(10L)).thenReturn("{\"tableId\":5}");
        when(extMapper.selectTableObjectName(5L)).thenReturn("wide_tbl");
        when(extMapper.selectColumnNameByAlias(10L, "cust")).thenReturn("cust_no");
    }

    private RulePayload importRule(String batchNo) {
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        RulePayload.Condition c = new RulePayload.Condition();
        c.setFieldName("cust");
        c.setTagType("客户号");
        c.setMatchType("import");
        c.setImportBatchNo(batchNo);
        rule.setConditions(Collections.singletonList(c));
        return rule;
    }

    @Test
    void 导入条件生成临时表子查询且SQL保持短小() {
        mockOnlineVersion();

        String sql = builder.buildSql(LIBRARY_ID, importRule(BATCH), IRuleSqlBuilder.MODE_COUNT);

        assertTrue(sql.startsWith("select count(*) from `wide_tbl`"), sql);
        assertTrue(sql.contains("where `cust_no` in (select `v` from `tmp_og_imp_" + BATCH + "`)"), sql);
        assertTrue(sql.length() < 500, "导入 SQL 不得随批次膨胀，实际长度：" + sql.length());
    }

    @Test
    void 非法批次号拒绝生成SQL() {
        mockOnlineVersion();

        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(LIBRARY_ID, importRule("x'; drop table t; --"), IRuleSqlBuilder.MODE_COUNT));
        assertTrue(e.getMessage().contains("不合法"), e.getMessage());
    }

    @Test
    void 缺失批次号拒绝生成SQL() {
        mockOnlineVersion();

        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(LIBRARY_ID, importRule(null), IRuleSqlBuilder.MODE_COUNT));
        assertTrue(e.getMessage().contains("批次缺失"), e.getMessage());
    }
}
