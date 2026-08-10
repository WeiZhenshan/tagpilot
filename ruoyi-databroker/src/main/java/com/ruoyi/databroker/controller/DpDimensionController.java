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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.service.IDpDimensionService;

/**
 * 维表管理 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/databroker/dimension")
public class DpDimensionController extends BaseController {

    @Autowired
    private IDpDimensionService dimensionService;

    /** 分页查询维表列表 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:list')")
    @GetMapping("/list")
    public TableDataInfo list(DpDimensionTable query) {
        startPage();
        List<DpDimensionTable> list = dimensionService.selectDimensionList(query);
        return getDataTable(list);
    }

    /** 查询维表详情（含数据源名称与标准字段校验结果） */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:query')")
    @GetMapping("/{dimensionId}")
    public AjaxResult getInfo(@PathVariable Long dimensionId) {
        return success(dimensionService.getDimensionDetail(dimensionId));
    }

    /** 登记维表 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDimensionTable dimension) {
        return toAjax(dimensionService.insertDimension(dimension));
    }

    /** 修改维表（仅允许修改维表名称和备注） */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDimensionTable dimension) {
        return toAjax(dimensionService.updateDimension(dimension));
    }

    /** 批量逻辑删除维表 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:remove')")
    @DeleteMapping("/{dimensionIds}")
    public AjaxResult remove(@PathVariable Long[] dimensionIds) {
        return toAjax(dimensionService.deleteDimensionByIds(dimensionIds));
    }

    /** 启用/停用维表 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:status')")
    @PutMapping("/{dimensionId}/status")
    public AjaxResult updateStatus(@PathVariable Long dimensionId, @RequestBody DpDimensionTable dimension) {
        return toAjax(dimensionService.updateStatus(dimensionId, dimension.getStatus()));
    }

    /** 可用数据连接下拉 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:list')")
    @GetMapping("/options/datasources")
    public AjaxResult datasourceOptions() {
        return success(dimensionService.listDatasourceOptions());
    }

    /** 指定数据源下可登记的物理表下拉 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:list')")
    @GetMapping("/options/tables")
    public AjaxResult tableOptions(@RequestParam Long datasourceId) {
        return success(dimensionService.listTableOptions(datasourceId));
    }

    /** 新建弹窗标准字段预检 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:add')")
    @GetMapping("/options/fields")
    public AjaxResult fieldChecks(@RequestParam Long sourceTableId) {
        return success(dimensionService.checkTableFields(sourceTableId));
    }

    /** 物理码值分页预览 */
    @PreAuthorize("@ss.hasPermi('databroker:dimension:preview')")
    @GetMapping("/{dimensionId}/values")
    public TableDataInfo values(@PathVariable Long dimensionId,
                                @RequestParam(required = false) Integer pageNum,
                                @RequestParam(required = false) Integer pageSize) {
        return dimensionService.previewValues(dimensionId, pageNum, pageSize);
    }
}
