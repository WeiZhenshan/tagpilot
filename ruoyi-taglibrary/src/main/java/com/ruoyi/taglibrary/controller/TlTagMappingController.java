package com.ruoyi.taglibrary.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.DraftSaveRequest;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeRequest;
import com.ruoyi.taglibrary.service.ITlTagLibraryService;
import com.ruoyi.taglibrary.service.ITlTagMappingService;

/**
 * 标签元数据变更（批量映射）Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/taglibrary/tag/mapping")
public class TlTagMappingController extends BaseController {

    @Autowired
    private ITlTagMappingService mappingService;

    @Autowired
    private ITlTagLibraryService libraryService;

    /** 批量映射分页列表（合并草稿/待审核状态） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:list')")
    @GetMapping("/list")
    public TableDataInfo list(TlTag query) {
        if (query.getLibraryId() == null) {
            throw new ServiceException("标签库ID不能为空");
        }
        startPage();
        return getDataTable(mappingService.selectMappingList(query));
    }

    /** 进入批量映射：增量同步标签库创建时关联数据集的所有字段为标签（幂等，尽力而为不阻塞映射查看） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:list')")
    @PostMapping("/sync/{libraryId}")
    public AjaxResult syncFields(@PathVariable Long libraryId) {
        try {
            int count = libraryService.syncFields(libraryId);
            return AjaxResult.success("同步完成，新增" + count + "个字段标签", count);
        } catch (ServiceException e) {
            // 数据集未上线/无启用字段等业务异常不阻塞进入页面，仍可查看现有映射
            return AjaxResult.success(e.getMessage());
        }
    }

    /** 批量保存草稿 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:save')")
    @PutMapping("/draft")
    public AjaxResult saveDraft(@RequestBody DraftSaveRequest request) {
        int saved = mappingService.saveDraft(request.getItems());
        return AjaxResult.success("草稿保存成功，共保存" + saved + "条");
    }

    /** 批量提交审核 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:submit')")
    @PostMapping("/submit")
    public AjaxResult submit(@RequestBody MetadataChangeRequest request) {
        return toAjax(mappingService.submit(request.getChangeIds()));
    }

    /** 待审核变更分页列表 */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:audit')")
    @GetMapping("/auditList")
    public TableDataInfo auditList(TlTagMetadataChange query) {
        startPage();
        return getDataTable(mappingService.selectAuditList(query));
    }

    /** 批量审核（pass=true通过 false驳回） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:audit')")
    @PostMapping("/audit")
    public AjaxResult audit(@RequestBody MetadataChangeRequest request) {
        if (request.getPass() == null) {
            throw new ServiceException("审核结论不能为空");
        }
        return toAjax(mappingService.audit(request.getChangeIds(), request.getPass(), request.getAuditComment()));
    }

    /** 变更差异详情（当前值 → 申请值对比） */
    @PreAuthorize("@ss.hasPermi('taglibrary:tag:mapping:audit')")
    @GetMapping("/{changeId}")
    public AjaxResult getInfo(@PathVariable Long changeId) {
        return success(mappingService.getChangeDetail(changeId));
    }
}
