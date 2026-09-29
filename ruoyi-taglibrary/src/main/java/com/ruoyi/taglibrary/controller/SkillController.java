package com.ruoyi.taglibrary.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.taglibrary.domain.TlSkillRun;
import com.ruoyi.taglibrary.domain.dto.SkillRunRequest;
import com.ruoyi.taglibrary.domain.dto.SkillStatusRequest;
import com.ruoyi.taglibrary.service.ISkillService;

/**
 * 洞察Skill治理：列表/详情/版本、生命周期流转、试运行与运行历史
 *
 * <p>Skill 定义与执行由 Python 技能引擎负责，本控制器只做治理代理与留痕。</p>
 */
@RestController
@RequestMapping("/taglibrary/skill")
public class SkillController extends BaseController {

    @Autowired
    private ISkillService skillService;

    /** 技能列表（代理技能引擎，按登录用户权限收敛） */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:list')")
    @GetMapping("/list")
    public AjaxResult list(@RequestParam(required = false) String status,
                           @RequestParam(required = false) String category,
                           @RequestParam(required = false) String keyword,
                           @RequestParam(required = false) Integer limit,
                           @RequestParam(required = false) Integer offset) {
        return success(skillService.listSkills(status, category, keyword, limit, offset));
    }

    /** 运行历史（本地 tl_skill_run 分页查询） */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:list')")
    @GetMapping("/runs")
    public TableDataInfo runs(TlSkillRun query) {
        startPage();
        return getDataTable(skillService.listRuns(query));
    }

    /** 技能详情（含 Manifest 与生命周期） */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:query')")
    @GetMapping("/{skillId}")
    public AjaxResult detail(@PathVariable String skillId, @RequestParam(required = false) String version) {
        return success(skillService.getSkill(skillId, version));
    }

    /** 技能版本列表 */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:query')")
    @GetMapping("/{skillId}/versions")
    public AjaxResult versions(@PathVariable String skillId) {
        return success(skillService.listVersions(skillId));
    }

    /** 生命周期状态流转（发布/下线/废弃/转草稿），成功与失败均写审计 */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:publish')")
    @PostMapping("/{skillId}/status")
    public AjaxResult status(@PathVariable String skillId, @RequestBody SkillStatusRequest request) {
        return success(skillService.changeStatus(skillId, request));
    }

    /** 试运行：解析客群成员后调用技能引擎并留存运行记录 */
    @PreAuthorize("@ss.hasPermi('taglibrary:skill:run')")
    @PostMapping("/{skillId}/run")
    public AjaxResult run(@PathVariable String skillId, @RequestBody SkillRunRequest request) {
        return success(skillService.runSkill(skillId, request));
    }
}
