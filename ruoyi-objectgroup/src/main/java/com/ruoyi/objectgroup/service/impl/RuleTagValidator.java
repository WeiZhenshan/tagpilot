package com.ruoyi.objectgroup.service.impl;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TagStatusRef;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;

/**
 * 对象群规则标签统一校验：保存、运行、SQL 预览、样例预览共用。
 * 校验标签所属库、上线状态、来源可用性、当前版本字段有效性及类型一致性；
 * 保存/运行额外校验选项型/布尔型条件的已选码值仍在维表码值中（失效编码不得继续保存或执行）。
 */
@Service
public class RuleTagValidator {

    /** 发布状态：已上线 */
    private static final String STATUS_ONLINE = "2";
    /** 发布状态：待完善（未通过首次元数据审核） */
    private static final String STATUS_PENDING = "4";
    /** 来源状态：可用 */
    private static final String SOURCE_AVAILABLE = "AVAILABLE";
    /** 来源状态：来源缺失 */
    private static final String SOURCE_MISSING = "MISSING";
    /** 来源状态：来源变更待确认 */
    private static final String SOURCE_CHANGED = "CHANGED";

    private static final String TAG_TYPE_OPTION = "选项型";
    private static final String TAG_TYPE_BOOL = "布尔型";

    @Autowired
    private TlObjectGroupExtMapper extMapper;
    @Autowired
    private DpOnlineVersionResolver onlineVersionResolver;
    @Autowired
    private IDimensionCodeOptionService dimensionCodeOptionService;

    /**
     * 校验规则引用的全部标签（条件字段、预览列、客户号字段）。
     * @param libraryId 标签库ID
     * @param versionId 当前在线数据集版本ID（调用方已解析）
     * @param rule      规则载荷
     */
    public void validateRule(Long libraryId, Long versionId, RulePayload rule) {
        if (rule == null) {
            return;
        }
        Map<String, TagStatusRef> tagsByField = new LinkedHashMap<>();
        List<TagStatusRef> tags = extMapper.selectTagRefsByLibrary(libraryId);
        if (tags != null) {
            for (TagStatusRef t : tags) {
                tagsByField.putIfAbsent(t.getFieldName(), t);
            }
        }
        Map<String, DpResolvedField> enabledByAlias = new LinkedHashMap<>();
        List<DpResolvedField> enabled = onlineVersionResolver.listEnabledFields(versionId);
        if (enabled != null) {
            for (DpResolvedField f : enabled) {
                enabledByAlias.putIfAbsent(f.getFieldAlias(), f);
            }
        }

        if (rule.getConditions() != null) {
            for (RulePayload.Condition c : rule.getConditions()) {
                TagStatusRef tag = validateFieldUsable(tagsByField, enabledByAlias, c.getFieldName(), c.getTagName());
                validateTypeConsistent(tag, c.getTagType(), c.getDataType());
            }
        }
        if (rule.getPreviewColumns() != null) {
            for (RulePayload.PreviewColumn pc : rule.getPreviewColumns()) {
                if (pc.getFieldName() == null || pc.getFieldName().equals(rule.getObjectKeyField())) {
                    continue;
                }
                TagStatusRef tag = validateFieldUsable(tagsByField, enabledByAlias, pc.getFieldName(), pc.getTagName());
                validateTypeConsistent(tag, pc.getTagType(), pc.getDataType());
            }
        }
        // 客户号字段：必须指向当前版本的启用字段；若库内存在对应标签，同样要求上线且来源可用
        String objectKey = rule.getObjectKeyField();
        if (objectKey != null && !objectKey.isEmpty()) {
            TagStatusRef tag = tagsByField.get(objectKey);
            if (tag != null) {
                validateTagStatus(tag);
            }
            if (!enabledByAlias.containsKey(objectKey)) {
                throw new ServiceException("客户号字段[" + objectKey + "]未在当前数据集版本中启用");
            }
        }
    }

    /**
     * 保存/运行追加校验：选项型/布尔型条件的已选码值必须在维表码值中，失效编码要求用户修正。
     * 码表不可达时明确报“无法校验”，不回退旧码值表。
     */
    public void validateCodeValues(Long libraryId, RulePayload rule) {
        if (rule == null || rule.getConditions() == null) {
            return;
        }
        for (RulePayload.Condition c : rule.getConditions()) {
            String tagType = c.getTagType() == null ? "" : c.getTagType();
            if (!TAG_TYPE_OPTION.equals(tagType) && !TAG_TYPE_BOOL.equals(tagType)) {
                continue;
            }
            if (c.getValues() == null || c.getValues().isEmpty()) {
                continue;
            }
            String label = c.getTagName() != null ? c.getTagName() : c.getFieldName();
            List<Map<String, Object>> options;
            try {
                options = dimensionCodeOptionService.listCodeOptions(libraryId, c.getFieldName());
            } catch (ServiceException e) {
                throw new ServiceException("标签[" + label + "]的码值无法校验：" + e.getMessage());
            }
            Set<String> validCodes = new LinkedHashSet<>();
            for (Map<String, Object> option : options) {
                Object code = option.get("code");
                if (code != null) {
                    validCodes.add(String.valueOf(code));
                }
            }
            for (String v : c.getValues()) {
                if (v != null && !validCodes.contains(v)) {
                    throw new ServiceException("标签[" + label + "]的码值[" + v + "]已失效，请修正后重新保存");
                }
            }
        }
    }

    /** 校验字段对应标签存在、已上线、来源可用且字段在当前版本启用，返回标签快照 */
    private TagStatusRef validateFieldUsable(Map<String, TagStatusRef> tagsByField,
                                             Map<String, DpResolvedField> enabledByAlias,
                                             String fieldName, String displayName) {
        String label = displayName != null ? displayName : String.valueOf(fieldName);
        TagStatusRef tag = fieldName == null ? null : tagsByField.get(fieldName);
        if (tag == null) {
            throw new ServiceException("标签[" + label + "]不存在于当前标签库或已删除");
        }
        validateTagStatus(tag);
        if (!enabledByAlias.containsKey(fieldName)) {
            throw new ServiceException("标签[" + label + "]的字段未在当前数据集版本中启用，请重新同步后修正规则");
        }
        return tag;
    }

    /** 发布状态 + 来源状态校验，报错指明具体标签与具体问题 */
    private void validateTagStatus(TagStatusRef tag) {
        String label = tag.getTagName() != null ? tag.getTagName() : tag.getFieldName();
        if (!STATUS_ONLINE.equals(tag.getStatus())) {
            if (STATUS_PENDING.equals(tag.getStatus())) {
                throw new ServiceException("标签[" + label + "]尚未通过首次元数据审核（待完善），不能用于对象群");
            }
            throw new ServiceException("标签[" + label + "]未上线，不能用于对象群");
        }
        if (SOURCE_MISSING.equals(tag.getSourceStatus())) {
            throw new ServiceException("标签[" + label + "]的来源字段已缺失，不能用于对象群");
        }
        if (SOURCE_CHANGED.equals(tag.getSourceStatus())) {
            throw new ServiceException("标签[" + label + "]的来源已变更待确认，审核通过前不能用于对象群");
        }
        if (!SOURCE_AVAILABLE.equals(tag.getSourceStatus())) {
            throw new ServiceException("标签[" + label + "]的来源状态不可用，不能用于对象群");
        }
    }

    /** 规则中声明的类型与库中实际类型一致性（旧规则缺省字段时跳过） */
    private void validateTypeConsistent(TagStatusRef tag, String declaredTagType, String declaredDataType) {
        String label = tag.getTagName() != null ? tag.getTagName() : tag.getFieldName();
        if (declaredTagType != null && !declaredTagType.isEmpty() && !declaredTagType.equals(tag.getTagType())) {
            throw new ServiceException("标签[" + label + "]的类型已变更（规则中为" + declaredTagType
                    + "，库中实际为" + tag.getTagType() + "），请修正规则");
        }
        if (declaredDataType != null && !declaredDataType.isEmpty()
                && tag.getDataType() != null && !declaredDataType.equals(tag.getDataType())) {
            throw new ServiceException("标签[" + label + "]的数据类型已变更（规则中为" + declaredDataType
                    + "，库中实际为" + tag.getDataType() + "），请修正规则");
        }
    }
}
