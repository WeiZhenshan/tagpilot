package com.ruoyi.objectgroup.service;

import com.ruoyi.objectgroup.domain.RulePayload;

/**
 * 规则 SQL 生成器（规则 JSON → 查询 SQL，纯函数）
 */
public interface IRuleSqlBuilder {

    String MODE_COUNT = "COUNT";
    String MODE_SELECT = "SELECT";
    /** 仅供服务端洞察聚合子查询使用：完整客户键，不含样例列或 LIMIT。 */
    String MODE_IDS = "IDS";

    /**
     * 生成查询 SQL
     * @param versionId 数据集在线版本ID（由调用方经 DpOnlineVersionResolver 单次解析后传入）
     * @param rule      规则载荷（conditions + objectKeyField + previewColumns）
     * @param mode      COUNT / SELECT
     * @return SQL 字符串
     */
    String buildSql(Long versionId, RulePayload rule, String mode);

    /** 客户号物理列名（rule.objectKeyField 优先，回退库内 is_object_key） */
    String resolveObjectKeyColumn(Long versionId, RulePayload rule);
}
