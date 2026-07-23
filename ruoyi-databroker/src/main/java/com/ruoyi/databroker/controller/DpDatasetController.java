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
import com.ruoyi.databroker.domain.DpDataset;
import com.ruoyi.databroker.domain.DpDatasetLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.CopyVersionRequest;
import com.ruoyi.databroker.domain.dto.PreviewRequest;
import com.ruoyi.databroker.domain.dto.PublishRequest;
import com.ruoyi.databroker.domain.dto.SaveDraftRequest;
import com.ruoyi.databroker.service.IDpDatasetService;

/**
 * 数据集管理 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/databroker/dataset")
public class DpDatasetController extends BaseController {

    @Autowired
    private IDpDatasetService datasetService;

    /** 目录 + 数据集树 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:list')")
    @GetMapping("/tree")
    public AjaxResult tree() {
        return success(datasetService.buildTree());
    }

    /** 查询数据集详情（含 defaultVersionId/latestVersionNo/数据源名） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/{datasetId}")
    public AjaxResult getInfo(@PathVariable Long datasetId) {
        return success(datasetService.selectDatasetById(datasetId));
    }

    /** 新增数据集（自动创建 V1 草稿） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:add')")
    @PostMapping
    public AjaxResult add(@RequestBody DpDataset dataset) {
        return toAjax(datasetService.insertDataset(dataset));
    }

    /** 修改数据集（编码/数据源不可改） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody DpDataset dataset) {
        return toAjax(datasetService.updateDataset(dataset));
    }

    /** 删除数据集（逻辑删） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:remove')")
    @DeleteMapping("/{datasetIds}")
    public AjaxResult remove(@PathVariable Long[] datasetIds) {
        datasetService.deleteDatasetByIds(datasetIds);
        return success();
    }

    /** 移动/排序数据集（拖拽排序用） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:edit')")
    @PutMapping("/{id}/move")
    public AjaxResult move(@PathVariable Long id, @RequestBody DpDataset dataset) {
        dataset.setDatasetId(id);
        return toAjax(datasetService.updateDatasetOrder(dataset));
    }

    /** 版本列表（不含 definition_json，附 isDefault） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/{datasetId}/versions")
    public AjaxResult versions(@PathVariable Long datasetId) {
        return success(datasetService.selectVersionList(datasetId));
    }

    /** 版本详情（definitionJson + fields 明细） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/version/{versionId}")
    public AjaxResult versionDetail(@PathVariable Long versionId) {
        return success(datasetService.selectVersionDetail(versionId));
    }

    /** 保存草稿（重写 definition_json/field/dependency + 校验） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:edit')")
    @PutMapping("/version")
    public AjaxResult saveDraft(@RequestBody SaveDraftRequest request) {
        return success(datasetService.saveDraft(request));
    }

    /** 复制版本（基于任意版本生成新 DRAFT） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:edit')")
    @PostMapping("/{datasetId}/version/copy")
    public AjaxResult copyVersion(@PathVariable Long datasetId, @RequestBody CopyVersionRequest request) {
        return success(datasetService.copyVersion(datasetId, request));
    }

    /** 发布版本 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:publish')")
    @PostMapping("/version/{versionId}/publish")
    public AjaxResult publish(@PathVariable Long versionId, @RequestBody PublishRequest request) {
        return toAjax(datasetService.publishVersion(versionId, request));
    }

    /** 下线版本 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:offline')")
    @PostMapping("/version/{versionId}/offline")
    public AjaxResult offline(@PathVariable Long versionId) {
        return toAjax(datasetService.offlineVersion(versionId));
    }

    /** 数据预览（重校验后 JDBC SELECT 启用字段 LIMIT 100） */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:preview')")
    @PostMapping("/preview")
    public AjaxResult preview(@RequestBody PreviewRequest request) {
        try {
            return success(datasetService.preview(request));
        } catch (Exception e) {
            return error(e.getMessage());
        }
    }

    /** 操作记录 */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/{datasetId}/logs")
    public TableDataInfo logs(@PathVariable Long datasetId, DpDatasetLog query) {
        startPage();
        List<DpDatasetLog> list = datasetService.listLogs(datasetId, query);
        return getDataTable(list);
    }

    /** 透传宽表分页查询（objectName 过滤），来自 dp_meta_table */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/datasource/{datasourceId}/tables")
    public TableDataInfo tables(@PathVariable Long datasourceId, DpMetaTable query) {
        startPage();
        List<DpMetaTable> list = datasetService.listTables(datasourceId, query);
        return getDataTable(list);
    }

    /** 透传字段列表，来自 dp_meta_column */
    @PreAuthorize("@ss.hasPermi('databroker:dataset:query')")
    @GetMapping("/table/{tableId}/columns")
    public AjaxResult columns(@PathVariable Long tableId) {
        return success(datasetService.listColumns(tableId));
    }
}
