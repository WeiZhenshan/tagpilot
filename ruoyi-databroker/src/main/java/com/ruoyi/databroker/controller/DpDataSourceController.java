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
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.service.IDpDataSourceService;

@RestController
@RequestMapping("/databroker/datasource")
public class DpDataSourceController extends BaseController {

    @Autowired
    private IDpDataSourceService dataSourceService;

    /** 目录 + 数据源树 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:list')")
    @GetMapping("/tree")
    public AjaxResult tree() {
        return success(dataSourceService.buildTree());
    }

    /** 查询数据源详情 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/{id}")
    public AjaxResult getInfo(@PathVariable Long id) {
        return success(dataSourceService.selectDataSourceById(id));
    }

    /** 新增数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDataSource dataSource) {
        return toAjax(dataSourceService.insertDataSource(dataSource));
    }

    /** 修改数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDataSource dataSource) {
        return toAjax(dataSourceService.updateDataSource(dataSource));
    }

    /** 删除数据源 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:remove')")
    @DeleteMapping("/{ids}")
    public AjaxResult remove(@PathVariable Long[] ids) {
        dataSourceService.deleteDataSourceByIds(ids);
        return success();
    }

    /** 测试连接 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:test')")
    @PostMapping("/test")
    public AjaxResult test(@RequestBody DpDataSource dataSource) {
        try {
            return success(dataSourceService.testConnection(dataSource));
        } catch (Exception e) {
            return error(e.getMessage());
        }
    }

    /** 同步元数据 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:sync')")
    @PostMapping("/{id}/sync")
    public AjaxResult sync(@PathVariable Long id) {
        try {
            return success(dataSourceService.syncMetadata(id));
        } catch (Exception e) {
            return error(e.getMessage());
        }
    }

    /** 表信息列表 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:list')")
    @GetMapping("/{id}/tables")
    public TableDataInfo tables(@PathVariable Long id, DpMetaTable query) {
        startPage();
        List<DpMetaTable> list = dataSourceService.listTables(id, query);
        return getDataTable(list);
    }

    /** 字段信息 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/table/{tableId}/columns")
    public AjaxResult columns(@PathVariable Long tableId) {
        return success(dataSourceService.listColumns(tableId));
    }

    /** 修改中文名 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:edit')")
    @PutMapping("/table/{tableId}/cnName")
    public AjaxResult updateCnName(@PathVariable Long tableId, @RequestBody DpMetaTable table) {
        return toAjax(dataSourceService.updateTableCnName(tableId, table.getCnName()));
    }

    /** 操作记录 */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:query')")
    @GetMapping("/{id}/logs")
    public TableDataInfo logs(@PathVariable Long id, DpDataSourceLog query) {
        startPage();
        List<DpDataSourceLog> list = dataSourceService.listLogs(id, query);
        return getDataTable(list);
    }

    /** 移动/排序数据源（拖拽排序用） */
    @PreAuthorize("@ss.hasPermi('databroker:datasource:edit')")
    @PutMapping("/{id}/move")
    public AjaxResult move(@PathVariable Long id, @RequestBody DpDataSource dataSource) {
        dataSource.setDatasourceId(id);
        return toAjax(dataSourceService.updateDataSourceOrder(dataSource));
    }
}
