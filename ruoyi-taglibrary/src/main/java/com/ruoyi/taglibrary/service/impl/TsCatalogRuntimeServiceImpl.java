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

    @Override
    public TsCatalogSnapshot publish(Long libraryId, String coverageNote) {
        if (libraryId == null) {
            throw new ServiceException("标签库不能为空");
        }
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        List<TsTagSemantic> semantics = tagSemanticMapper.selectByLibraryId(libraryId);
        List<Map<String, Object>> excluded = new ArrayList<Map<String, Object>>();
        List<Map<String, Object>> tagRows = new ArrayList<Map<String, Object>>();
        Set<Long> publishedIds = new HashSet<Long>();
        for (TsTagSemantic semantic : semantics) {
            if ("ID_KEY".equals(semantic.getSemanticType())) {
                continue;
            }
            if (!REVIEWED.equals(semantic.getReviewStatus())) {
                excluded.add(issue(semantic.getTagId(), "NOT_REVIEWED", "未复核，不进入生产快照"));
                continue;
            }
            if (semantic.getConceptId() == null) {
                excluded.add(issue(semantic.getTagId(), "NO_CONCEPT", "未挂接概念"));
                continue;
            }
            TsConcept concept = conceptMapper.selectConceptById(semantic.getConceptId());
            if (concept == null || !REVIEWED.equals(concept.getReviewStatus()) || !"0".equals(concept.getStatus())) {
                excluded.add(issue(semantic.getTagId(), "CONCEPT_NOT_READY", "概念未启用或未复核"));
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("kind", "tag");
            row.put("tag_id", semantic.getTagId());
            row.put("field_name", semantic.getFieldName());
            row.put("name", semantic.getTagName());
            row.put("semantic_type", semantic.getSemanticType());
            row.put("family_key", semantic.getFamilyKey());
            row.put("concept_id", semantic.getConceptId());
            tagRows.add(row);
            publishedIds.add(semantic.getTagId());
        }
        if (tagRows.isEmpty()) {
            throw new ServiceException("没有可发布的 REVIEWED 业务标签");
        }
        Integer maxNo = snapshotMapper.selectMaxSnapshotNo(libraryId);
        int nextNo = maxNo == null ? 1 : maxNo.intValue() + 1;
        String snapshotId = "L" + libraryId + "-" + new SimpleDateFormat("yyyyMMdd").format(new Date()) + "-"
                + String.format("%03d", nextNo);
        Map<String, Object> meta = new LinkedHashMap<String, Object>();
        meta.put("kind", "meta");
        meta.put("library_id", libraryId);
        meta.put("schema_version", "v1");
        meta.put("scope", "PILOT");
        meta.put("coverage_note", StringUtils.isEmpty(coverageNote) ? "分阶段发布，不得把范围内覆盖写成全库100%" : coverageNote);
        List<String> lines = new ArrayList<String>();
        lines.add(toJson(meta));
        for (Map<String, Object> row : tagRows) {
            lines.add(toJson(row));
        }
        String jsonl = StringUtils.join(lines.toArray(new String[0]), "\n") + "\n";
        List<Map<String, Object>> hashRows = new ArrayList<Map<String, Object>>();
        hashRows.add(meta);
        hashRows.addAll(tagRows);
        String hash = com.ruoyi.taglibrary.service.TsSnapshotCanonicalizer.contentHash(hashRows);
        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("published_tag_ids", publishedIds);
        report.put("excluded", excluded);
        report.put("tag_count", tagRows.size());
        report.put("coverage", tagRows.size() + "/969");
        report.put("scope", "PILOT");
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot();
        snapshot.setSnapshotId(snapshotId);
        snapshot.setLibraryId(libraryId);
        snapshot.setSnapshotNo(Integer.valueOf(nextNo));
        snapshot.setTagCount(Integer.valueOf(tagRows.size()));
        snapshot.setContentHash(hash);
        snapshot.setStorageUri("memory://" + snapshotId);
        snapshot.setSchemaVersion("v1");
        snapshot.setStatus("PUBLISHED");
        snapshot.setQualityReport(toJson(report));
        snapshot.setSourceManifest("{\"library_id\":" + libraryId + ",\"library_name\":\"" + library.getLibraryName() + "\"}");
        snapshot.setPublishBy(username());
        snapshot.setPublishTime(new Date());
        snapshot.setCreateBy(username());
        snapshot.setJsonl(jsonl);
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
            if (snapshot == null) {
                throw new ServiceException("快照不存在，拒绝服务");
            }
            Set<Long> snapIds = parsePublishedIds(snapshot.getQualityReport());
            List<Long> inter = new ArrayList<Long>();
            for (Long id : current) {
                if (snapIds.contains(id)) {
                    inter.add(id);
                }
            }
            current = inter;
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
        TsCatalogSnapshot snapshot = snapshotMapper.selectById(build.getSnapshotId());
        if (snapshot == null || (!"PUBLISHED".equals(snapshot.getStatus()) && !"ACTIVE".equals(snapshot.getStatus()))) {
            throw new ServiceException("只能对已发布快照登记构建");
        }
        if (StringUtils.isEmpty(build.getStatus())) {
            build.setStatus("BUILDING");
        }
        if (StringUtils.isEmpty(build.getStoreType())) {
            build.setStoreType("LOCAL");
        }
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
        if (!"READY".equals(build.getStatus())) {
            throw new ServiceException("仅 READY 构建可以激活");
        }
        TsCatalogSnapshot snapshot = snapshotMapper.selectById(build.getSnapshotId());
        if (snapshot == null) {
            throw new ServiceException("快照不存在");
        }
        snapshotMapper.retireActive(snapshot.getLibraryId(), snapshot.getSnapshotId());
        snapshot.setStatus("ACTIVE");
        snapshotMapper.updateSnapshot(snapshot);
        indexBuildMapper.retireActiveBySnapshotId(snapshot.getSnapshotId());
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
        bundle.put("doc_template_version", build.getDocTemplateVersion());
        bundle.put("embedding_model", build.getEmbeddingModel());
        bundle.put("store_type", build.getStoreType());
        return bundle;
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
