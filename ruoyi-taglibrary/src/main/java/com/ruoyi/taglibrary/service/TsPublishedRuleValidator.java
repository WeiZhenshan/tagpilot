package com.ruoyi.taglibrary.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.service.IRuleAuthorityValidator;

/** 保存的高级规则仍须按当前身份与发布版本重建；不相信客户端携带的物理 AST。 */
@Component
public class TsPublishedRuleValidator implements IRuleAuthorityValidator {
    @Autowired private TsAudiencePlanCompiler compiler;
    @Override public void validate(Long libraryId, RulePayload rule) {
        if(rule.getAudiencePlan()==null)throw new ServiceException("高级圈选规则缺少原发布方案");
        RulePayload rebuilt=compiler.compile(libraryId,rule.getAudiencePlan());
        if(rebuilt.getSchemaVersion()!=4)throw new ServiceException("高级规则不能降级解释");
        rule.setConditions(rebuilt.getConditions());rule.setPreviewColumns(rebuilt.getPreviewColumns());
        rule.setObjectKeyField(rebuilt.getObjectKeyField());rule.setAuthorityValidated(true);
    }
}
