package com.ruoyi.taglibrary.service;

import java.util.List;
import java.util.Map;
import com.ruoyi.taglibrary.domain.TlSkillRun;
import com.ruoyi.taglibrary.domain.dto.SkillRunRequest;
import com.ruoyi.taglibrary.domain.dto.SkillStatusRequest;

/**
 * 洞察Skill治理服务。
 *
 * <p>Skill 的定义、版本、生命周期与执行权威都在 Python（tagpilot-agent）；
 * 本服务负责代理调用、本地权限收敛、客群成员解析、运行记录与审计落库。</p>
 */
public interface ISkillService {

    /**
     * 技能列表（代理 GET /skills）
     *
     * @param status   状态过滤：draft/published/deprecated/offline，可空
     * @param category 分类过滤：fact/diagnostic/action，可空
     * @param keyword  关键字（名称或描述），可空
     * @param limit    返回条数上限，可空
     * @param offset   偏移量，可空
     */
    Map<String, Object> listSkills(String status, String category, String keyword, Integer limit, Integer offset);

    /** 技能详情（代理 GET /skills/{id}），version 可空表示当前版本 */
    Map<String, Object> getSkill(String skillId, String version);

    /** 技能版本与生命周期（代理 GET /skills/{id}/versions） */
    Map<String, Object> listVersions(String skillId);

    /** 生命周期状态流转（代理 POST /skills/{id}/status 并写审计） */
    Map<String, Object> changeStatus(String skillId, SkillStatusRequest request);

    /** 试运行：解析客群成员 → 代理 POST /skills/{id}/run → 落运行记录 */
    Map<String, Object> runSkill(String skillId, SkillRunRequest request);

    /** 运行历史（查本地 tl_skill_run） */
    List<TlSkillRun> listRuns(TlSkillRun query);
}
