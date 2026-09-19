package com.ruoyi.taglibrary.service.impl;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsIndexBuild;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsCatalogSnapshotMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsIndexBuildMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import com.ruoyi.taglibrary.service.ITsCatalogRuntimeService;

@Service
public class TsCatalogRuntimeServiceImpl implements ITsCatalogRuntimeService {

    private static final String REVIEWED = "REVIEWED";
    private static final String STATUS_ONLINE = "2";
    private static final String AVAILABLE = "AVAILABLE";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TsTagSemanticMapper tagSemanticMapper;
    @Autowired
    private TsConceptMapper conceptMapper;
    @Autowired
    private TsCatalogSnapshotMapper snapshotMapper;
    @Autowired
    private TsIndexBuildMapper indexBuildMapper;
    @Autowired
    private DpOnlineVersionResolver versionResolver;

    @Autowired private com.ruoyi.taglibrary.service.ITsBootstrapService bootstrap;
    @Autowired private com.ruoyi.taglibrary.service.TsRuntimeClient runtime;
    @Autowired private com.ruoyi.taglibrary.service.TsSnapshotAssembler assembler;
    @Autowired private com.ruoyi.taglibrary.service.TsSnapshotArtifactStore artifacts;
    @Autowired private com.ruoyi.taglibrary.service.TsIndexMaintenanceService maintenance;

    @Override
    @Transactional(isolation = org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public TsCatalogSnapshot publish(Long libraryId, String coverageNote) {
        if (libraryId == null || libraryMapper.selectLibraryById(libraryId) == null) throw new ServiceException("标签库不存在");
        snapshotMapper.lockLibrary(libraryId);
        com.ruoyi.taglibrary.service.TsSnapshotAssembler.Result assembled = assembler.assemble(libraryId, coverageNote);
        if (assembled.tagIds.isEmpty()) throw new ServiceException("没有通过发布门禁的业务标签，请查看质量报告");
        Integer maxNo = snapshotMapper.selectMaxSnapshotNo(libraryId);
        int nextNo = maxNo == null ? 1 : maxNo + 1;
        String snapshotId = "L" + libraryId + "-" + new SimpleDateFormat("yyyyMMdd").format(new Date()) + "-" + String.format("%03d", nextNo);
        String hash = com.ruoyi.taglibrary.service.TsSnapshotCanonicalizer.contentHash(assembled.rows);
        assembled.rows.get(0).put("snapshot_id", snapshotId);
        assembled.rows.get(0).put("snapshot_no", nextNo);
        assembled.rows.get(0).put("content_hash", hash);
        StringBuilder jsonl = new StringBuilder();
        for (Map<String, Object> row : assembled.rows) jsonl.append(toJson(row)).append('\n');
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot();
        snapshot.setSnapshotId(snapshotId); snapshot.setLibraryId(libraryId); snapshot.setSnapshotNo(nextNo);
        snapshot.setTagCount(assembled.tagIds.size()); snapshot.setConceptCount(assembled.concepts);
        snapshot.setCodeValueCount(assembled.codes); snapshot.setAliasCount(assembled.aliases);
        snapshot.setContentHash(hash); snapshot.setSchemaVersion("v1"); snapshot.setStatus("PUBLISHED");
        snapshot.setQualityReport(toJson(assembled.report)); snapshot.setSourceManifest(toJson(assembled.sourceManifest));
        snapshot.setPublishBy(username()); snapshot.setCreateBy(username()); snapshot.setPublishTime(new Date());
        artifacts.write(snapshot, jsonl.toString());
        // 文件先于数据库提交可用。事务失败留下未登记文件供对账，不覆盖或暴露它。
        snapshotMapper.insertSnapshot(snapshot);
        return snapshot;
    }

    @Override
    public List<Long> eligibleTagIds(Long libraryId, String snapshotId) {
        if (libraryId == null) {
            throw new ServiceException("标签库不能为空");
        }
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (library.getDatasetId() == null) {
            throw new ServiceException("无法取得资格，数据集缺失");
        }
        DpResolvedVersion version = versionResolver.resolve(library.getDatasetId());
        if (version == null) {
            throw new ServiceException("无法取得资格，无在线数据集版本");
        }
        Set<String> enabled = new HashSet<String>();
        List<DpResolvedField> fields = versionResolver.listEnabledFields(version.getVersionId());
        if (fields != null) {
            for (DpResolvedField field : fields) {
                if (field.getFieldAlias() != null) {
                    enabled.add(field.getFieldAlias());
                }
            }
        }
        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> tags = tagMapper.selectTagList(query);
        List<Long> current = new ArrayList<Long>();
        for (TlTag tag : tags) {
            if ("1".equals(tag.getIsObjectKey())) {
                continue;
            }
            if (!STATUS_ONLINE.equals(tag.getStatus()) || !AVAILABLE.equals(tag.getSourceStatus())) {
                continue;
            }
            if (!enabled.contains(tag.getFieldName())) {
                continue;
            }
            current.add(tag.getTagId());
        }
        if (StringUtils.isNotEmpty(snapshotId)) {
            TsCatalogSnapshot snapshot = snapshotMapper.selectById(snapshotId);
            if (snapshot == null || !libraryId.equals(snapshot.getLibraryId())) {
                throw new ServiceException("快照不存在或不属于该库，拒绝服务");
            }
            Set<Long> snapIds = parsePublishedIds(snapshot.getQualityReport());
            List<Long> inter = new ArrayList<Long>();
            for (Long id : current) {
                if (snapIds.contains(id)) {
                    inter.add(id);
                }
            }
            current = compatibleIds(libraryId, snapshot, inter);
        }
        if (current.isEmpty()) {
            throw new ServiceException("无法取得资格，拒绝服务");
        }
        return current;
    }

    @Override
    public TsCatalogSnapshot activeSnapshot(Long libraryId) {
        return snapshotMapper.selectActiveByLibraryId(libraryId);
    }

    @Override
    public TsIndexBuild registerBuild(TsIndexBuild build) {
        if (build == null || StringUtils.isEmpty(build.getBuildId()) || StringUtils.isEmpty(build.getSnapshotId())) {
            throw new ServiceException("build_id 与 snapshot_id 不能为空");
        }
        if (!build.getBuildId().matches("[A-Za-z0-9_-]{1,48}")) throw new ServiceException("build_id 格式非法");
        TsCatalogSnapshot snapshot = snapshotMapper.selectById(build.getSnapshotId());
        if (snapshot == null || (!"PUBLISHED".equals(snapshot.getStatus()) && !"ACTIVE".equals(snapshot.getStatus()))) {
            throw new ServiceException("只能对已发布快照登记构建");
        }
        if (build.getStatus() != null && !"BUILDING".equals(build.getStatus())) throw new ServiceException("构建必须从 BUILDING 开始");
        build.setStatus("BUILDING");
        if (StringUtils.isEmpty(build.getStoreType())) {
            build.setStoreType("LOCAL");
        }
        if (!"LOCAL".equals(build.getStoreType()) && !"MILVUS".equals(build.getStoreType())) throw new ServiceException("不支持的存储模式");
        if (StringUtils.isEmpty(build.getDocTemplateVersion())) {
            build.setDocTemplateVersion("tpl1");
        }
        if (StringUtils.isEmpty(build.getArtifactUri())) {
            build.setArtifactUri("file:///data/tag-index/" + build.getSnapshotId() + "/" + build.getBuildId());
        }
        build.setCreateBy(username());
        indexBuildMapper.insertBuild(build);
        return build;
    }

    @Override
    public TsIndexBuild updateBuildStatus(String buildId, String status, String evalSummary) {
        TsIndexBuild existing = indexBuildMapper.selectById(buildId);
        if (existing == null) {
            throw new ServiceException("构建不存在");
        }
        if ("ACTIVE".equals(status)) {
            throw new ServiceException("不能通过状态接口直接设置为 ACTIVE");
        }
        if (!"BUILDING".equals(existing.getStatus()) || !("READY".equals(status) || "FAILED".equals(status))) throw new ServiceException("非法构建状态迁移");
        if ("READY".equals(status)) {
            Map<String, Object> stats = runtime.get("/stats?build_id=" + buildId);
            TsCatalogSnapshot snapshot = snapshotMapper.selectById(existing.getSnapshotId());
            if (!Boolean.TRUE.equals(stats.get("id_reconciled")) || existing.getDocIdHash() == null || !existing.getDocIdHash().equals(stats.get("doc_id_hash"))
                    || !existing.getSnapshotId().equals(stats.get("snapshot_id")) || !existing.getStoreType().equals(stats.get("store_type"))
                    || !snapshot.getContentHash().equals(stats.get("content_hash"))) throw new ServiceException("READY 前置对账失败");
        }
        existing.setStatus(status);
        existing.setEvalSummary(evalSummary);
        existing.setUpdateBy(username());
        indexBuildMapper.updateBuild(existing);
        return existing;
    }

    @Override
    @Transactional
    public TsIndexBuild activate(String buildId) {
        TsIndexBuild build = indexBuildMapper.selectById(buildId);
        if (build == null) {
            throw new ServiceException("构建不存在");
        }
        if (!"READY".equals(build.getStatus()) && !"RETIRED".equals(build.getStatus())) {
            throw new ServiceException("仅 READY 构建可以激活");
        }
        TsCatalogSnapshot snapshot = snapshotMapper.selectById(build.getSnapshotId());
        if (snapshot == null) {
            throw new ServiceException("快照不存在");
        }
        snapshotMapper.lockLibrary(snapshot.getLibraryId());
        // 锁后重新读取，防止并发激活使用陈旧状态。
        build = indexBuildMapper.selectById(buildId);
        if (!("READY".equals(build.getStatus()) || "RETIRED".equals(build.getStatus()))) throw new ServiceException("构建状态已变化");
        Map<String, Object> stats = runtime.get("/stats?build_id=" + buildId);
        if (!Boolean.TRUE.equals(stats.get("id_reconciled")) || (build.getDocIdHash() == null || !build.getDocIdHash().equals(stats.get("doc_id_hash")))) throw new ServiceException("索引行集对账失败");
        final Long activationLibraryId = snapshot.getLibraryId();
        final Map<String, Object> attemptedActivation = activationPayload(snapshot, build);
        if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(new org.springframework.transaction.support.TransactionSynchronization() {
                @Override public void afterCompletion(int status) {
                    if (status != STATUS_COMMITTED) {
                        try {
                            // 回滚已释放原库锁，须在新事务重新取锁并读取当前权威状态；不能覆盖随后成功的激活。
                            maintenance.reconcile(activationLibraryId);
                        }
                        catch (Exception e) { org.slf4j.LoggerFactory.getLogger(TsCatalogRuntimeServiceImpl.class).error("语义索引激活补偿失败，须按数据库 ACTIVE 对账恢复"); }
                    }
                }
            });
        }
        // 必须先登记补偿：RPC 超时不代表远端 alias 没有切换。
        runtime.post("/activate", attemptedActivation);
        indexBuildMapper.retireActiveByLibraryId(snapshot.getLibraryId());
        snapshotMapper.retireActive(snapshot.getLibraryId(), snapshot.getSnapshotId());
        snapshot.setStatus("ACTIVE");
        snapshotMapper.updateSnapshot(snapshot);
        build.setStatus("ACTIVE");
        build.setMilvusAlias("tag_docs_active_l" + snapshot.getLibraryId());
        indexBuildMapper.updateBuild(build);
        return build;
    }

    @Override
    public Map<String, Object> activeBundle(Long libraryId) {
        TsCatalogSnapshot snapshot = snapshotMapper.selectActiveByLibraryId(libraryId);
        if (snapshot == null) {
            throw new ServiceException("库内无 ACTIVE 快照");
        }
        TsIndexBuild build = indexBuildMapper.selectActiveBySnapshotId(snapshot.getSnapshotId());
        if (build == null) {
            throw new ServiceException("库内无 ACTIVE 索引构建");
        }
        Map<String, Object> bundle = new LinkedHashMap<String, Object>();
        bundle.put("snapshot_id", snapshot.getSnapshotId());
        bundle.put("build_id", build.getBuildId());
        bundle.put("milvus_collection", build.getMilvusCollection());
        bundle.put("artifact_uri", build.getArtifactUri());
        bundle.put("artifact_hash", build.getArtifactHash());
        bundle.put("doc_template_version", build.getDocTemplateVersion());
        bundle.put("embedding_model", build.getEmbeddingModel());
        bundle.put("store_type", build.getStoreType());
        return bundle;
    }

    @SuppressWarnings("unchecked")
    private List<Long> compatibleIds(Long libraryId, TsCatalogSnapshot snapshot, List<Long> ids) {
        try {
            Map<Long, Map<String, Object>> frozen = new java.util.HashMap<>();
            for (String line : java.nio.file.Files.readAllLines(artifacts.verifiedPath(snapshot), java.nio.charset.StandardCharsets.UTF_8)) {
                Map<String, Object> row = MAPPER.readValue(line, Map.class);
                if ("tag".equals(row.get("kind"))) frozen.put(Long.valueOf(String.valueOf(row.get("tag_id"))), row);
            }
            com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest request = new com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest();
            request.setLibraryId(libraryId); request.setTagIds(ids);
            com.ruoyi.taglibrary.domain.dto.BootstrapExportResult freeze = bootstrap.exportFreeze(request);
            if (!freeze.getIssues().isEmpty()) throw new ServiceException("当前来源存在异常，拒绝检索");
            Map<Long, Map<String, Object>> tags = new java.util.HashMap<>();
            Map<Long, List<Map<String, Object>>> codes = new java.util.HashMap<>();
            for (String line : freeze.getJsonl().split("\n")) {
                Map<String, Object> row = MAPPER.readValue(line, Map.class);
                if ("tag".equals(row.get("kind"))) tags.put(Long.valueOf(String.valueOf(row.get("tag_id"))), row);
                if ("code_value".equals(row.get("kind"))) codes.computeIfAbsent(Long.valueOf(String.valueOf(row.get("tag_id"))), k -> new ArrayList<>()).add(row);
            }
            List<Long> compatible = new ArrayList<>();
            for (Long id : ids) {
                Map<String, Object> old = frozen.get(id), now = tags.get(id);
                if (old == null || now == null) continue;
                String basis = com.ruoyi.taglibrary.service.TsSnapshotAssembler.basisHash(now, codes.getOrDefault(id, java.util.Collections.emptyList()));
                if (!basis.equals(old.get("basis_hash")) || !java.util.Objects.equals(old.get("binding"), now.get("binding"))) continue;
                Long cid = Long.valueOf(String.valueOf(old.get("concept_id"))); Set<Long> seen = new HashSet<>(); boolean enabled = true;
                while (cid != null && cid != 0) {
                    if (!seen.add(cid)) { enabled = false; break; }
                    TsConcept concept = conceptMapper.selectConceptById(cid);
                    if (concept == null || !"0".equals(concept.getStatus())) { enabled = false; break; }
                    cid = concept.getParentId();
                }
                if (enabled) compatible.add(id);
            }
            return compatible;
        } catch (ServiceException e) { throw e; } catch (Exception e) { throw new ServiceException("当前资格与快照依据校验失败，拒绝服务"); }
    }

    private Map<String, Object> activationPayload(TsCatalogSnapshot snapshot, TsIndexBuild build) {
        return com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("build_id", build.getBuildId(), "snapshot_id", snapshot.getSnapshotId(), "library_id", snapshot.getLibraryId(), "store_type", build.getStoreType());
    }

    private Set<Long> parsePublishedIds(String qualityReport) {
        Set<Long> ids = new HashSet<Long>();
        if (StringUtils.isEmpty(qualityReport)) {
            return ids;
        }
        try {
            Map<?, ?> report = MAPPER.readValue(qualityReport, Map.class);
            Object raw = report.get("published_tag_ids");
            if (raw instanceof Iterable) {
                for (Object item : (Iterable<?>) raw) {
                    ids.add(Long.valueOf(String.valueOf(item)));
                }
            }
        } catch (Exception e) {
            throw new ServiceException("快照资格清单无法解析");
        }
        return ids;
    }

    private Map<String, Object> issue(Long tagId, String code, String message) {
        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("tag_id", tagId);
        row.put("code", code);
        row.put("message", message);
        return row;
    }

    private String toJson(Object row) {
        try {
            return MAPPER.writeValueAsString(row);
        } catch (Exception e) {
            throw new ServiceException("序列化失败");
        }
    }

    private String username() {
        try {
            return SecurityUtils.getUsername();
        } catch (Exception e) {
            return "system";
        }
    }
}
