package com.ruoyi.objectgroup.service;

import com.ruoyi.objectgroup.domain.RulePayload;

/** 上层模块实现发布规则重新核验，避免 objectgroup 反向依赖 taglibrary。 */
public interface IRuleAuthorityValidator {
    void validate(Long libraryId, RulePayload rule);
}
