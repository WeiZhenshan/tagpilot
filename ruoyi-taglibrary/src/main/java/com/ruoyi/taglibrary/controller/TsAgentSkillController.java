package com.ruoyi.taglibrary.controller;

import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.taglibrary.service.TsAgentSkillService;

@RestController
@RequestMapping("/taglibrary/agent/skills")
public class TsAgentSkillController {
    @Autowired private TsAgentSkillService skills;
    @GetMapping
    @PreAuthorize("@ss.hasPermi('taglibrary:insight:list')")
    public AjaxResult list(){return AjaxResult.success(skills.list(false));}
    @GetMapping("/available")
    @PreAuthorize("@ss.hasPermi('taglibrary:insight:run')")
    public AjaxResult available(){return AjaxResult.success(skills.list(true));}
    @PostMapping
    @PreAuthorize("@ss.hasPermi('taglibrary:insight:edit')")
    @Log(title="Agent技能草稿",businessType=BusinessType.UPDATE,isSaveRequestData=false)
    public AjaxResult save(@RequestBody Map<String,Object> body){skills.save(body);return AjaxResult.success();}
    @PostMapping("/{name}/publish")
    @PreAuthorize("@ss.hasPermi('taglibrary:insight:publish')")
    @Log(title="Agent技能发布",businessType=BusinessType.UPDATE)
    public AjaxResult publish(@PathVariable String name,@RequestBody Map<String,Object> body){skills.publish(name,body);return AjaxResult.success();}
    @PostMapping("/{name}/retire")
    @PreAuthorize("@ss.hasPermi('taglibrary:insight:publish')")
    @Log(title="Agent技能下线",businessType=BusinessType.UPDATE)
    public AjaxResult retire(@PathVariable String name,@RequestBody Map<String,Object> body){skills.retire(name,body);return AjaxResult.success();}
}
