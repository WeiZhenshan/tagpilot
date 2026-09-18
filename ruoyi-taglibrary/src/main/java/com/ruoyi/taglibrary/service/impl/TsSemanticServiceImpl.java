package com.ruoyi.taglibrary.service.impl;

import java.util.Date;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsAliasMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import com.ruoyi.taglibrary.service.ITsSemanticService;

/**
 * 标签语义草稿维护。不改写 tl_tag。
 */
@Service
public class TsSemanticServiceImpl implements ITsSemanticService {

    private static final String STATUS_DRAFT = "DRAFT";
    private static final String STATUS_REVIEWED = "REVIEWED";

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
}
