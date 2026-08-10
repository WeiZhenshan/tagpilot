package com.ruoyi.objectgroup.service.impl;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupImportMapper;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;

/**
 * 规则 SQL 生成器：规则 JSON → WHERE 子句 → 完整查询 SQL
 */
@Service
public class RuleSqlBuilder implements IRuleSqlBuilder {

    private static final Logger log = LoggerFactory.getLogger(RuleSqlBuilder.class);

    public static final String MODE_COUNT = "COUNT";
    public static final String MODE_SELECT = "SELECT";

    private static final int PREVIEW_LIMIT = 100;
    private static final int MAX_IMPORT_VALUES = 50000;

    /** 日期型条件允许的取值格式：yyyy-MM-dd，可带可选时间部分 */
    private static final Pattern DATE_VALUE_PATTERN =
            Pattern.compile("^\\d{4}-\\d{2}-\\d{2}([ T]\\d{2}:\\d{2}(:\\d{2})?)?$");

    @Autowired
    private TlObjectGroupExtMapper extMapper;
    @Autowired
    private TlObjectGroupImportMapper importMapper;
    @Autowired
    private ObjectMapper objectMapper;

    @Override
    public String buildSql(Long libraryId, RulePayload rule, String mode) {
        Long versionId = extMapper.selectOnlineVersionId(libraryId);
        if (versionId == null) {
            throw new ServiceException("关联标签库的数据集不存在或未上线");
        }
        String tableName = resolveTableName(versionId);
        if (tableName == null) {
            throw new ServiceException("无法定位规则执行宽表，请检查数据集的宽表配置");
        }

        StringBuilder sql = new StringBuilder();
        if (MODE_SELECT.equals(mode)) {
            String objectKeyCol = resolveObjectKeyColumnByVersion(versionId, rule);
            List<String> selectCols = new ArrayList<>();
            selectCols.add(backtick(objectKeyCol));
            if (rule.getPreviewColumns() != null) {
                for (RulePayload.PreviewColumn pc : rule.getPreviewColumns()) {
                    if (pc.getFieldName() == null || pc.getFieldName().equals(rule.getObjectKeyField())) {
                        continue;
                    }
                    String col = extMapper.selectColumnNameByAlias(versionId, pc.getFieldName());
                    if (col != null) {
                        selectCols.add(backtick(col) + " as " + backtick(pc.getTagName() != null ? pc.getTagName() : pc.getFieldName()));
                    }
                }
            }
            sql.append("select ").append(String.join(", ", selectCols));
        } else {
            sql.append("select count(*)");
        }
        sql.append(" from ").append(backtick(tableName));

        String where = buildWhere(versionId, rule);
        if (!where.isEmpty()) {
            sql.append(" where ").append(where);
        }
        if (MODE_SELECT.equals(mode)) {
            sql.append(" limit ").append(PREVIEW_LIMIT);
        }
        return sql.toString();
    }

    @Override
    public String resolveObjectKeyColumn(Long libraryId, RulePayload rule) {
        Long versionId = extMapper.selectOnlineVersionId(libraryId);
        if (versionId == null) {
            throw new ServiceException("关联标签库的数据集不存在或未上线");
        }
        return resolveObjectKeyColumnByVersion(versionId, rule);
    }

    private String resolveObjectKeyColumnByVersion(Long versionId, RulePayload rule) {
        if (rule.getObjectKeyField() != null && !rule.getObjectKeyField().isEmpty()) {
            String col = extMapper.selectColumnNameByAlias(versionId, rule.getObjectKeyField());
            if (col != null) {
                return col;
            }
        }
        String fallback = extMapper.selectObjectKeyColumn(versionId);
        if (fallback == null) {
            throw new ServiceException("该标签库未标记客户号字段，请先同步字段");
        }
        return fallback;
    }

    private String resolveTableName(Long versionId) {
        String definitionJson = extMapper.selectVersionDefinitionJson(versionId);
        if (definitionJson == null || definitionJson.isEmpty()) {
            return null;
        }
        try {
            Map<String, Object> def = objectMapper.readValue(definitionJson,
                    new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {});
            Object tableIdObj = def.get("tableId");
            if (tableIdObj == null) {
                return null;
            }
            Long tableId = Long.valueOf(String.valueOf(tableIdObj));
            return extMapper.selectTableObjectName(tableId);
        } catch (Exception e) {
            log.warn("解析数据集定义 JSON 失败: {}", e.getMessage());
            return null;
        }
    }

    private String buildWhere(Long versionId, RulePayload rule) {
        if (rule.getConditions() == null || rule.getConditions().isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        int parenBalance = 0;
        for (RulePayload.Condition c : rule.getConditions()) {
            String col = extMapper.selectColumnNameByAlias(versionId, c.getFieldName());
            if (col == null) {
                throw new ServiceException("规则字段[" + c.getFieldName() + "]未在数据集中启用");
            }
            String expr = buildConditionSql(c, col);
            if (expr == null || expr.isEmpty()) {
                continue;
            }
            // connector must precede open parens: "expr1 and (expr2 ...)", not "expr1 ( and expr2"
            if (!first) {
                sb.append(" ").append("AND".equalsIgnoreCase(c.getConnector()) ? "and" : "or").append(" ");
            }
            int open = orZero(c.getOpenParen());
            for (int i = 0; i < open; i++) {
                sb.append("(");
            }
            sb.append(expr);
            int close = orZero(c.getCloseParen());
            for (int i = 0; i < close; i++) {
                sb.append(")");
            }
            parenBalance += open - close;
            if (parenBalance < 0) {
                throw new ServiceException("规则括号不匹配，请检查分组设置");
            }
            first = false;
        }
        if (parenBalance != 0) {
            throw new ServiceException("规则括号不匹配，请检查分组设置");
        }
        return sb.toString();
    }

    private String buildConditionSql(RulePayload.Condition c, String col) {
        String column = backtick(col);
        String tagType = c.getTagType() == null ? "" : c.getTagType();

        if ("客户号".equals(tagType) || ("import".equals(c.getMatchType()))) {
            if ("import".equals(c.getMatchType())) {
                if (c.getImportBatchNo() == null || c.getImportBatchNo().isEmpty()) {
                    throw new ServiceException("客户号导入批次缺失");
                }
                List<String> values = importMapper.selectValuesByBatch(c.getImportBatchNo());
                if (values == null || values.isEmpty()) {
                    throw new ServiceException("导入批次无数据，请重新导入");
                }
                if (values.size() > MAX_IMPORT_VALUES) {
                    throw new ServiceException("导入值超过上限（5万条），请拆分后重新导入");
                }
                List<String> quoted = new ArrayList<>();
                for (String v : values) {
                    quoted.add(quote(v));
                }
                return column + " in (" + String.join(", ", quoted) + ")";
            }
            String value = valueAt(c.getValues(), 0);
            if ("like".equals(c.getMatchType())) {
                return column + " like " + quote("%" + value + "%");
            }
            return column + " = " + quote(value);
        }

        if ("布尔型".equals(tagType)) {
            return column + " = " + quote(valueAt(c.getValues(), 0));
        }
        if ("选项型".equals(tagType)) {
            List<String> quoted = new ArrayList<>();
            for (String v : c.getValues()) {
                quoted.add(quote(v));
            }
            return column + " in (" + String.join(", ", quoted) + ")";
        }
        if ("数值型".equals(tagType)) {
            String v1 = valueAt(c.getValues(), 0);
            String v2 = valueAt(c.getValues(), 1);
            boolean hasV1 = v1 != null && !v1.isEmpty();
            boolean hasV2 = v2 != null && !v2.isEmpty();
            if (!hasV1 && !hasV2) {
                throw new ServiceException("数值型规则[" + c.getTagName() + "]未填写范围");
            }
            if (hasV1 && hasV2) {
                return column + " >= " + numericLiteral(v1, c) + " and " + column + " <= " + numericLiteral(v2, c);
            }
            if (hasV1) {
                return column + " >= " + numericLiteral(v1, c);
            }
            return column + " <= " + numericLiteral(v2, c);
        }
        if ("日期型".equals(tagType)) {
            String start = valueAt(c.getValues(), 0);
            String end = valueAt(c.getValues(), 1);
            if (isBlank(start) && isBlank(end)) {
                throw new ServiceException("日期型规则[" + c.getTagName() + "]未选择范围");
            }
            List<String> parts = new ArrayList<>();
            if (!isBlank(start)) {
                parts.add(column + " >= " + dateLiteral(start, c));
            }
            if (!isBlank(end)) {
                parts.add(column + " <= " + dateLiteral(end, c));
            }
            return String.join(" and ", parts);
        }
        // 文本型
        String value = valueAt(c.getValues(), 0);
        if ("like".equals(c.getOperator())) {
            return column + " like " + quote("%" + value + "%");
        }
        return column + " = " + quote(value);
    }

    // ---- helpers ----

    private int orZero(Integer v) {
        return v == null ? 0 : v;
    }

    private String valueAt(List<String> values, int idx) {
        if (values == null || values.size() <= idx) {
            return "";
        }
        String v = values.get(idx);
        return v == null ? "" : v.trim();
    }

    private boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }

    /** 标识符反引号转义 */
    private String backtick(String identifier) {
        return "`" + identifier.replace("`", "``") + "`";
    }

    /** 字符串值单引号转义 */
    private String quote(String value) {
        if (value == null) {
            return "''";
        }
        return "'" + value.replace("'", "''") + "'";
    }

    /** 数值型条件字面值：仅接受合法数字，拒绝一切原样拼接，防 SQL 注入 */
    private String numericLiteral(String value, RulePayload.Condition c) {
        try {
            return new BigDecimal(value).toPlainString();
        } catch (NumberFormatException e) {
            throw new ServiceException("数值型规则[" + c.getTagName() + "]的范围值不是合法数字");
        }
    }

    /** 日期型条件字面值：白名单格式校验后再转义 */
    private String dateLiteral(String value, RulePayload.Condition c) {
        if (!DATE_VALUE_PATTERN.matcher(value).matches()) {
            throw new ServiceException("日期型规则[" + c.getTagName() + "]的日期格式不正确");
        }
        return quote(value);
    }
}
