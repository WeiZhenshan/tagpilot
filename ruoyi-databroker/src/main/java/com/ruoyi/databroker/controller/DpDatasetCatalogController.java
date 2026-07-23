package com.ruoyi.databroker.controller;

import java.util.List;
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
import com.ruoyi.databroker.domain.DpDatasetCatalog;
import com.ruoyi.databroker.service.IDpDatasetCatalogService;

/**
 * 数据集目录（目录树）Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/databroker/dataset/catalog")
public class DpDatasetCatalogController extends BaseController {

    @Autowired
    private IDpDatasetCatalogService catalogService;

    /** 目录列表（扁平，前端 handleTree 构建树） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:list')")
    @GetMapping("/list")
    public AjaxResult list(DpDatasetCatalog catalog) {
        List<DpDatasetCatalog> list = catalogService.selectCatalogList(catalog);
        return success(list);
    }

    /** 目录详情 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:list')")
    @GetMapping("/{catalogId}")
    public AjaxResult getInfo(@PathVariable Long catalogId) {
        return success(catalogService.selectCatalogById(catalogId));
    }

    /** 新增目录 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDatasetCatalog catalog) {
        return toAjax(catalogService.insertCatalog(catalog));
    }

    /** 修改目录 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDatasetCatalog catalog) {
        return toAjax(catalogService.updateCatalog(catalog));
    }

    /** 删除目录（空目录才允许） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:remove')")
    @DeleteMapping("/{catalogId}")
    public AjaxResult remove(@PathVariable Long catalogId) {
        return toAjax(catalogService.deleteCatalogById(catalogId));
    }

    /** 移动/排序目录（拖拽排序用） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:catalog:edit')")
    @PutMapping("/move")
    public AjaxResult move(@RequestBody DpDatasetCatalog catalog) {
        return toAjax(catalogService.updateCatalogOrder(catalog));
    }
}
