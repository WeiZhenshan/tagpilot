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
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.service.IDpDataSourceCatalogService;

/**
 * 数据源目录（目录树）Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/databroker/catalog")
public class DpDataSourceCatalogController extends BaseController {

    @Autowired
    private IDpDataSourceCatalogService catalogService;

    /** 目录列表（扁平，前端 handleTree 构建树） */
    @PreAuthorize("@ss.hasPermi('databroker:catalog:list')")
    @GetMapping("/list")
    public AjaxResult list(DpDataSourceCatalog catalog) {
        List<DpDataSourceCatalog> list = catalogService.selectCatalogList(catalog);
        return success(list);
    }

    /** 目录详情 */
    @PreAuthorize("@ss.hasPermi('databroker:catalog:query')")
    @GetMapping("/{catalogId}")
    public AjaxResult getInfo(@PathVariable Long catalogId) {
        return success(catalogService.selectCatalogById(catalogId));
    }

    /** 新增目录 */
    @PreAuthorize("@ss.hasPermi('databroker:catalog:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDataSourceCatalog catalog) {
        return toAjax(catalogService.insertCatalog(catalog));
    }

    /** 修改目录 */
    @PreAuthorize("@ss.hasPermi('databroker:catalog:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDataSourceCatalog catalog) {
        return toAjax(catalogService.updateCatalog(catalog));
    }

    /** 删除目录（空目录才允许） */
    @PreAuthorize("@ss.hasPermi('databroker:catalog:remove')")
    @DeleteMapping("/{catalogId}")
    public AjaxResult remove(@PathVariable Long catalogId) {
        return toAjax(catalogService.deleteCatalogById(catalogId));
    }
}
