package com.ruoyi.objectgroup.service.impl;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TagStatusRef;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;

/**
 * RuleTagValidator 单元测试：五入口统一校验（所属库/上线状态/来源可用/版本字段有效性/类型一致）
 * 与保存、运行时的失效编码校验
 */
@ExtendWith(MockitoExtension.class)
class RuleTagValidatorTest {

    private static final Long LIBRARY_ID = 7L;
    private static final Long VERSION_ID = 11L;

    @Mock
    private TlObjectGroupExtMapper extMapper;
    @Mock
    private DpOnlineVersionResolver onlineVersionResolver;
    @Mock
    private IDimensionCodeOptionService dimensionCodeOptionService;

    @InjectMocks
    private RuleTagValidator validator;

    private TagStatusRef tag(String fieldName, String tagName, String tagType, String status, String sourceStatus) {
        TagStatusRef ref = new TagStatusRef();
        ref.setFieldName(fieldName);
        ref.setTagName(tagName);
        ref.setTagType(tagType);
        ref.setDataType("varchar");
        ref.setStatus(status);
        ref.setSourceStatus(sourceStatus);
        return ref;
    }

    private DpResolvedField field(String alias) {
        DpResolvedField f = new DpResolvedField();
        f.setFieldAlias(alias);
        f.setFieldName(alias + "_col");
        f.setDataType("varchar");
        return f;
    }

    private RulePayload.Condition condition(String fieldName, String tagType) {
        RulePayload.Condition c = new RulePayload.Condition();
        c.setFieldName(fieldName);
        c.setTagName("标签" + fieldName);
        c.setTagType(tagType);
        c.setDataType("varchar");
        return c;
    }

    private RulePayload ruleWith(RulePayload.Condition... conditions) {
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Arrays.asList(conditions));
        return rule;
    }

    /** 正常可用标签 + 启用字段（含客户号 cust） */
    private void mockUsable(TagStatusRef... tags) {
        List<TagStatusRef> tagList = Arrays.asList(tags);
        when(extMapper.selectTagRefsByLibrary(LIBRARY_ID)).thenReturn(tagList);
        java.util.List<DpResolvedField> fields = new java.util.ArrayList<>();
        fields.add(field("cust"));
        for (TagStatusRef t : tagList) {
            fields.add(field(t.getFieldName()));
        }
        when(onlineVersionResolver.listEnabledFields(VERSION_ID)).thenReturn(fields);
    }

    @Test
    void 全部标签可用时校验通过() {
        mockUsable(tag("sex", "性别", "选项型", "2", "AVAILABLE"));

        assertDoesNotThrow(() -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
    }

    @Test
    void 标签不属于当前库时报错() {
        mockUsable(); // 库内无 sex 标签，仅有 cust 启用字段

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("不存在"), e.getMessage());
    }

    @Test
    void 待完善标签报错并指明审核原因() {
        mockUsable(tag("sex", "性别", "选项型", "4", "AVAILABLE"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("性别"), e.getMessage());
        assertTrue(e.getMessage().contains("待完善"), e.getMessage());
    }

    @Test
    void 未上线标签报错() {
        mockUsable(tag("sex", "性别", "选项型", "0", "AVAILABLE"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("未上线"), e.getMessage());
    }

    @Test
    void 来源缺失标签报错() {
        mockUsable(tag("sex", "性别", "选项型", "2", "MISSING"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("缺失"), e.getMessage());
    }

    @Test
    void 来源变更待确认标签报错() {
        mockUsable(tag("sex", "性别", "选项型", "2", "CHANGED"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("待确认"), e.getMessage());
    }

    @Test
    void 字段未在当前版本启用时报错() {
        when(extMapper.selectTagRefsByLibrary(LIBRARY_ID))
                .thenReturn(Collections.singletonList(tag("sex", "性别", "选项型", "2", "AVAILABLE")));
        // 启用字段只有客户号，sex 已停用
        when(onlineVersionResolver.listEnabledFields(VERSION_ID))
                .thenReturn(Collections.singletonList(field("cust")));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "选项型"))));
        assertTrue(e.getMessage().contains("未在当前数据集版本中启用"), e.getMessage());
    }

    @Test
    void 规则声明类型与库中实际类型不一致时报错() {
        mockUsable(tag("sex", "性别", "选项型", "2", "AVAILABLE"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(condition("sex", "文本型"))));
        assertTrue(e.getMessage().contains("类型已变更"), e.getMessage());
    }

    @Test
    void 客户号伪类型不参与类型一致性比较() {
        // 前端按 isObjectKey 派生的"客户号"是伪类型，库中 cust_id 实际为数值型，不应误判变更
        mockUsable(tag("cust", "客户号", "数值型", "2", "AVAILABLE"));
        RulePayload.Condition c = condition("cust", "客户号");
        c.setDataType("bigint");
        // bigint 与库中快照 varchar 不一致时仍应报数据类型变更
        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(c)));
        assertTrue(e.getMessage().contains("数据类型已变更"), e.getMessage());
        // dataType 一致时通过
        c.setDataType("varchar");
        assertDoesNotThrow(() -> validator.validateRule(LIBRARY_ID, VERSION_ID, ruleWith(c)));
    }

    @Test
    void 预览列与客户号纳入校验() {
        mockUsable(tag("sex", "性别", "选项型", "2", "AVAILABLE"));
        RulePayload rule = ruleWith();
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        pc.setTagType("选项型");
        rule.setPreviewColumns(Collections.singletonList(pc));

        assertDoesNotThrow(() -> validator.validateRule(LIBRARY_ID, VERSION_ID, rule));
    }

    @Test
    void 失效预览列报错而非静默跳过() {
        when(extMapper.selectTagRefsByLibrary(LIBRARY_ID))
                .thenReturn(Collections.singletonList(tag("sex", "性别", "选项型", "2", "AVAILABLE")));
        when(onlineVersionResolver.listEnabledFields(VERSION_ID))
                .thenReturn(Collections.singletonList(field("cust")));
        RulePayload rule = ruleWith();
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        rule.setPreviewColumns(Collections.singletonList(pc));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, rule));
        assertTrue(e.getMessage().contains("性别"), e.getMessage());
        assertTrue(e.getMessage().contains("未在当前数据集版本中启用"), e.getMessage());
    }

    @Test
    void 客户号字段未启用时报错() {
        when(extMapper.selectTagRefsByLibrary(LIBRARY_ID)).thenReturn(Collections.emptyList());
        when(onlineVersionResolver.listEnabledFields(VERSION_ID))
                .thenReturn(Collections.singletonList(field("sex")));
        RulePayload rule = ruleWith();

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateRule(LIBRARY_ID, VERSION_ID, rule));
        assertTrue(e.getMessage().contains("客户号字段"), e.getMessage());
    }

    // ==================== 失效编码校验（保存/运行） ====================

    private Map<String, Object> option(String code, String def) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("code", code);
        row.put("codeDefinition", def);
        return row;
    }

    @Test
    void 选项型条件码值均在码表中时校验通过() {
        RulePayload.Condition c = condition("sex", "选项型");
        c.setValues(Arrays.asList("1", "2"));
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "sex"))
                .thenReturn(Arrays.asList(option("1", "男"), option("2", "女")));

        assertDoesNotThrow(() -> validator.validateCodeValues(LIBRARY_ID, ruleWith(c)));
    }

    @Test
    void 选项型条件码值失效时报错要求修正() {
        RulePayload.Condition c = condition("sex", "选项型");
        c.setValues(Arrays.asList("1", "9"));
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "sex"))
                .thenReturn(Arrays.asList(option("1", "男"), option("2", "女")));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateCodeValues(LIBRARY_ID, ruleWith(c)));
        assertTrue(e.getMessage().contains("已失效"), e.getMessage());
        assertTrue(e.getMessage().contains("9"), e.getMessage());
    }

    @Test
    void 布尔型条件码值失效时报错() {
        RulePayload.Condition c = condition("active", "布尔型");
        c.setValues(Collections.singletonList("X"));
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "active"))
                .thenReturn(Arrays.asList(option("Y", "是"), option("N", "否")));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateCodeValues(LIBRARY_ID, ruleWith(c)));
        assertTrue(e.getMessage().contains("已失效"), e.getMessage());
    }

    @Test
    void 码表不可达时报无法校验且不回退旧码值表() {
        RulePayload.Condition c = condition("sex", "选项型");
        c.setValues(Collections.singletonList("1"));
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "sex"))
                .thenThrow(new ServiceException("码值选项查询失败：连接超时"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> validator.validateCodeValues(LIBRARY_ID, ruleWith(c)));
        assertTrue(e.getMessage().contains("无法校验"), e.getMessage());
    }

    @Test
    void 非选项类型与空值条件不做码值校验() {
        RulePayload.Condition text = condition("name", "文本型");
        text.setValues(Collections.singletonList("任意值"));
        RulePayload.Condition empty = condition("sex", "选项型");
        empty.setValues(Collections.emptyList());

        assertDoesNotThrow(() -> validator.validateCodeValues(LIBRARY_ID, ruleWith(text, empty)));
    }
}
