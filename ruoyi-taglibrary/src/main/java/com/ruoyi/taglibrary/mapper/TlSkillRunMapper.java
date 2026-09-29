package com.ruoyi.taglibrary.mapper;

import java.util.List;
import com.ruoyi.taglibrary.domain.TlSkillRun;

/**
 * 洞察Skill运行记录 Mapper
 */
public interface TlSkillRunMapper {

    /** 新增运行记录 */
    int insertRun(TlSkillRun row);

    /** 运行历史列表（支持技能、客群、状态、操作人与时间范围过滤） */
    List<TlSkillRun> selectRunList(TlSkillRun query);
}
