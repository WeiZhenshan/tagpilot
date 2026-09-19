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
import com.ruoyi.taglibrary.domain.TsBusinessTerm;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsConfusable;
import com.ruoyi.taglibrary.domain.TsTagExample;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.taglibrary.domain.dto.SemanticReviewRequest;
import com.ruoyi.taglibrary.domain.TsIndexBuild;
import com.ruoyi.taglibrary.service.ITsBootstrapService;
import com.ruoyi.taglibrary.service.ITsCatalogRuntimeService;
import com.ruoyi.taglibrary.service.ITsSemanticService;

/**
 * 标签语义草稿维护、快照发布与索引激活
 */
@RestController
@RequestMapping("/taglibrary/semantic")
public class TsSemanticController extends BaseController {

    @Autowired
    private ITsSemanticService semanticService;
    @Autowired
    private ITsBootstrapService bootstrapService;
    @Autowired
    private ITsCatalogRuntimeService catalogRuntimeService;

    @Autowired private com.ruoyi.taglibrary.mapper.TsCatalogSnapshotMapper snapshots;
    @Autowired private com.ruoyi.taglibrary.mapper.TsIndexBuildMapper builds;
    @Autowired private com.ruoyi.taglibrary.service.TsSnapshotArtifactStore artifacts;

    @Autowired private com.ruoyi.taglibrary.service.TsRuntimeClient runtimeClient;
    @Autowired private com.ruoyi.taglibrary.service.TsRetrievalService retrievalService;

    @Autowired private com.ruoyi.taglibrary.service.TsProfileService profileService;

    @Autowired private com.ruoyi.taglibrary.service.TsSnapshotAssembler snapshotAssembler;

    @Autowired private com.ruoyi.taglibrary.service.TsIndexMaintenanceService maintenance;
    @Autowired private com.ruoyi.taglibrary.mapper.TlTagMapper tagMapper;
    @Autowired private com.ruoyi.objectgroup.service.IDimensionCodeOptionService codeOptions;

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/library/{libraryId}/cleanup")
    public AjaxResult cleanup(@PathVariable Long libraryId) { return success(maintenance.cleanup(libraryId)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:publish')")
    @PostMapping("/library/{libraryId}/reconcile")
    public AjaxResult reconcile(@PathVariable Long libraryId) { return success(maintenance.reconcile(libraryId)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/catalog-overview")
    public AjaxResult overview(@RequestParam Long libraryId) {
        java.util.Map<String, Object> bundle = catalogRuntimeService.activeBundle(libraryId);
        java.util.List<Long> eligible = catalogRuntimeService.eligibleTagIds(libraryId, String.valueOf(bundle.get("snapshot_id")));
        return success(runtimeClient.post("/catalog-overview", com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("requirement", "overview", "library_id", libraryId, "build_id", bundle.get("build_id"), "eligible_tag_ids", eligible)));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:publish')")
    @GetMapping("/snapshot/quality")
    @org.springframework.transaction.annotation.Transactional(readOnly = true, isolation = org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public AjaxResult quality(@RequestParam Long libraryId) { return success(snapshotAssembler.assemble(libraryId, null).report); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/profile/{tagId}")
    public AjaxResult profile(@PathVariable Long tagId) { return success(profileService.latest(tagId)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/profile/{tagId}/aggregate")
    public AjaxResult aggregateProfile(@PathVariable Long tagId) { return success(profileService.aggregate(tagId)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @PostMapping("/retrieve")
    public AjaxResult retrieve(@RequestBody java.util.Map<String, String> request) {
        return success(retrievalService.retrieve(Long.valueOf(request.get("libraryId")), request.get("requirement")));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @PostMapping("/feedback")
    public AjaxResult feedback(@RequestBody com.ruoyi.taglibrary.domain.TsRetrievalFeedback request) { return toAjax(retrievalService.feedback(request)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/index-build/start")
    public AjaxResult startBuild(@RequestParam String snapshotId, @RequestParam String storeType) { return success(retrievalService.startBuild(snapshotId, storeType)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @GetMapping("/index-build/{buildId}/stats")
    public AjaxResult stats(@PathVariable String buildId) {
        if (!buildId.matches("[A-Za-z0-9_-]{1,48}") || builds.selectById(buildId) == null) throw new com.ruoyi.common.exception.ServiceException("构建不存在");
        return success(runtimeClient.get("/stats?build_id=" + buildId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/snapshot/list")
    public TableDataInfo snapshots(@RequestParam Long libraryId) {
        startPage(); return getDataTable(snapshots.selectByLibraryId(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/index-build/list")
    public AjaxResult builds(@RequestParam String snapshotId) { return success(builds.selectBySnapshotId(snapshotId)); }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/snapshot/{snapshotId}/download")
    public void download(@PathVariable String snapshotId, javax.servlet.http.HttpServletResponse response) throws java.io.IOException {
        com.ruoyi.taglibrary.domain.TsCatalogSnapshot snapshot = snapshots.selectById(snapshotId);
        if (snapshot == null) throw new com.ruoyi.common.exception.ServiceException("快照不存在");
        java.nio.file.Path path = artifacts.verifiedPath(snapshot);
        response.setContentType("application/x-ndjson;charset=UTF-8");
        response.setHeader("X-Content-Sha256", snapshot.getFileSha256());
        response.setHeader("X-Catalog-Content-Hash", snapshot.getContentHash());
        response.setHeader("Content-Disposition", "attachment; filename=\"" + path.getFileName() + "\"");
        java.nio.file.Files.copy(path, response.getOutputStream());
    }

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

    /** 复核时实时展示权威码义，禁止将其作为语义草稿修改。 */
    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/code-value/{tagId}/source")
    public AjaxResult codeValueSource(@PathVariable Long tagId) {
        com.ruoyi.taglibrary.domain.TlTag tag = tagMapper.selectTagById(tagId);
        if (tag == null) throw new com.ruoyi.common.exception.ServiceException("标签不存在或已删除");
        return success(codeOptions.listCodeOptions(tag.getLibraryId(), tag.getFieldName()));
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

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/term/list")
    public TableDataInfo termList(@RequestParam(required = false) String termNorm,
                                  @RequestParam(required = false) String termType) {
        startPage();
        return getDataTable(semanticService.selectTermList(termNorm, termType));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/term")
    public AjaxResult saveTerm(@RequestBody TsBusinessTerm term) {
        return toAjax(semanticService.saveTerm(term));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/term/{termId}/review")
    public AjaxResult reviewTerm(@PathVariable Long termId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewTerm(termId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/confusable/{tagId}")
    public AjaxResult listConfusable(@PathVariable Long tagId) {
        return success(semanticService.selectConfusableByTagId(tagId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/confusable")
    public AjaxResult saveConfusable(@RequestBody TsConfusable pair) {
        return toAjax(semanticService.saveConfusable(pair));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/confusable/{pairId}/review")
    public AjaxResult reviewConfusable(@PathVariable Long pairId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewConfusable(pairId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PostMapping("/confusable/generate")
    public AjaxResult generateConfusable(@RequestParam Long libraryId) {
        return success(semanticService.generateTimeFacetPairs(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/example/{tagId}")
    public AjaxResult listExamples(@PathVariable Long tagId) {
        return success(semanticService.selectExamplesByTagId(tagId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:edit')")
    @PutMapping("/example")
    public AjaxResult saveExample(@RequestBody TsTagExample example) {
        return toAjax(semanticService.saveExample(example));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:review')")
    @PostMapping("/example/{exampleId}/review")
    public AjaxResult reviewExample(@PathVariable Long exampleId, @RequestBody(required = false) SemanticReviewRequest request) {
        String sourceRef = request == null ? null : request.getSourceRef();
        return toAjax(semanticService.reviewExample(exampleId, sourceRef));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/eligible-tags")
    public AjaxResult eligibleTags(@RequestParam Long libraryId, @RequestParam(required = false) String snapshotId) {
        return success(catalogRuntimeService.eligibleTagIds(libraryId, snapshotId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:list')")
    @GetMapping("/snapshot/active")
    public AjaxResult activeSnapshot(@RequestParam Long libraryId) {
        return success(catalogRuntimeService.activeBundle(libraryId));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:publish')")
    @PostMapping("/snapshot/publish")
    public AjaxResult publish(@RequestParam Long libraryId, @RequestParam(required = false) String coverageNote) {
        return success(catalogRuntimeService.publish(libraryId, coverageNote));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PostMapping("/index-build")
    public AjaxResult registerBuild(@RequestBody TsIndexBuild build) {
        return success(catalogRuntimeService.registerBuild(build));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:bootstrap')")
    @PutMapping("/index-build/{buildId}/status")
    public AjaxResult updateBuild(@PathVariable String buildId, @RequestParam String status,
                                  @RequestParam(required = false) String evalSummary) {
        return success(catalogRuntimeService.updateBuildStatus(buildId, status, evalSummary));
    }

    @PreAuthorize("@ss.hasPermi('taglibrary:semantic:publish')")
    @PostMapping("/index-build/{buildId}/activate")
    public AjaxResult activate(@PathVariable String buildId) {
        return success(catalogRuntimeService.activate(buildId));
    }
}
