package com.ruoyi.taglibrary.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.dto.DimensionSetRequest;
import com.ruoyi.taglibrary.service.ITlTagLibraryDimensionService;

/**
 * 标签库默认码表（维表关联）Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/taglibrary/library")
public class TlTagLibraryDimensionController extends BaseController {

    @Autowired
    private ITlTagLibraryDimensionService dimensionService;

    /** 候选维表分页（全部已登记维表；非同源/停用也返回，前端禁用复选框） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:dimension:list')")
    @GetMapping("/{libraryId}/dimensions/candidates")
    public TableDataInfo candidates(@PathVariable Long libraryId,
                                    @RequestParam(required = false) String dimensionName) {
        startPage();
        return getDataTable(dimensionService.selectCandidates(libraryId, dimensionName));
    }

    /** 该库全部已关联维表ID数组（跨分页回显用） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:dimension:list')")
    @GetMapping("/{libraryId}/dimensions/selected")
    public AjaxResult selected(@PathVariable Long libraryId) {
        return success(dimensionService.selectSelectedDimensionIds(libraryId));
    }

    /** 多选覆盖保存默认码表，body { dimensionIds: [] }，空数组=清空 */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:dimension:set')")
    @PutMapping("/{libraryId}/dimensions")
    public AjaxResult save(@PathVariable Long libraryId, @RequestBody DimensionSetRequest request) {
        if (request == null || request.getDimensionIds() == null) {
            throw new ServiceException("请提交 dimensionIds 数组");
        }
        return success(dimensionService.saveDimensions(libraryId, request.getDimensionIds()));
    }

    /** 引用了某维表的标签库列表（维表详情抽屉用，不分页） */
    @PreAuthorize("@ss.hasPermi('taglibrary:library:dimension:list')")
    @GetMapping("/dimension/{dimensionId}/libraries")
    public AjaxResult libraries(@PathVariable Long dimensionId) {
        return success(dimensionService.selectLibrariesByDimensionId(dimensionId));
    }
}
