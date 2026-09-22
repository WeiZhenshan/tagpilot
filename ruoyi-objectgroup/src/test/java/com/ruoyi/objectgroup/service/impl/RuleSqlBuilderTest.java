package com.ruoyi.objectgroup.service.impl;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

import java.util.Arrays;
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
 * RuleSqlBuilder 单元测试：客户号导入条件必须生成临时表 join 而非巨型 IN；
 * 在线版本由调用方解析后传入，预览列失效不得静默跳过
 */
@ExtendWith(MockitoExtension.class)
class RuleSqlBuilderTest {

    private static final Long VERSION_ID = 10L;
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

    private void mockVersion() {
        when(extMapper.selectVersionDefinitionJson(VERSION_ID)).thenReturn("{\"tableId\":5}");
        when(extMapper.selectTableObjectName(5L)).thenReturn("wide_tbl");
        when(extMapper.selectColumnNameByAlias(VERSION_ID, "cust")).thenReturn("cust_no");
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
        mockVersion();

        String sql = builder.buildSql(VERSION_ID, importRule(BATCH), IRuleSqlBuilder.MODE_COUNT);

        assertTrue(sql.startsWith("select count(*) from `wide_tbl`"), sql);
        assertTrue(sql.contains("where `cust_no` in (select `v` from `tmp_og_imp_" + BATCH + "`)"), sql);
        assertTrue(sql.length() < 500, "导入 SQL 不得随批次膨胀，实际长度：" + sql.length());
    }

    @Test
    void 非法批次号拒绝生成SQL() {
        mockVersion();

        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(VERSION_ID, importRule("x'; drop table t; --"), IRuleSqlBuilder.MODE_COUNT));
        assertTrue(e.getMessage().contains("不合法"), e.getMessage());
    }

    @Test
    void 缺失批次号拒绝生成SQL() {
        mockVersion();

        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(VERSION_ID, importRule(null), IRuleSqlBuilder.MODE_COUNT));
        assertTrue(e.getMessage().contains("批次缺失"), e.getMessage());
    }

    @Test
    void 版本为空拒绝生成SQL() {
        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(null, importRule(BATCH), IRuleSqlBuilder.MODE_COUNT));
        assertTrue(e.getMessage().contains("未上线"), e.getMessage());
    }

    @Test
    void 失效预览列报错而非静默跳过() {
        mockVersion();
        when(extMapper.selectColumnNameByAlias(VERSION_ID, "sex")).thenReturn(null);
        RulePayload rule = importRule(BATCH);
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        rule.setPreviewColumns(Collections.singletonList(pc));

        ServiceException e = assertThrows(ServiceException.class,
                () -> builder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT));
        assertTrue(e.getMessage().contains("性别"), e.getMessage());
        assertTrue(e.getMessage().contains("未在数据集中启用"), e.getMessage());
    }

    @Test
    void 预览列与客户号同列时跳过且正常出列() {
        mockVersion();
        when(extMapper.selectColumnNameByAlias(VERSION_ID, "sex")).thenReturn("sex_code");
        RulePayload rule = importRule(BATCH);
        RulePayload.PreviewColumn same = new RulePayload.PreviewColumn();
        same.setFieldName("cust");
        same.setTagName("客户号");
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        rule.setPreviewColumns(Arrays.asList(same, pc));

        String sql = builder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT);

        assertTrue(sql.startsWith("select `cust_no`, `sex_code` as `性别` from `wide_tbl`"), sql);
        assertTrue(sql.endsWith("limit 100"), sql);
    }
    @Test
    void V3严格比较不退化为闭区间且旧规则保持原语义() {
        mockVersion();
        RulePayload rule=importRule(BATCH);
        RulePayload.Condition c=rule.getConditions().get(0);
        c.setMatchType(null); c.setTagType("数值型");c.setOperator(">");c.setValues(Collections.singletonList("500000"));
        rule.setSchemaVersion(3);
        String sql=builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT);
        assertTrue(sql.contains(" > 500000"),sql);
        rule.setSchemaVersion(2);
        assertTrue(builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT).contains(" >= 500000"));
    }
    @Test
    void V3排除集合与空值显式处理() {
        mockVersion();RulePayload rule=importRule(BATCH);rule.setSchemaVersion(3);
        RulePayload.Condition c=rule.getConditions().get(0);c.setMatchType(null);c.setTagType("选项型");c.setOperator("not_in");c.setValues(Arrays.asList("closed","unknown"));
        assertTrue(builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT).contains("not in ('closed','unknown')"));
        c.setOperator("is_null");c.setValues(Collections.emptyList());
        assertTrue(builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT).contains("is null"));
    }
    @Test
    void V3拒绝非法操作符与反向区间() {
        mockVersion();RulePayload rule=importRule(BATCH);rule.setSchemaVersion(3);
        RulePayload.Condition c=rule.getConditions().get(0);c.setMatchType(null);c.setTagType("数值型");c.setOperator("between");c.setValues(Arrays.asList("10","1"));
        assertThrows(ServiceException.class,()->builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT));
        c.setOperator("or 1=1");c.setValues(Collections.singletonList("1"));
        assertThrows(ServiceException.class,()->builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT));
    }
    @Test
    void V3文本中的反斜线和单引号不能逃逸字面量() {
        mockVersion();RulePayload rule=importRule(BATCH);rule.setSchemaVersion(3);
        RulePayload.Condition c=rule.getConditions().get(0);c.setMatchType(null);c.setTagType("文本型");c.setOperator("=");
        c.setValues(Collections.singletonList("\\' OR 1=1 --"));
        String sql=builder.buildSql(VERSION_ID,rule,IRuleSqlBuilder.MODE_COUNT);
        assertTrue(sql.contains("= '\\\\'' OR 1=1 --'"),sql);
    }

}
