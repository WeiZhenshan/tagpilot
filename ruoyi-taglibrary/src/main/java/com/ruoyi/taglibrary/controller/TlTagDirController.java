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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.service.ITlTagDirService;

/**
 * 标签目录 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/taglibrary/dir")
public class TlTagDirController extends BaseController {

    @Autowired
    private ITlTagDirService dirService;

    /** 目录列表 */
    @PreAuthorize("@ss.hasPermi('taglibrary:dir:list')")
    @GetMapping("/list")
    public AjaxResult list(@RequestParam Long libraryId) {
        return success(dirService.selectDirList(libraryId));
    }

    /** 新增目录 */
    @PreAuthorize("@ss.hasPermi('taglibrary:dir:add')")
    @PostMapping
    public AjaxResult add(@RequestBody TlTagDir dir) {
        return toAjax(dirService.insertDir(dir));
    }

    /** 修改目录 */
    @PreAuthorize("@ss.hasPermi('taglibrary:dir:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody TlTagDir dir) {
        return toAjax(dirService.updateDir(dir));
    }

    /** 删除目录（目录下存在标签时拒绝） */
    @PreAuthorize("@ss.hasPermi('taglibrary:dir:remove')")
    @DeleteMapping("/{dirId}")
    public AjaxResult remove(@PathVariable Long dirId) {
        return toAjax(dirService.deleteDirById(dirId));
    }
}
