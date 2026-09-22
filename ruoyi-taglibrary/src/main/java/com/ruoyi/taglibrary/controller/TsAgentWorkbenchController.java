package com.ruoyi.taglibrary.controller;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.taglibrary.service.TsAgentWorkbenchService;

@RestController
@RequestMapping("/taglibrary/agent")
@PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
public class TsAgentWorkbenchController extends BaseController {
    @Autowired private TsAgentWorkbenchService service;
    @Autowired private com.fasterxml.jackson.databind.ObjectMapper json;
    /** 有界 SSE 帧；浏览器重连只读取已持久化运行，绝不重发用户命令。 */
    @GetMapping(value="/threads/{id}/events",produces="text/event-stream")
    public org.springframework.http.ResponseEntity<String> events(@PathVariable String id) throws Exception {
        return org.springframework.http.ResponseEntity.ok().header("Cache-Control","no-store").header("X-Accel-Buffering","no")
            .body("retry: 1000\nevent: state\ndata: "+json.writeValueAsString(service.get(id))+"\n\n");
    }
    @GetMapping("/threads") public AjaxResult list(@RequestParam(defaultValue="false") boolean archived) { return success(service.listThreads(archived)); }
    @PostMapping("/threads") public AjaxResult create(@RequestBody Map<String,Object> body) { return success(service.create(Long.valueOf(String.valueOf(body.get("library_id"))))); }
    @GetMapping("/threads/{id}") public AjaxResult get(@PathVariable String id) { return success(service.get(id)); }
    @PatchMapping("/threads/{id}") public AjaxResult rename(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.rename(id,body));}
    @DeleteMapping("/threads/{id}") public AjaxResult delete(@PathVariable String id) {service.delete(id);return success();}
    @PostMapping("/threads/{id}/runs") public AjaxResult start(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.start(id,body));}
    @PostMapping("/threads/{id}/resume") public AjaxResult resume(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.resume(id,body));}
    @PostMapping("/threads/{id}/cancel") public AjaxResult cancel(@PathVariable String id) {return success(service.cancel(id));}
    @PostMapping("/threads/{id}/count") public AjaxResult count(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.count(id,body));}
    @PostMapping("/threads/{id}/preview") public AjaxResult preview(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.preview(id,body));}
    @PostMapping("/threads/{id}/create-group") public AjaxResult createGroup(@PathVariable String id,@RequestBody Map<String,Object> body) {return success(service.createGroup(id,body));}
    @GetMapping("/threads/{id}/execution") public AjaxResult execution(@PathVariable String id) {return success(service.execution(id));}
}
