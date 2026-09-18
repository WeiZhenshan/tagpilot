package com.ruoyi.taglibrary.service.impl;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportResult;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportResult;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import com.ruoyi.taglibrary.service.ITsBootstrapService;

/**
 * 同批冻结导出：一次读取绑定码表，不回退 tl_tag_code_value。
 */
@Service
public class TsBootstrapExportService implements ITsBootstrapService {

    private static final Pattern TABLE_NAME_PATTERN = Pattern.compile("^[A-Za-z0-9_]+$");
    private static final String STATUS_ENABLED = "0";
    private static final String DEL_FLAG_EXIST = "0";
    private static final String TAG_TYPE_OPTION = "选项型";
    private static final String TAG_TYPE_BOOL = "布尔型";
    private static final String STATUS_DRAFT = "DRAFT";
    private static final String STATUS_REVIEWED = "REVIEWED";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DpOnlineVersionResolver versionResolver;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DataBrokerProperties properties;
    @Autowired
    private TsTagSemanticMapper tagSemanticMapper;
    @Autowired
    private TsCodeValueSemanticMapper codeValueMapper;

    @Override
    public BootstrapExportResult exportFreeze(BootstrapExportRequest request) {
        if (request == null || request.getLibraryId() == null) {
            throw new ServiceException("标签库不能为空");
        }
        Long libraryId = request.getLibraryId();
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (library.getDatasetId() == null) {
            throw new ServiceException("标签库未关联数据集");
        }
        DpResolvedVersion version = versionResolver.resolve(library.getDatasetId());
        if (version == null) {
            throw new ServiceException("数据集无可用在线版本");
        }
        List<DpResolvedField> enabledFields = versionResolver.listEnabledFields(version.getVersionId());
        Map<String, DpResolvedField> fieldByAlias = new HashMap<String, DpResolvedField>();
        for (DpResolvedField field : enabledFields) {
            if (field.getFieldAlias() != null) {
                fieldByAlias.put(field.getFieldAlias(), field);
            }
        }

        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> tags = filterTags(tagMapper.selectTagList(query), request);
        List<TlTagDir> dirs = dirMapper.selectDirList(libraryId);
        Map<Long, TlTagDir> dirMap = new HashMap<Long, TlTagDir>();
        for (TlTagDir dir : dirs) {
            dirMap.put(dir.getDirId(), dir);
        }

        List<Map<String, Object>> issues = new ArrayList<Map<String, Object>>();
        Map<String, MergedCode> codes = loadMergedCodes(libraryId, version, fieldByAlias, issues);

        List<Map<String, Object>> domainRows = buildDomains(dirs, dirMap);
        List<Map<String, Object>> tagRows = new ArrayList<Map<String, Object>>();
        List<Map<String, Object>> codeRows = new ArrayList<Map<String, Object>>();
        for (TlTag tag : tags) {
            DpResolvedField field = fieldByAlias.get(tag.getFieldName());
            boolean objectKey = "1".equals(tag.getIsObjectKey());
            if (field == null) {
                issues.add(issue("FIELD_NOT_ENABLED", tag.getFieldName(), "字段未在当前在线版本启用"));
            }
            tagRows.add(buildTagRow(tag, field, version, dirMap, objectKey));
            List<MergedCode> fieldCodes = findCodes(codes, tag.getFieldName());
            if (fieldCodes.isEmpty() && isCodeTag(tag) && !objectKey) {
                issues.add(issue("CODE_UNMAPPED", tag.getFieldName(), "选项/布尔标签未匹配到活动码表"));
            }
            for (MergedCode code : fieldCodes) {
                codeRows.add(buildCodeRow(tag.getTagId(), code));
            }
        }

        Map<String, Object> meta = new LinkedHashMap<String, Object>();
        meta.put("kind", "meta");
        meta.put("library_id", libraryId);
        meta.put("library_name", library.getLibraryName());
        meta.put("tag_object", library.getTagObject());
        meta.put("schema_version", "v1");
        Map<String, Object> sourceManifest = new LinkedHashMap<String, Object>();
        sourceManifest.put("dataset_id", library.getDatasetId());
        sourceManifest.put("version_id", version.getVersionId());
        sourceManifest.put("version_no", version.getVersionNo());
        sourceManifest.put("version_name", version.getVersionName());
        sourceManifest.put("resolve_reason", version.getReason());
        sourceManifest.put("enabled_field_count", enabledFields.size());
        meta.put("source_manifest", sourceManifest);
        Map<String, Object> counts = new LinkedHashMap<String, Object>();
        counts.put("tag", tagRows.size());
        counts.put("domain", domainRows.size());
        counts.put("code_value", codeRows.size());
        meta.put("counts", counts);

        List<String> lines = new ArrayList<String>();
        lines.add(toJson(meta));
        for (Map<String, Object> row : domainRows) {
            lines.add(toJson(row));
        }
        for (Map<String, Object> row : tagRows) {
            lines.add(toJson(row));
        }
        for (Map<String, Object> row : codeRows) {
            lines.add(toJson(row));
        }
        String jsonl = StringUtils.join(lines.toArray(new String[0]), "\n") + "\n";
        String contentHash = sha256(jsonl);

        BootstrapExportResult result = new BootstrapExportResult();
        result.setLibraryId(libraryId);
        result.setJsonl(jsonl);
        result.setContentHash(contentHash);
        result.setTagCount(tagRows.size());
        result.setDomainCount(domainRows.size());
        result.setCodeValueCount(codeRows.size());
        result.setIssues(issues);
        return result;
    }

    @Override
    public BootstrapImportResult importDrafts(BootstrapImportRequest request) {
        if (request == null || request.getLibraryId() == null) {
            throw new ServiceException("标签库不能为空");
        }
        if (StringUtils.isEmpty(request.getJsonl())) {
            throw new ServiceException("导入内容不能为空");
        }
        Long libraryId = request.getLibraryId();
        List<JsonNode> tagNodes = new ArrayList<JsonNode>();
        List<JsonNode> codeNodes = new ArrayList<JsonNode>();
        String[] lines = request.getJsonl().split("\\r?\\n");
        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();
            if (line.isEmpty()) {
                continue;
            }
            JsonNode node;
            try {
                node = MAPPER.readTree(line);
            } catch (Exception e) {
                throw new ServiceException("导入 JSONL 第 " + (i + 1) + " 行无法解析");
            }
            String kind = text(node, "kind");
            if ("tag_semantic".equals(kind)) {
                tagNodes.add(node);
            } else if ("code_value_semantic".equals(kind)) {
                codeNodes.add(node);
            } else {
                throw new ServiceException("导入 JSONL 第 " + (i + 1) + " 行未知 kind=" + kind);
            }
        }

        BootstrapImportResult result = new BootstrapImportResult();
        result.setLibraryId(libraryId);
        String username = currentUser();
        int importedTags = 0;
        int skipped = 0;
        for (JsonNode node : tagNodes) {
            Long tagId = longValue(node, "tag_id");
            if (tagId == null) {
                result.getRejected().add(reject(null, "INVALID_ROW", "tag_id 为空"));
                continue;
            }
            TlTag tag = tagMapper.selectTagById(tagId);
            if (tag == null || !libraryId.equals(tag.getLibraryId())) {
                result.getRejected().add(reject(tagId, "TAG_NOT_IN_LIBRARY", "标签不属于该库或不存在"));
                continue;
            }
            if (!sameAuthority(tag, node)) {
                result.getRejected().add(reject(tagId, "BASIS_DRIFT", "权威口径或字段依据已漂移，拒绝覆盖"));
                continue;
            }
            TsTagSemantic existing = tagSemanticMapper.selectByTagId(tagId);
            if (existing != null && STATUS_REVIEWED.equals(existing.getReviewStatus())) {
                skipped++;
                result.getRejected().add(reject(tagId, "REVIEWED_SKIP", "已复核语义不允许被 RULE 草稿覆盖"));
                continue;
            }
            TsTagSemantic row = toTagSemantic(node, tagId, username);
            if (existing == null) {
                tagSemanticMapper.insertTagSemantic(row);
            } else {
                row.setUpdateBy(username);
                tagSemanticMapper.updateTagSemantic(row);
            }
            importedTags++;
        }

        int importedCodes = 0;
        for (JsonNode node : codeNodes) {
            Long tagId = longValue(node, "tag_id");
            String code = text(node, "code");
            if (tagId == null || StringUtils.isEmpty(code)) {
                result.getRejected().add(reject(tagId, "INVALID_ROW", "码值 tag_id/code 为空"));
                continue;
            }
            TlTag tag = tagMapper.selectTagById(tagId);
            if (tag == null || !libraryId.equals(tag.getLibraryId())) {
                result.getRejected().add(reject(tagId, "TAG_NOT_IN_LIBRARY", "码值所属标签不属于该库"));
                continue;
            }
            TsCodeValueSemantic existing = codeValueMapper.selectByTagIdAndCode(tagId, code);
            if (existing != null && STATUS_REVIEWED.equals(existing.getReviewStatus())) {
                skipped++;
                result.getRejected().add(reject(tagId, "REVIEWED_SKIP", "已复核码值语义不允许被 RULE 草稿覆盖"));
                continue;
            }
            TsCodeValueSemantic row = toCodeSemantic(node, tagId, code, username);
            if (existing == null) {
                codeValueMapper.insertCodeValue(row);
            } else {
                row.setUpdateBy(username);
                codeValueMapper.updateCodeValue(row);
            }
            importedCodes++;
        }
        result.setImportedTagCount(importedTags);
        result.setImportedCodeCount(importedCodes);
        result.setSkippedReviewedCount(skipped);
        return result;
    }

    private List<TlTag> filterTags(List<TlTag> tags, BootstrapExportRequest request) {
        Set<Long> tagIds = request.getTagIds() == null ? Collections.<Long>emptySet()
                : new HashSet<Long>(request.getTagIds());
        Set<String> fieldNames = request.getFieldNames() == null ? Collections.<String>emptySet()
                : new HashSet<String>(request.getFieldNames());
        if (tagIds.isEmpty() && fieldNames.isEmpty()) {
            return tags;
        }
        List<TlTag> filtered = new ArrayList<TlTag>();
        for (TlTag tag : tags) {
            if (tagIds.contains(tag.getTagId()) || fieldNames.contains(tag.getFieldName())) {
                filtered.add(tag);
            }
        }
        return filtered;
    }

    private Map<String, MergedCode> loadMergedCodes(Long libraryId, DpResolvedVersion version,
            Map<String, DpResolvedField> fieldByAlias, List<Map<String, Object>> issues) {
        List<Long> ids = dimensionMapper.selectDimensionIdsByLibraryId(libraryId);
        if (ids == null || ids.isEmpty()) {
            return new LinkedHashMap<String, MergedCode>();
        }
        List<DpDimensionTable> dims = dimensionMapper.selectDimensionsForConflictCheck(ids);
        Long libraryDatasourceId = dimensionMapper.selectLibraryDatasourceId(libraryId);
        List<DpDimensionTable> active = new ArrayList<DpDimensionTable>();
        for (Long id : ids) {
            DpDimensionTable dim = findDim(dims, id);
            if (dim == null || !DEL_FLAG_EXIST.equals(dim.getDelFlag())) {
                continue;
            }
            if (!STATUS_ENABLED.equals(dim.getStatus())) {
                issues.add(issue("DIM_DISABLED", dim.getSourceTableName(), "维表已停用，跳过：" + dim.getDimensionName()));
                continue;
            }
            if (libraryDatasourceId != null && !libraryDatasourceId.equals(dim.getDatasourceId())) {
                issues.add(issue("DIM_CROSS_SOURCE", dim.getSourceTableName(), "维表与标签库不同源，跳过"));
                continue;
            }
            active.add(dim);
        }
        if (active.isEmpty()) {
            return new LinkedHashMap<String, MergedCode>();
        }
        return readAndMerge(libraryDatasourceId, active);
    }

    private Map<String, MergedCode> readAndMerge(Long datasourceId, List<DpDimensionTable> dims) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(datasourceId);
        if (ds == null) {
            throw new ServiceException("标签库数据源不存在");
        }
        String password = "";
        if (ds.getPasswordCipher() != null && !ds.getPasswordCipher().isEmpty()) {
            password = cryptoService.decrypt(ds.getPasswordCipher());
        }
        Map<String, MergedCode> merged = new LinkedHashMap<String, MergedCode>();
        try (Connection conn = connectionFactory.createConnection(ds, password)) {
            for (DpDimensionTable dim : dims) {
                String tableName = dim.getSourceTableName();
                if (tableName == null || !TABLE_NAME_PATTERN.matcher(tableName).matches()) {
                    throw new ServiceException("维表[" + dim.getDimensionName() + "]的物理表名非法：" + tableName);
                }
                String sql = "select tag_name_en, tag_code, tag_name_cn, code_definition, code_sort, last_update_time from `"
                        + tableName + "`";
                try (Statement stmt = conn.createStatement()) {
                    stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
                    try (ResultSet rs = stmt.executeQuery(sql)) {
                        while (rs.next()) {
                            String tagNameEn = rs.getString("tag_name_en");
                            String code = rs.getString("tag_code");
                            if (tagNameEn == null || code == null) {
                                continue;
                            }
                            String nameCn = rs.getString("tag_name_cn");
                            String definition = rs.getString("code_definition");
                            String key = tagNameEn + "\u0001" + code;
                            MergedCode exist = merged.get(key);
                            if (exist == null) {
                                MergedCode row = new MergedCode();
                                row.tagNameEn = tagNameEn;
                                row.code = code;
                                row.label = nameCn;
                                row.definition = definition;
                                row.codeSort = rs.getString("code_sort");
                                row.lastUpdateTime = rs.getString("last_update_time");
                                row.sources.add(sourceOf(dim));
                                merged.put(key, row);
                            } else if (!Objects.equals(exist.definition, definition) || !Objects.equals(exist.label, nameCn)) {
                                throw new ServiceException("维表[" + exist.sources.get(0).get("dimension_name")
                                        + "]与维表[" + dim.getDimensionName() + "]存在码值冲突：标签[" + tagNameEn
                                        + "]、码值[" + code + "]的定义不一致（" + exist.definition + " / " + definition + "）");
                            } else {
                                exist.sources.add(sourceOf(dim));
                            }
                        }
                    }
                }
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            throw new ServiceException("读取活动码表失败：" + e.getMessage());
        }
        return merged;
    }

    private List<MergedCode> findCodes(Map<String, MergedCode> codes, String fieldName) {
        List<MergedCode> list = new ArrayList<MergedCode>();
        for (MergedCode row : codes.values()) {
            if (fieldName != null && fieldName.equals(row.tagNameEn)) {
                list.add(row);
            }
        }
        return list;
    }

    private List<Map<String, Object>> buildDomains(List<TlTagDir> dirs, Map<Long, TlTagDir> dirMap) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        for (TlTagDir dir : dirs) {
            Long parentId = dir.getParentId() == null ? 0L : dir.getParentId();
            if (parentId.longValue() != 0L) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("kind", "domain");
            row.put("dir_id", dir.getDirId());
            row.put("parent_id", parentId);
            row.put("name", dir.getDirName());
            row.put("path", Collections.singletonList(dir.getDirName()));
            rows.add(row);
        }
        return rows;
    }

    private Map<String, Object> buildTagRow(TlTag tag, DpResolvedField field, DpResolvedVersion version,
            Map<Long, TlTagDir> dirMap, boolean objectKey) {
        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("kind", "tag");
        row.put("tag_id", tag.getTagId());
        row.put("library_id", tag.getLibraryId());
        row.put("field_name", tag.getFieldName());
        row.put("name", tag.getTagName());
        row.put("data_type", tag.getDataType());
        row.put("tag_type", tag.getTagType());
        row.put("is_object_key", tag.getIsObjectKey());
        row.put("business_candidate", Boolean.valueOf(!objectKey));
        row.put("status", tag.getStatus());
        row.put("source_status", tag.getSourceStatus());
        row.put("version", tag.getVersion());
        row.put("business_caliber", tag.getBusinessCaliber());
        row.put("tech_caliber", tag.getTechCaliber());
        row.put("update_cycle", tag.getUpdateCycle());
        row.put("dir_id", tag.getDirId());
        row.put("dir_path", dirPath(tag.getDirId(), dirMap));
        row.put("source_fingerprint", tag.getSourceFingerprint());
        row.put("confirmed_fingerprint", tag.getConfirmedFingerprint());
        Map<String, Object> binding = new LinkedHashMap<String, Object>();
        if (field != null) {
            binding.put("datasource_id", field.getDatasourceId());
            binding.put("dataset_id", version.getDatasetId());
            binding.put("version_id", version.getVersionId());
            binding.put("field_id", field.getFieldId());
            binding.put("source_table_id", field.getSourceTableId());
            binding.put("source_column_id", field.getSourceColumnId());
            binding.put("table", field.getTableName());
            binding.put("column", field.getFieldName());
        }
        row.put("binding", binding);
        return row;
    }

    private Map<String, Object> buildCodeRow(Long tagId, MergedCode code) {
        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("kind", "code_value");
        row.put("tag_id", tagId);
        row.put("code", code.code);
        row.put("label", code.label);
        row.put("definition", code.definition);
        row.put("code_sort", code.codeSort);
        row.put("last_update_time", code.lastUpdateTime);
        row.put("sources", code.sources);
        return row;
    }

    private List<String> dirPath(Long dirId, Map<Long, TlTagDir> dirMap) {
        List<String> path = new ArrayList<String>();
        Set<Long> seen = new HashSet<Long>();
        Long current = dirId;
        while (current != null && current.longValue() != 0L) {
            if (!seen.add(current)) {
                break;
            }
            TlTagDir dir = dirMap.get(current);
            if (dir == null) {
                break;
            }
            path.add(0, dir.getDirName());
            current = dir.getParentId();
        }
        return path;
    }

    private DpDimensionTable findDim(List<DpDimensionTable> dims, Long id) {
        for (DpDimensionTable dim : dims) {
            if (id.equals(dim.getDimensionId())) {
                return dim;
            }
        }
        return null;
    }

    private Map<String, Object> sourceOf(DpDimensionTable dim) {
        Map<String, Object> source = new LinkedHashMap<String, Object>();
        source.put("dimension_id", dim.getDimensionId());
        source.put("dimension_name", dim.getDimensionName());
        source.put("datasource_id", dim.getDatasourceId());
        source.put("source_table_name", dim.getSourceTableName());
        return source;
    }

    private boolean isCodeTag(TlTag tag) {
        return TAG_TYPE_OPTION.equals(tag.getTagType()) || TAG_TYPE_BOOL.equals(tag.getTagType());
    }

    private Map<String, Object> issue(String code, String field, String message) {
        Map<String, Object> issue = new LinkedHashMap<String, Object>();
        issue.put("code", code);
        issue.put("field_name", field);
        issue.put("message", message);
        return issue;
    }

    private String toJson(Map<String, Object> row) {
        try {
            return MAPPER.writeValueAsString(row);
        } catch (Exception e) {
            throw new ServiceException("序列化冻结记录失败：" + e.getMessage());
        }
    }

    private String sha256(String content) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(content.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new ServiceException("计算内容哈希失败");
        }
    }

    private TsTagSemantic toTagSemantic(JsonNode node, Long tagId, String username) {
        TsTagSemantic row = new TsTagSemantic();
        row.setTagId(tagId);
        row.setConceptId(null);
        row.setFamilyKey(nz(text(node, "family_candidate"), "UNNAMED|NONE|ALL|NONE|NONE|BASE"));
        row.setCaliberVariant(nz(text(node, "caliber_variant"), "BASE"));
        row.setSemanticType(text(node, "semantic_type"));
        row.setAllowedOperators(jsonText(node.get("allowed_operators")));
        row.setDefaultOperator(text(node, "default_operator"));
        row.setUnit(nz(text(node, "unit"), "NONE"));
        row.setUnitScale(decimalValue(node, "unit_scale"));
        JsonNode caliber = node.get("caliber_struct");
        row.setCaliberStruct(caliber == null || caliber.isNull() ? "{}" : caliber.toString());
        row.setDefinitionLong(text(node, "definition_long"));
        row.setSensitivity(nz(text(node, "sensitivity"), "UNKNOWN"));
        row.setBasisHash(text(node, "basis_hash"));
        row.setSource("RULE");
        row.setReviewStatus(STATUS_DRAFT);
        row.setSemanticVersion(1);
        row.setSourceRef("rule_init");
        row.setRemark(text(node, "concept_candidate"));
        row.setCreateBy(username);
        if (StringUtils.isEmpty(row.getSemanticType()) || StringUtils.isEmpty(row.getAllowedOperators())) {
            throw new ServiceException("标签 " + tagId + " 缺少 semantic_type 或 allowed_operators");
        }
        return row;
    }

    private TsCodeValueSemantic toCodeSemantic(JsonNode node, Long tagId, String code, String username) {
        TsCodeValueSemantic row = new TsCodeValueSemantic();
        row.setTagId(tagId);
        row.setCode(code);
        row.setRankNo(intValue(node, "rank_no"));
        row.setLowerBound(decimalValue(node, "lower_bound"));
        row.setUpperBound(decimalValue(node, "upper_bound"));
        row.setLowerInclusive(intValue(node, "lower_inclusive"));
        row.setUpperInclusive(intValue(node, "upper_inclusive"));
        row.setBoundUnit(text(node, "bound_unit"));
        row.setIsUnknownBucket(0);
        row.setBasisHash(text(node, "basis_hash"));
        row.setSource("RULE");
        row.setReviewStatus(STATUS_DRAFT);
        row.setSourceRef("rule_init");
        row.setCreateBy(username);
        return row;
    }

    private boolean sameAuthority(TlTag tag, JsonNode node) {
        JsonNode authority = node.get("authority");
        if (authority == null || authority.isNull()) {
            return false;
        }
        return eq(tag.getFieldName(), text(authority, "field_name"))
                && eq(nz(tag.getBusinessCaliber(), ""), nz(text(authority, "business_caliber"), ""))
                && eq(nz(tag.getTechCaliber(), ""), nz(text(authority, "tech_caliber"), ""))
                && eq(nz(tag.getDataType(), ""), nz(text(authority, "data_type"), ""));
    }

    private Map<String, Object> reject(Long tagId, String code, String message) {
        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("tag_id", tagId);
        row.put("code", code);
        row.put("message", message);
        return row;
    }

    private String currentUser() {
        try {
            String name = SecurityUtils.getUsername();
            return StringUtils.isEmpty(name) ? "rule_init" : name;
        } catch (Exception e) {
            return "rule_init";
        }
    }

    private String text(JsonNode node, String field) {
        if (node == null || !node.has(field) || node.get(field).isNull()) {
            return null;
        }
        return node.get(field).asText();
    }

    private Long longValue(JsonNode node, String field) {
        if (node == null || !node.has(field) || node.get(field).isNull()) {
            return null;
        }
        return Long.valueOf(node.get(field).asLong());
    }

    private Integer intValue(JsonNode node, String field) {
        if (node == null || !node.has(field) || node.get(field).isNull()) {
            return null;
        }
        return Integer.valueOf(node.get(field).asInt());
    }

    private BigDecimal decimalValue(JsonNode node, String field) {
        if (node == null || !node.has(field) || node.get(field).isNull()) {
            return null;
        }
        return new BigDecimal(node.get(field).asText());
    }

    private String jsonText(JsonNode node) {
        if (node == null || node.isNull()) {
            return "[]";
        }
        return node.toString();
    }

    private String nz(String value, String fallback) {
        return StringUtils.isEmpty(value) ? fallback : value;
    }

    private boolean eq(String left, String right) {
        return Objects.equals(left, right);
    }

    private static class MergedCode {
        private String tagNameEn;
        private String code;
        private String label;
        private String definition;
        private String codeSort;
        private String lastUpdateTime;
        private final List<Map<String, Object>> sources = new ArrayList<Map<String, Object>>();
    }
}
