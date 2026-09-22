package com.ruoyi.taglibrary.service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportResult;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;

/**
 * 同一冻结批次的批量复核。用于全库业务复核包落库，仍执行逐标签/逐码值依据哈希校验。
 * 该服务不生成语义、不替代审批人判断，也不对外暴露跳过权限的 HTTP 接口。
 */
@Service
public class TsSemanticBatchReviewService {
    private static final ObjectMapper JSON = new ObjectMapper();
    @Autowired private ITsBootstrapService bootstrap;
    @Autowired private ITsSemanticService semantics;
    @Autowired private TsConceptMapper conceptMapper;
    @Autowired private TsTagSemanticMapper tagMapper;
    @Autowired private TsCodeValueSemanticMapper codeMapper;

    /** 仅重绑已复核包声明的概念与 family；basis_hash 不一致时拒绝。 */
    @Transactional
    public int rebindConceptsFromPackage(Long libraryId, String packageJsonl) {
        if (libraryId == null || StringUtils.isEmpty(packageJsonl)) throw new ServiceException("标签库与复核包不能为空");
        Map<String, TsConcept> conceptsByCode = new HashMap<String, TsConcept>();
        TsConcept query = new TsConcept(); query.setLibraryId(libraryId);
        for (TsConcept concept : semantics.selectConceptList(query)) conceptsByCode.put(concept.getConceptCode(), concept);
        int changed = 0;
        try {
            for (String line : packageJsonl.split("\\r?\\n")) {
                if (line.trim().isEmpty()) continue;
                JsonNode node = JSON.readTree(line);
                if (!"tag_semantic".equals(node.path("kind").asText())) continue;
                Long tagId = node.path("tag_id").asLong();
                TsTagSemantic tag = tagMapper.selectByTagId(tagId);
                // 对象主键仅用于实体关联，不进入可检索业务概念；复核包会显式标记 skip_concept。
                if (node.path("skip_concept").asBoolean(false)) {
                    if (tag == null || !Objects.equals(tag.getBasisHash(), node.path("basis_hash").asText())) {
                        throw new ServiceException("对象主键依据缺失或漂移：" + tagId);
                    }
                    continue;
                }
                TsConcept concept = conceptsByCode.get(node.path("concept_code").asText());
                if (tag == null || concept == null || !Objects.equals(tag.getBasisHash(), node.path("basis_hash").asText())) {
                    throw new ServiceException("概念重绑依据缺失或漂移：" + tagId);
                }
                String familyKey = node.path("family_key").asText();
                if (!Objects.equals(tag.getConceptId(), concept.getConceptId()) || !Objects.equals(tag.getFamilyKey(), familyKey)) {
                    tag.setConceptId(concept.getConceptId()); tag.setFamilyKey(familyKey); tag.setReviewStatus("DRAFT");
                    tag.setUpdateBy(SecurityUtils.getUsername()); tagMapper.updateTagSemantic(tag); changed++;
                }
            }
        } catch (ServiceException e) { throw e; }
        catch (Exception e) { throw new ServiceException("复核包概念重绑内容无法解析"); }
        return changed;
    }

    @Transactional
    public Map<String, Object> reviewLibrary(Long libraryId, String sourceRef) {
        if (libraryId == null || StringUtils.isEmpty(sourceRef)) {
            throw new ServiceException("标签库与复核依据不能为空");
        }
        BootstrapExportRequest request = new BootstrapExportRequest();
        request.setLibraryId(libraryId);
        BootstrapExportResult freeze = bootstrap.exportFreeze(request);
        if (!freeze.getIssues().isEmpty()) {
            throw new ServiceException("来源冻结存在异常，拒绝批量复核");
        }
        return reviewLibrary(libraryId, sourceRef, freeze);
    }

    @Transactional
    public Map<String, Object> reviewLibraryFromFreeze(Long libraryId, String sourceRef, String jsonl, String contentHash) {
        if (libraryId == null || StringUtils.isEmpty(sourceRef) || jsonl == null || contentHash == null
                || !contentHash.equals(TsSnapshotCanonicalizer.sha256(jsonl))) {
            throw new ServiceException("标签库、复核依据或冻结工件无效");
        }
        BootstrapExportResult freeze = new BootstrapExportResult();
        freeze.setLibraryId(libraryId); freeze.setJsonl(jsonl); freeze.setContentHash(contentHash);
        freeze.setIssues(Collections.emptyList());
        return reviewLibrary(libraryId, sourceRef, freeze);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> reviewLibrary(Long libraryId, String sourceRef, BootstrapExportResult freeze) {
        Map<Long, Map<String, Object>> authority = new HashMap<Long, Map<String, Object>>();
        Map<Long, List<Map<String, Object>>> sourceCodes = new HashMap<Long, List<Map<String, Object>>>();
        try {
            for (String line : freeze.getJsonl().split("\\r?\\n")) {
                if (line.trim().isEmpty()) continue;
                Map<String, Object> row = JSON.readValue(line, Map.class);
                Long tagId = row.get("tag_id") instanceof Number ? ((Number) row.get("tag_id")).longValue() : null;
                if ("tag".equals(row.get("kind"))) authority.put(tagId, row);
                if ("code_value".equals(row.get("kind"))) sourceCodes.computeIfAbsent(tagId, k -> new ArrayList<Map<String, Object>>()).add(row);
            }
        } catch (Exception e) {
            throw new ServiceException("冻结内容无法解析");
        }

        String reviewer = SecurityUtils.getUsername();
        Date now = new Date();
        int conceptCount = 0, codeCount = 0, tagCount = 0;
        Map<Long, TsConcept> concepts = new HashMap<Long, TsConcept>();
        TsConcept query = new TsConcept(); query.setLibraryId(libraryId);
        for (TsConcept concept : semantics.selectConceptList(query)) {
            concepts.put(concept.getConceptId(), concept);
            if (!"REVIEWED".equals(concept.getReviewStatus())) {
                concept.setReviewStatus("REVIEWED"); concept.setReviewBy(reviewer); concept.setReviewTime(now);
                concept.setSourceRef(sourceRef); concept.setUpdateBy(reviewer); conceptMapper.updateConcept(concept);
            }
            conceptCount++;
        }

        List<TsTagSemantic> tags = semantics.selectTagSemanticByLibraryId(libraryId);
        if (tags.size() != authority.size()) {
            throw new ServiceException("标签语义数量与冻结字段数量不一致");
        }
        for (TsTagSemantic tag : tags) {
            Map<String, Object> source = authority.get(tag.getTagId());
            List<Map<String, Object>> sourceList = sourceCodes.getOrDefault(tag.getTagId(), Collections.<Map<String, Object>>emptyList());
            if (source == null || !Objects.equals(tag.getBasisHash(), TsSnapshotAssembler.basisHash(source, sourceList))) {
                throw new ServiceException("标签复核依据已漂移：" + tag.getTagId());
            }
            List<TsCodeValueSemantic> codes = semantics.selectCodeValuesByTagId(tag.getTagId());
            Map<String, Map<String, Object>> sourceByCode = new HashMap<String, Map<String, Object>>();
            for (Map<String, Object> row : sourceList) sourceByCode.put(String.valueOf(row.get("code")), row);
            if (codes.size() != sourceByCode.size()) {
                throw new ServiceException("码值语义数量与冻结来源不一致：" + tag.getTagId());
            }
            for (TsCodeValueSemantic code : codes) {
                Map<String, Object> sourceCode = sourceByCode.get(code.getCode());
                if (sourceCode == null || !Objects.equals(code.getBasisHash(), TsSnapshotAssembler.codeBasisHash(tag.getTagId(), sourceCode, tag.getBasisHash()))) {
                    throw new ServiceException("码值复核依据已漂移：" + tag.getTagId() + "#" + code.getCode());
                }
                if (!"REVIEWED".equals(code.getReviewStatus())) {
                    code.setReviewStatus("REVIEWED"); code.setReviewBy(reviewer); code.setReviewTime(now);
                    code.setSourceRef(sourceRef); code.setUpdateBy(reviewer); codeMapper.updateCodeValue(code);
                }
                codeCount++;
            }
        }

        for (TsTagSemantic tag : tags) {
            List<TsAlias> aliases = semantics.selectAliasList("TAG", String.valueOf(tag.getTagId()));
            List<TsCodeValueSemantic> codes = semantics.selectCodeValuesByTagId(tag.getTagId());
            TsConcept concept = concepts.get(tag.getConceptId());
            int score = TsCompletenessScorer.score(tag, concept, aliases, codes,
                    semantics.selectConfusableByTagId(tag.getTagId()).stream().anyMatch(p -> "REVIEWED".equals(p.getReviewStatus())),
                    semantics.selectExamplesByTagId(tag.getTagId()).stream().anyMatch(e -> "REVIEWED".equals(e.getReviewStatus()) && "POS".equals(e.getExampleType())));
            if (!"ID_KEY".equals(tag.getSemanticType()) && score < 70) {
                throw new ServiceException("标签完整度不足：" + tag.getTagId() + " score=" + score);
            }
            tag.setCompletenessScore(Integer.valueOf(score)); tag.setReviewStatus("REVIEWED");
            tag.setReviewBy(reviewer); tag.setReviewTime(now); tag.setSourceRef(sourceRef); tag.setUpdateBy(reviewer);
            tagMapper.updateTagSemantic(tag); tagCount++;
        }
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("freeze_sha256", freeze.getContentHash()); result.put("concepts", conceptCount);
        result.put("tags", tagCount); result.put("codes", codeCount); result.put("review_by", reviewer);
        result.put("source_ref", sourceRef); result.put("release_mode", "FROZEN_ARTIFACT_LOCAL_DEMO"); return result;
    }
}
