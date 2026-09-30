package com.ruoyi.taglibrary.controller;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.taglibrary.service.*;
@RestController
@RequestMapping("/taglibrary/insight")
public class TsInsightController {
 @Autowired private TsInsightRegistryService registry;
 @Autowired private TsInsightRunService runs;
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:list') or @ss.hasPermi('taglibrary:insight:run')")
 @GetMapping("/{libraryId}/catalog") public AjaxResult catalog(@PathVariable Long libraryId){return AjaxResult.success(registry.catalog(libraryId));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:list')")
 @PostMapping("/{libraryId}/{id}/{version}/trial") public AjaxResult trial(@PathVariable Long libraryId,@PathVariable String id,@PathVariable String version){return AjaxResult.success(registry.trial(libraryId,id,version));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:edit')")
 @Log(title="洞察技能版本",businessType=BusinessType.INSERT)
 @PostMapping("/{libraryId}/versions") public AjaxResult save(@PathVariable Long libraryId,@RequestBody Map<String,Object> body){registry.save(libraryId,body);return AjaxResult.success("草稿已登记，复核后方可发布");}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:review')")
 @Log(title="洞察技能复核",businessType=BusinessType.UPDATE)
 @PostMapping("/{libraryId}/{id}/{version}/review") public AjaxResult review(@PathVariable Long libraryId,@PathVariable String id,@PathVariable String version){registry.review(libraryId,id,version);return AjaxResult.success();}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:publish')")
 @Log(title="洞察技能发布或回滚",businessType=BusinessType.UPDATE)
 @PostMapping("/{libraryId}/{id}/{version}/publish") public AjaxResult publish(@PathVariable Long libraryId,@PathVariable String id,@PathVariable String version){registry.publish(libraryId,id,version);return AjaxResult.success();}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:publish')")
 @Log(title="洞察技能下线",businessType=BusinessType.UPDATE)
 @PostMapping("/{libraryId}/{id}/retire") public AjaxResult retire(@PathVariable Long libraryId,@PathVariable String id){registry.retire(libraryId,id);return AjaxResult.success();}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:run') and @ss.hasPermi('objectgroup:group:run')")
 @Log(title="客群洞察运行",businessType=BusinessType.OTHER,isSaveRequestData=false,isSaveResponseData=false)
 @PostMapping("/threads/{id}/run") public AjaxResult run(@PathVariable String id,@RequestBody Map<String,Object> body){return AjaxResult.success(runs.run(id,body));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:run')")
 @PostMapping("/threads/{id}/route") public AjaxResult route(@PathVariable String id,@RequestBody Map<String,Object> body){return AjaxResult.success(runs.route(id,body));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:run')")
 @PostMapping("/threads/{id}/edit") public AjaxResult edit(@PathVariable String id,@RequestBody Map<String,Object> body){return AjaxResult.success(runs.edit(id,body));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:list')")
 @GetMapping("/{libraryId}/audit") public AjaxResult audit(@PathVariable Long libraryId){return AjaxResult.success(runs.audit(libraryId));}
 @PreAuthorize("@ss.hasPermi('taglibrary:insight:run')")
 @PostMapping("/runs/{id}/feedback") public AjaxResult feedback(@PathVariable String id,@RequestBody Map<String,Object> body){runs.feedback(id,body);return AjaxResult.success();}
}
