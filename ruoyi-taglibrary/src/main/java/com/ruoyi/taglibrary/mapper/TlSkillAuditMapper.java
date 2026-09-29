package com.ruoyi.taglibrary.mapper;

import com.ruoyi.taglibrary.domain.TlSkillAudit;

/**
 * 洞察Skill管理动作审计 Mapper
 */
public interface TlSkillAuditMapper {

    /** 新增审计记录 */
    int insertAudit(TlSkillAudit row);
}
