package com.ruoyi.objectgroup.service;

import com.ruoyi.objectgroup.domain.RulePayload;

/**
 * 规则 SQL 生成器（规则 JSON → 查询 SQL，纯函数）
 */
public interface IRuleSqlBuilder {

    String MODE_COUNT = "COUNT";
    String MODE_SELECT = "SELECT";

    /**
     * 生成查询 SQL
     * @param libraryId 标签库ID
     * @param rule      规则载荷（conditions + objectKeyField + previewColumns）
     * @param mode      COUNT / SELECT
     * @return SQL 字符串
     */
    String buildSql(Long libraryId, RulePayload rule, String mode);

    /** 客户号物理列名（rule.objectKeyField 优先，回退库内 is_object_key） */
    String resolveObjectKeyColumn(Long libraryId, RulePayload rule);
}
