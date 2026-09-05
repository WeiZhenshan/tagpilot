package com.ruoyi.taglibrary.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
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
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.dto.AuditRequest;
import com.ruoyi.taglibrary.service.ITlTagLibraryService;

/**
 * 标签库管理 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/taglibrary/library")
public class TlTagLibraryController extends BaseController {

    @Autowired
    private ITlTagLibraryService libraryService;

    /** 标签库分页列表（含卡片统计） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:list')")
    @GetMapping("/list")
    public TableDataInfo list(TlTagLibrary query) {
        startPage();
        return getDataTable(libraryService.selectLibraryList(query));
    }

    /** 已上线数据集列表（新建弹窗选用） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
    @GetMapping("/datasets")
    public AjaxResult datasets() {
        return success(libraryService.listOnlineDatasets());
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:query')")
    @GetMapping("/{libraryId}")
    public AjaxResult getInfo(@PathVariable Long libraryId) {
        return success(libraryService.selectLibraryById(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:add')")
    @PostMapping
    public AjaxResult add(@RequestBody TlTagLibrary library) {
        return toAjax(libraryService.insertLibrary(library));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody TlTagLibrary library) {
        return toAjax(libraryService.updateLibrary(library));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:library:remove')")
    @DeleteMapping("/{libraryIds}")
    public AjaxResult remove(@PathVariable Long[] libraryIds) {
        return toAjax(libraryService.deleteLibraryByIds(libraryIds));
    }

    /** 同步数据集字段（按当前在线版本对账，返回版本信息与统计） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:sync')")
    @PostMapping("/sync/{libraryId}")
    public AjaxResult sync(@PathVariable Long libraryId) {
        return AjaxResult.success("同步完成", libraryService.syncFields(libraryId));
    }

    /** 提交审批（草稿/已下线→待审批） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:submit')")
    @PostMapping("/submit/{libraryId}")
    public AjaxResult submit(@PathVariable Long libraryId) {
        return toAjax(libraryService.submit(libraryId));
    }

    /** 审批（通过→已上线 / 驳回→草稿） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:audit')")
    @PostMapping("/audit")
    public AjaxResult audit(@RequestBody AuditRequest request) {
        return toAjax(libraryService.audit(request.getIds()[0], request.getPass(), request.getAuditComment()));
    }

    /** 下线（已上线→已下线） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:offline')")
    @PostMapping("/offline/{libraryId}")
    public AjaxResult offline(@PathVariable Long libraryId) {
        return toAjax(libraryService.offline(libraryId));
    }
}
