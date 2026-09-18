package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsBusinessTerm;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsConfusable;
import com.ruoyi.taglibrary.domain.TsTagExample;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsAliasMapper;
import com.ruoyi.taglibrary.mapper.TsBusinessTermMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsConfusableMapper;
import com.ruoyi.taglibrary.mapper.TsTagExampleMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import com.ruoyi.taglibrary.service.ITsSemanticService;

/**
 * 标签语义草稿维护。不改写 tl_tag。
 */
@Service
public class TsSemanticServiceImpl implements ITsSemanticService {

    private static final String STATUS_DRAFT = "DRAFT";
    private static final String STATUS_REVIEWED = "REVIEWED";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TsTagSemanticMapper tagSemanticMapper;
    @Autowired
    private TsConceptMapper conceptMapper;
    @Autowired
    private TsAliasMapper aliasMapper;
    @Autowired
    private TsCodeValueSemanticMapper codeValueMapper;
    @Autowired
    private TsBusinessTermMapper termMapper;
    @Autowired
    private TsConfusableMapper confusableMapper;
    @Autowired
    private TsTagExampleMapper exampleMapper;

    @Override
    public TsTagSemantic selectTagSemanticByTagId(Long tagId) {
        return tagSemanticMapper.selectByTagId(tagId);
    }

    @Override
    public List<TsTagSemantic> selectTagSemanticByLibraryId(Long libraryId) {
        if (libraryId == null) {
            throw new ServiceException("标签库不能为空");
        }
        return tagSemanticMapper.selectByLibraryId(libraryId);
    }

    @Override
    public int saveTagSemantic(TsTagSemantic semantic) {
        if (semantic == null || semantic.getTagId() == null) {
            throw new ServiceException("标签ID不能为空");
        }
        TlTag tag = requireTag(semantic.getTagId());
        validateRequiredSemantic(semantic);
        if (semantic.getConceptId() != null) {
            TsConcept concept = conceptMapper.selectConceptById(semantic.getConceptId());
            if (concept == null) {
                throw new ServiceException("概念不存在");
            }
            if (!tag.getLibraryId().equals(concept.getLibraryId())) {
                throw new ServiceException("概念与标签必须属于同一标签库");
            }
        }
        String username = SecurityUtils.getUsername();
        TsTagSemantic existing = tagSemanticMapper.selectByTagId(semantic.getTagId());
        semantic.setReviewStatus(STATUS_DRAFT);
        if (existing == null) {
            if (StringUtils.isEmpty(semantic.getSource())) {
                semantic.setSource("HUMAN");
            }
            if (semantic.getCaliberVariant() == null) {
                semantic.setCaliberVariant("BASE");
            }
            if (semantic.getSensitivity() == null) {
                semantic.setSensitivity("UNKNOWN");
            }
            if (semantic.getSemanticVersion() == null) {
                semantic.setSemanticVersion(1);
            }
            semantic.setCreateBy(username);
            return tagSemanticMapper.insertTagSemantic(semantic);
        }
        semantic.setUpdateBy(username);
        return tagSemanticMapper.updateTagSemantic(semantic);
    }

    @Override
    public int reviewTagSemantic(Long tagId, String sourceRef) {
        TsTagSemantic existing = tagSemanticMapper.selectByTagId(tagId);
        if (existing == null) {
            throw new ServiceException("语义记录不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        TsConcept concept = existing.getConceptId() == null ? null : conceptMapper.selectConceptById(existing.getConceptId());
        existing.setCompletenessScore(Integer.valueOf(com.ruoyi.taglibrary.service.TsCompletenessScorer.score(
                existing, concept, java.util.Collections.<TsAlias>emptyList(),
                codeValueMapper.selectByTagId(tagId), true, false)));
        return tagSemanticMapper.updateTagSemantic(existing);
    }

    @Override
    public TsConcept selectConceptById(Long conceptId) {
        return conceptMapper.selectConceptById(conceptId);
    }

    @Override
    public List<TsConcept> selectConceptList(TsConcept query) {
        return conceptMapper.selectConceptList(query);
    }

    @Override
    public int saveConcept(TsConcept concept) {
        if (concept == null || concept.getLibraryId() == null) {
            throw new ServiceException("标签库不能为空");
        }
        if (StringUtils.isEmpty(concept.getConceptCode()) || StringUtils.isEmpty(concept.getConceptName())) {
            throw new ServiceException("概念编码与名称不能为空");
        }
        if (concept.getDomainDirId() == null) {
            throw new ServiceException("业务域目录不能为空");
        }
        if (StringUtils.isEmpty(concept.getTagObject())) {
            throw new ServiceException("业务对象不能为空");
        }
        String username = SecurityUtils.getUsername();
        concept.setReviewStatus(STATUS_DRAFT);
        if (concept.getParentId() == null) {
            concept.setParentId(0L);
        }
        if (StringUtils.isEmpty(concept.getStatus())) {
            concept.setStatus("0");
        }
        if (concept.getConceptId() == null) {
            if (StringUtils.isEmpty(concept.getSource())) {
                concept.setSource("HUMAN");
            }
            concept.setCreateBy(username);
            return conceptMapper.insertConcept(concept);
        }
        TsConcept existing = conceptMapper.selectConceptById(concept.getConceptId());
        if (existing == null) {
            throw new ServiceException("概念不存在");
        }
        concept.setUpdateBy(username);
        return conceptMapper.updateConcept(concept);
    }

    @Override
    public int reviewConcept(Long conceptId, String sourceRef) {
        TsConcept existing = conceptMapper.selectConceptById(conceptId);
        if (existing == null) {
            throw new ServiceException("概念不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return conceptMapper.updateConcept(existing);
    }

    @Override
    public TsAlias selectAliasById(Long aliasId) {
        return aliasMapper.selectAliasById(aliasId);
    }

    @Override
    public List<TsAlias> selectAliasList(String targetType, String targetId) {
        return aliasMapper.selectAliasList(targetType, targetId);
    }

    @Override
    public int saveAlias(TsAlias alias) {
        if (alias == null || StringUtils.isEmpty(alias.getTargetType()) || StringUtils.isEmpty(alias.getTargetId())) {
            throw new ServiceException("别名目标不能为空");
        }
        if (StringUtils.isEmpty(alias.getAliasText()) || StringUtils.isEmpty(alias.getAliasType())) {
            throw new ServiceException("别名文本与类型不能为空");
        }
        if (StringUtils.isEmpty(alias.getAliasNorm())) {
            alias.setAliasNorm(normalizeAlias(alias.getAliasText()));
        }
        String username = SecurityUtils.getUsername();
        alias.setReviewStatus(STATUS_DRAFT);
        if (alias.getAliasId() == null) {
            if (StringUtils.isEmpty(alias.getSource())) {
                alias.setSource("HUMAN");
            }
            alias.setCreateBy(username);
            return aliasMapper.insertAlias(alias);
        }
        TsAlias existing = aliasMapper.selectAliasById(alias.getAliasId());
        if (existing == null) {
            throw new ServiceException("别名不存在");
        }
        alias.setUpdateBy(username);
        return aliasMapper.updateAlias(alias);
    }

    @Override
    public int reviewAlias(Long aliasId, String sourceRef) {
        TsAlias existing = aliasMapper.selectAliasById(aliasId);
        if (existing == null) {
            throw new ServiceException("别名不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return aliasMapper.updateAlias(existing);
    }

    @Override
    public List<TsCodeValueSemantic> selectCodeValuesByTagId(Long tagId) {
        requireTag(tagId);
        return codeValueMapper.selectByTagId(tagId);
    }

    @Override
    public int saveCodeValue(TsCodeValueSemantic row) {
        if (row == null || row.getTagId() == null || StringUtils.isEmpty(row.getCode())) {
            throw new ServiceException("标签与码值不能为空");
        }
        requireTag(row.getTagId());
        String username = SecurityUtils.getUsername();
        row.setReviewStatus(STATUS_DRAFT);
        TsCodeValueSemantic existing = codeValueMapper.selectByTagIdAndCode(row.getTagId(), row.getCode());
        if (existing == null) {
            if (StringUtils.isEmpty(row.getSource())) {
                row.setSource("HUMAN");
            }
            if (row.getIsUnknownBucket() == null) {
                row.setIsUnknownBucket(0);
            }
            row.setCreateBy(username);
            return codeValueMapper.insertCodeValue(row);
        }
        row.setUpdateBy(username);
        return codeValueMapper.updateCodeValue(row);
    }

    @Override
    public int reviewCodeValue(Long tagId, String code, String sourceRef) {
        TsCodeValueSemantic existing = codeValueMapper.selectByTagIdAndCode(tagId, code);
        if (existing == null) {
            throw new ServiceException("码值语义不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return codeValueMapper.updateCodeValue(existing);
    }

    @Override
    public List<TsBusinessTerm> selectTermList(String termNorm, String termType) {
        return termMapper.selectTermList(termNorm, termType);
    }

    @Override
    public int saveTerm(TsBusinessTerm term) {
        if (term == null || StringUtils.isEmpty(term.getTerm()) || StringUtils.isEmpty(term.getTermType())) {
            throw new ServiceException("词条与类型不能为空");
        }
        if (StringUtils.isEmpty(term.getTermNorm())) {
            term.setTermNorm(normalizeAlias(term.getTerm()));
        }
        if (StringUtils.isEmpty(term.getTagObject())) {
            term.setTagObject("客户");
        }
        String username = SecurityUtils.getUsername();
        term.setReviewStatus(STATUS_DRAFT);
        if (term.getTermId() == null) {
            term.setCreateBy(username);
            return termMapper.insertTerm(term);
        }
        TsBusinessTerm existing = termMapper.selectTermById(term.getTermId());
        if (existing == null) {
            throw new ServiceException("词条不存在");
        }
        term.setUpdateBy(username);
        return termMapper.updateTerm(term);
    }

    @Override
    public int reviewTerm(Long termId, String sourceRef) {
        TsBusinessTerm existing = termMapper.selectTermById(termId);
        if (existing == null) {
            throw new ServiceException("词条不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return termMapper.updateTerm(existing);
    }

    @Override
    public List<TsConfusable> selectConfusableByTagId(Long tagId) {
        return confusableMapper.selectByTagId(tagId);
    }

    @Override
    public int saveConfusable(TsConfusable pair) {
        if (pair == null || pair.getTagIdA() == null || pair.getTagIdB() == null) {
            throw new ServiceException("易混淆标签对不能为空");
        }
        if (pair.getTagIdA().equals(pair.getTagIdB())) {
            throw new ServiceException("易混淆对不能是同一标签");
        }
        if (pair.getTagIdA().longValue() > pair.getTagIdB().longValue()) {
            Long tmp = pair.getTagIdA();
            pair.setTagIdA(pair.getTagIdB());
            pair.setTagIdB(tmp);
        }
        if (StringUtils.isEmpty(pair.getConfusionType())) {
            throw new ServiceException("混淆类型不能为空");
        }
        String username = SecurityUtils.getUsername();
        pair.setReviewStatus(STATUS_DRAFT);
        if (pair.getPairId() == null) {
            if (StringUtils.isEmpty(pair.getSource())) {
                pair.setSource("HUMAN");
            }
            pair.setCreateBy(username);
            return confusableMapper.insertPair(pair);
        }
        TsConfusable existing = confusableMapper.selectById(pair.getPairId());
        if (existing == null) {
            throw new ServiceException("易混淆对不存在");
        }
        pair.setUpdateBy(username);
        return confusableMapper.updatePair(pair);
    }

    @Override
    public int reviewConfusable(Long pairId, String sourceRef) {
        TsConfusable existing = confusableMapper.selectById(pairId);
        if (existing == null) {
            throw new ServiceException("易混淆对不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return confusableMapper.updatePair(existing);
    }

    @Override
    public int generateTimeFacetPairs(Long libraryId) {
        if (libraryId == null) {
            throw new ServiceException("标签库不能为空");
        }
        List<TsTagSemantic> tags = tagSemanticMapper.selectByLibraryId(libraryId);
        Map<String, List<TsTagSemantic>> groups = new HashMap<String, List<TsTagSemantic>>();
        for (TsTagSemantic tag : tags) {
            if ("ID_KEY".equals(tag.getSemanticType()) || StringUtils.isEmpty(tag.getFamilyKey())) {
                continue;
            }
            List<TsTagSemantic> members = groups.get(tag.getFamilyKey());
            if (members == null) {
                members = new ArrayList<TsTagSemantic>();
                groups.put(tag.getFamilyKey(), members);
            }
            members.add(tag);
        }
        int created = 0;
        String username = SecurityUtils.getUsername();
        for (List<TsTagSemantic> members : groups.values()) {
            if (members.size() < 2) {
                continue;
            }
            for (int i = 0; i < members.size(); i++) {
                for (int j = i + 1; j < members.size(); j++) {
                    TsTagSemantic left = members.get(i);
                    TsTagSemantic right = members.get(j);
                    Long a = left.getTagId();
                    Long b = right.getTagId();
                    if (a.longValue() > b.longValue()) {
                        Long tmp = a;
                        a = b;
                        b = tmp;
                        TsTagSemantic swap = left;
                        left = right;
                        right = swap;
                    }
                    if (confusableMapper.selectByPair(a, b) != null) {
                        continue;
                    }
                    String la = timeLabel(left);
                    String lb = timeLabel(right);
                    TsConfusable pair = new TsConfusable();
                    pair.setTagIdA(a);
                    pair.setTagIdB(b);
                    pair.setConfusionType("TIME_FACET");
                    pair.setDifferenceNote("两者仅统计时点不同：" + la + " vs " + lb);
                    pair.setDisambiguationHint("用户提到" + la + "选" + nz(left.getTagName(), String.valueOf(a))
                            + "；提到" + lb + "选" + nz(right.getTagName(), String.valueOf(b)));
                    pair.setSource("RULE");
                    pair.setReviewStatus(STATUS_DRAFT);
                    pair.setCreateBy(username);
                    confusableMapper.insertPair(pair);
                    created++;
                }
            }
        }
        return created;
    }

    @Override
    public List<TsTagExample> selectExamplesByTagId(Long tagId) {
        return exampleMapper.selectByTagId(tagId);
    }

    @Override
    public int saveExample(TsTagExample example) {
        if (example == null || example.getTagId() == null || StringUtils.isEmpty(example.getUtterance())) {
            throw new ServiceException("示例标签与说法不能为空");
        }
        if (StringUtils.isEmpty(example.getExampleType())) {
            throw new ServiceException("示例类型不能为空");
        }
        requireTag(example.getTagId());
        String username = SecurityUtils.getUsername();
        example.setReviewStatus(STATUS_DRAFT);
        if (example.getExampleId() == null) {
            if (StringUtils.isEmpty(example.getSource())) {
                example.setSource("HUMAN");
            }
            example.setCreateBy(username);
            return exampleMapper.insertExample(example);
        }
        TsTagExample existing = exampleMapper.selectById(example.getExampleId());
        if (existing == null) {
            throw new ServiceException("示例不存在");
        }
        example.setUpdateBy(username);
        return exampleMapper.updateExample(example);
    }

    @Override
    public int reviewExample(Long exampleId, String sourceRef) {
        TsTagExample existing = exampleMapper.selectById(exampleId);
        if (existing == null) {
            throw new ServiceException("示例不存在");
        }
        requireDraft(existing.getReviewStatus());
        existing.setReviewStatus(STATUS_REVIEWED);
        existing.setSourceRef(sourceRef);
        existing.setReviewBy(SecurityUtils.getUsername());
        existing.setReviewTime(new Date());
        existing.setUpdateBy(SecurityUtils.getUsername());
        return exampleMapper.updateExample(existing);
    }

    private TlTag requireTag(Long tagId) {
        TlTag tag = tagMapper.selectTagById(tagId);
        if (tag == null) {
            throw new ServiceException("标签不存在或已删除");
        }
        return tag;
    }

    private void validateRequiredSemantic(TsTagSemantic semantic) {
        if (StringUtils.isEmpty(semantic.getFamilyKey())) {
            throw new ServiceException("family_key 不能为空");
        }
        if (StringUtils.isEmpty(semantic.getSemanticType())) {
            throw new ServiceException("semantic_type 不能为空");
        }
        if (StringUtils.isEmpty(semantic.getAllowedOperators())) {
            throw new ServiceException("allowed_operators 不能为空");
        }
        if (StringUtils.isEmpty(semantic.getCaliberStruct())) {
            throw new ServiceException("caliber_struct 不能为空");
        }
    }

    private void requireDraft(String reviewStatus) {
        if (!STATUS_DRAFT.equals(reviewStatus)) {
            throw new ServiceException("仅 DRAFT 状态可以复核");
        }
    }

    static String normalizeAlias(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == ' ' || c == '　') {
                continue;
            }
            if (c >= 0xFF01 && c <= 0xFF5E) {
                c = (char) (c - 0xFEE0);
            }
            sb.append(Character.toLowerCase(c));
        }
        return sb.toString();
    }

    private String timeLabel(TsTagSemantic tag) {
        String raw = tag.getCaliberStruct();
        if (StringUtils.isEmpty(raw)) {
            return "无时间";
        }
        try {
            JsonNode node = MAPPER.readTree(raw);
            JsonNode label = node.get("time_anchor_label");
            if (label != null && !label.isNull() && StringUtils.isNotEmpty(label.asText())) {
                return label.asText();
            }
        } catch (Exception ignored) {
            return "无时间";
        }
        return "无时间";
    }

    private String nz(String value, String fallback) {
        return StringUtils.isEmpty(value) ? fallback : value;
    }
}
