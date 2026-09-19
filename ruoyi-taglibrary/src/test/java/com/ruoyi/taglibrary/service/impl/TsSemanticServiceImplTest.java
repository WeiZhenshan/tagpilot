package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsAliasMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;

/**
 * 语义草稿 Service 单元测试（Mockito，不起 Spring）
 */
@ExtendWith(MockitoExtension.class)
class TsSemanticServiceImplTest extends BaseServiceTest {

    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private TsTagSemanticMapper tagSemanticMapper;
    @Mock
    private TsConceptMapper conceptMapper;
    @Mock
    private TsAliasMapper aliasMapper;
    @Mock
    private TsCodeValueSemanticMapper codeValueMapper;

    @Mock private com.ruoyi.taglibrary.service.TsSemanticBasisGuard basisGuard;

    @InjectMocks
    private TsSemanticServiceImpl semanticService;

    @Test
    void saveTagSemanticRejectsUnknownTag() {
        when(tagMapper.selectTagById(999L)).thenReturn(null);
        TsTagSemantic semantic = validSemantic(999L);
        ServiceException ex = assertThrows(ServiceException.class, () -> semanticService.saveTagSemantic(semantic));
        assertEquals("标签不存在或已删除", ex.getMessage());
        verify(tagSemanticMapper, never()).insertTagSemantic(any());
    }

    @Test
    void saveTagSemanticRejectsConceptFromOtherLibrary() {
        TlTag tag = tag(534L, 107L);
        when(tagMapper.selectTagById(534L)).thenReturn(tag);
        TsConcept concept = new TsConcept();
        concept.setConceptId(8L);
        concept.setLibraryId(105L);
        when(conceptMapper.selectConceptById(8L)).thenReturn(concept);

        TsTagSemantic semantic = validSemantic(534L);
        semantic.setConceptId(8L);
        ServiceException ex = assertThrows(ServiceException.class, () -> semanticService.saveTagSemantic(semantic));
        assertEquals("概念与标签必须属于同一标签库", ex.getMessage());
    }

    @Test
    void saveTagSemanticInsertsDraft() {
        when(tagMapper.selectTagById(534L)).thenReturn(tag(534L, 107L));
        when(tagSemanticMapper.selectByTagId(534L)).thenReturn(null);
        when(tagSemanticMapper.insertTagSemantic(any(TsTagSemantic.class))).thenReturn(1);

        TsTagSemantic semantic = validSemantic(534L);
        assertEquals(1, semanticService.saveTagSemantic(semantic));

        ArgumentCaptor<TsTagSemantic> captor = ArgumentCaptor.forClass(TsTagSemantic.class);
        verify(tagSemanticMapper).insertTagSemantic(captor.capture());
        assertEquals("DRAFT", captor.getValue().getReviewStatus());
        assertEquals("RULE", captor.getValue().getSource());
        assertEquals(USERNAME, captor.getValue().getCreateBy());
    }

    @Test
    void saveTagSemanticRevertsReviewedToDraft() {
        when(tagMapper.selectTagById(534L)).thenReturn(tag(534L, 107L));
        TsTagSemantic existing = validSemantic(534L);
        existing.setReviewStatus("REVIEWED");
        when(tagSemanticMapper.selectByTagId(534L)).thenReturn(existing);
        when(tagSemanticMapper.updateTagSemantic(any(TsTagSemantic.class))).thenReturn(1);

        TsTagSemantic patch = validSemantic(534L);
        patch.setDefinitionLong("更新定义");
        semanticService.saveTagSemantic(patch);

        ArgumentCaptor<TsTagSemantic> captor = ArgumentCaptor.forClass(TsTagSemantic.class);
        verify(tagSemanticMapper).updateTagSemantic(captor.capture());
        assertEquals("DRAFT", captor.getValue().getReviewStatus());
        assertEquals("更新定义", captor.getValue().getDefinitionLong());
    }

    @Test
    void reviewTagSemanticRejectsNonDraft() {
        TsTagSemantic existing = validSemantic(534L);
        existing.setReviewStatus("REVIEWED");
        when(tagSemanticMapper.selectByTagId(534L)).thenReturn(existing);
        ServiceException ex = assertThrows(ServiceException.class,
                () -> semanticService.reviewTagSemantic(534L, "ok"));
        assertEquals("仅 DRAFT 状态可以复核", ex.getMessage());
    }

    @Test
    void reviewTagSemanticMarksReviewed() {
        TsTagSemantic existing = validSemantic(534L);
        existing.setReviewStatus("DRAFT");
        when(tagSemanticMapper.selectByTagId(534L)).thenReturn(existing);
        when(tagSemanticMapper.updateTagSemantic(any(TsTagSemantic.class))).thenReturn(1);

        semanticService.reviewTagSemantic(534L, "业务确认区间");

        ArgumentCaptor<TsTagSemantic> captor = ArgumentCaptor.forClass(TsTagSemantic.class);
        verify(tagSemanticMapper).updateTagSemantic(captor.capture());
        assertEquals("REVIEWED", captor.getValue().getReviewStatus());
        assertEquals("业务确认区间", captor.getValue().getSourceRef());
        assertEquals(USERNAME, captor.getValue().getReviewBy());
    }

    private static TlTag tag(Long tagId, Long libraryId) {
        TlTag tag = new TlTag();
        tag.setTagId(tagId);
        tag.setLibraryId(libraryId);
        tag.setFieldName("OUTSIDE_ASSET_WAN_KYC");
        return tag;
    }

    private static TsTagSemantic validSemantic(Long tagId) {
        TsTagSemantic semantic = new TsTagSemantic();
        semantic.setTagId(tagId);
        semantic.setFamilyKey("OUTSIDE_ASSET|NONE|ALL|NONE|NONE|BASE");
        semantic.setSemanticType("ENUM_ORDINAL");
        semantic.setAllowedOperators("[\"=\",\"in\",\"not_in\"]");
        semantic.setCaliberStruct("{}");
        semantic.setSource("RULE");
        return semantic;
    }
}
