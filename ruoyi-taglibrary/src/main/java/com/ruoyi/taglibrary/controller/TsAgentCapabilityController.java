package com.ruoyi.taglibrary.controller;

import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.taglibrary.service.TsAgentCapabilityService;

/** 治理人员维护版本；模型没有此写接口。复核不等于激活发布快照。 */
@RestController
@RequestMapping("/taglibrary/semantic/capabilities")
public class TsAgentCapabilityController {
    @Autowired private TsAgentCapabilityService service;
    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PostMapping("/{libraryId}")
    public AjaxResult save(@PathVariable Long libraryId,@RequestBody Map<String,Object> body) {
        service.save(libraryId,body);return AjaxResult.success("草稿版本已保存，复核并发布后生效");
    }
    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/{libraryId}/{id}/{version}/review")
    public AjaxResult review(@PathVariable Long libraryId,@PathVariable String id,@PathVariable Integer version) {
        service.review(libraryId,id,version);return AjaxResult.success("版本已复核，需通过快照发布生效");
    }
}
