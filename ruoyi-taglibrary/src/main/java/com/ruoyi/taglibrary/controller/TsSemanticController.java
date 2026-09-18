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
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.taglibrary.domain.dto.SemanticReviewRequest;
import com.ruoyi.taglibrary.service.ITsBootstrapService;
import com.ruoyi.taglibrary.service.ITsSemanticService;

/**
 * 标签语义草稿维护（不含发布）
 */
@RestController
@RequestMapping("/taglibrary/semantic")
public class TsSemanticController extends BaseController {

    @Autowired
    private ITsSemanticService semanticService;
    @Autowired
    private ITsBootstrapService bootstrapService;

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/tag/list")
    public TableDataInfo tagList(@RequestParam Long libraryId) {
        startPage();
        return getDataTable(semanticService.selectTagSemanticByLibraryId(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/tag/{tagId}")
    public AjaxResult getTag(@PathVariable Long tagId) {
        return success(semanticService.selectTagSemanticByTagId(tagId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/tag")
    public AjaxResult saveTag(@RequestBody TsTagSemantic semantic) {
        return toAjax(semanticService.saveTagSemantic(semantic));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/tag/{tagId}/review")
    public AjaxResult reviewTag(@PathVariable Long tagId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewTagSemantic(tagId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/concept/list")
    public TableDataInfo conceptList(TsConcept query) {
        startPage();
        List<TsConcept> list = semanticService.selectConceptList(query);
        return getDataTable(list);
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/concept/{conceptId}")
    public AjaxResult getConcept(@PathVariable Long conceptId) {
        return success(semanticService.selectConceptById(conceptId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/concept")
    public AjaxResult saveConcept(@RequestBody TsConcept concept) {
        return toAjax(semanticService.saveConcept(concept));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/concept/{conceptId}/review")
    public AjaxResult reviewConcept(@PathVariable Long conceptId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewConcept(conceptId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/alias/list")
    public TableDataInfo aliasList(@RequestParam(required = false) String targetType,
                                   @RequestParam(required = false) String targetId) {
        startPage();
        return getDataTable(semanticService.selectAliasList(targetType, targetId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/alias")
    public AjaxResult saveAlias(@RequestBody TsAlias alias) {
        return toAjax(semanticService.saveAlias(alias));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/alias/{aliasId}/review")
    public AjaxResult reviewAlias(@PathVariable Long aliasId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewAlias(aliasId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/code-value/{tagId}")
    public AjaxResult listCodeValues(@PathVariable Long tagId) {
        return success(semanticService.selectCodeValuesByTagId(tagId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/code-value")
    public AjaxResult saveCodeValue(@RequestBody TsCodeValueSemantic row) {
        return toAjax(semanticService.saveCodeValue(row));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/bootstrap/export")
    public AjaxResult bootstrapExport(@RequestBody BootstrapExportRequest request) {
        return success(bootstrapService.exportFreeze(request));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/bootstrap/import")
    public AjaxResult bootstrapImport(@RequestBody BootstrapImportRequest request) {
        return success(bootstrapService.importDrafts(request));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/code-value/{tagId}/{code}/review")
    public AjaxResult reviewCodeValue(@PathVariable Long tagId, @PathVariable String code,
                                      @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewCodeValue(tagId, code, sourceRef));
    }
}
