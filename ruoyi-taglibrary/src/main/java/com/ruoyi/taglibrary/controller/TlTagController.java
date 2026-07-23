package com.ruoyi.taglibrary.controller;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.dto.AuditRequest;
import com.ruoyi.taglibrary.domain.dto.MoveRequest;
import com.ruoyi.taglibrary.mapper.TlAuditLogMapper;
import com.ruoyi.taglibrary.service.ITlTagService;

/**
 * 标签管理 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/taglibrary/tag")
public class TlTagController extends BaseController {

    @Autowired
    private ITlTagService tagService;

    @Autowired
    private TlAuditLogMapper auditLogMapper;

    /** 左侧树（tab=online 已上线 / offline 未上线） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:list')")
    @GetMapping("/tree")
    public AjaxResult tree(@RequestParam Long libraryId, @RequestParam(defaultValue = "online") String tab) {
        return success(tagService.buildTree(libraryId, tab));
    }

    /** 字段管理抽屉的分页列表 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:list')")
    @GetMapping("/list")
    public TableDataInfo list(TlTag query) {
        startPage();
        return getDataTable(tagService.selectTagList(query));
    }

    /** 标签详情 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:query')")
    @GetMapping("/{tagId}")
    public AjaxResult getInfo(@PathVariable Long tagId) {
        return success(tagService.selectTagById(tagId));
    }

    /** 编辑标签（version+1） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody TlTag tag) {
        return toAjax(tagService.updateTag(tag));
    }

    /** 批量移动目录 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:move')")
    @PutMapping("/move")
    public AjaxResult move(@RequestBody MoveRequest request) {
        return toAjax(tagService.moveTag(request.getTagIds(), request.getDirId()));
    }

    /** 批量提交审批 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:submit')")
    @PostMapping("/submit")
    public AjaxResult submit(@RequestBody AuditRequest request) {
        return toAjax(tagService.submit(request.getIds()));
    }

    /** 批量审批（通过→已上线 / 驳回→草稿） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:audit')")
    @PostMapping("/audit")
    public AjaxResult audit(@RequestBody AuditRequest request) {
        return toAjax(tagService.audit(request.getIds(), request.getPass(), request.getAuditComment()));
    }

    /** 批量下线 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:offline')")
    @PostMapping("/offline")
    public AjaxResult offline(@RequestBody AuditRequest request) {
        return toAjax(tagService.offline(request.getIds()));
    }

    /** 审批日志（库/标签共用：bizType=library|tag） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
    @GetMapping("/auditLogs")
    public TableDataInfo auditLogs(TlAuditLog query) {
        startPage();
        List<TlAuditLog> list = auditLogMapper.selectAuditLogList(query);
        return getDataTable(list);
    }
}
