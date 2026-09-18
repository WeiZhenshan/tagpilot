package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
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
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportResult;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;

/**
 * rule_init 草稿导入：属于该库、依据未漂移才 upsert DRAFT；拒绝覆盖 REVIEWED。
 */
@ExtendWith(MockitoExtension.class)
class TsBootstrapImportServiceTest extends BaseServiceTest {

    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private TsTagSemanticMapper tagSemanticMapper;
    @Mock
    private TsCodeValueSemanticMapper codeValueMapper;

    @InjectMocks
    private TsBootstrapExportService bootstrapService;

    @Test
    void importInsertsDraftTagAndCode() {
        when(tagMapper.selectTagById(526L)).thenReturn(tag(526L, 107L, "GENDER", "text", "性别口径"));
        when(tagSemanticMapper.selectByTagId(526L)).thenReturn(null);
        when(tagSemanticMapper.insertTagSemantic(any(TsTagSemantic.class))).thenReturn(1);
        when(codeValueMapper.selectByTagIdAndCode(526L, "M")).thenReturn(null);
        when(codeValueMapper.insertCodeValue(any(TsCodeValueSemantic.class))).thenReturn(1);

        BootstrapImportResult result = bootstrapService.importDrafts(request(107L, tagLine() + codeLine()));
        assertEquals(1, result.getImportedTagCount());
        assertEquals(1, result.getImportedCodeCount());
        assertEquals(0, result.getSkippedReviewedCount());

        ArgumentCaptor<TsTagSemantic> captor = ArgumentCaptor.forClass(TsTagSemantic.class);
        verify(tagSemanticMapper).insertTagSemantic(captor.capture());
        TsTagSemantic saved = captor.getValue();
        assertEquals("ENUM_NOMINAL", saved.getSemanticType());
        assertEquals("RULE", saved.getSource());
        assertEquals("DRAFT", saved.getReviewStatus());
        assertNull(saved.getConceptId());
        assertEquals("性别", saved.getRemark());
    }

    @Test
    void importSkipsReviewed() {
        when(tagMapper.selectTagById(526L)).thenReturn(tag(526L, 107L, "GENDER", "text", "性别口径"));
        TsTagSemantic reviewed = new TsTagSemantic();
        reviewed.setTagId(526L);
        reviewed.setReviewStatus("REVIEWED");
        when(tagSemanticMapper.selectByTagId(526L)).thenReturn(reviewed);

        BootstrapImportResult result = bootstrapService.importDrafts(request(107L, tagLine()));
        assertEquals(0, result.getImportedTagCount());
        assertEquals(1, result.getSkippedReviewedCount());
        assertEquals("REVIEWED_SKIP", result.getRejected().get(0).get("code"));
        verify(tagSemanticMapper, never()).updateTagSemantic(any());
        verify(tagSemanticMapper, never()).insertTagSemantic(any());
    }

    @Test
    void importRejectsOtherLibraryAndDrift() {
        when(tagMapper.selectTagById(526L)).thenReturn(tag(526L, 105L, "GENDER", "text", "性别口径"));
        BootstrapImportResult otherLib = bootstrapService.importDrafts(request(107L, tagLine()));
        assertEquals("TAG_NOT_IN_LIBRARY", otherLib.getRejected().get(0).get("code"));

        when(tagMapper.selectTagById(526L)).thenReturn(tag(526L, 107L, "GENDER", "text", "口径已改"));
        BootstrapImportResult drift = bootstrapService.importDrafts(request(107L, tagLine()));
        assertEquals("BASIS_DRIFT", drift.getRejected().get(0).get("code"));
        verify(tagSemanticMapper, never()).insertTagSemantic(any());
    }

    private BootstrapImportRequest request(Long libraryId, String jsonl) {
        BootstrapImportRequest req = new BootstrapImportRequest();
        req.setLibraryId(libraryId);
        req.setJsonl(jsonl);
        return req;
    }

    private TlTag tag(Long tagId, Long libraryId, String field, String dataType, String caliber) {
        TlTag tag = new TlTag();
        tag.setTagId(tagId);
        tag.setLibraryId(libraryId);
        tag.setFieldName(field);
        tag.setDataType(dataType);
        tag.setBusinessCaliber(caliber);
        tag.setTechCaliber("L_INDVCST_LABEL");
        tag.setDelFlag("0");
        return tag;
    }

    private String tagLine() {
        return "{\"kind\":\"tag_semantic\",\"tag_id\":526,\"library_id\":107,\"field_name\":\"GENDER\","
                + "\"semantic_type\":\"ENUM_NOMINAL\",\"allowed_operators\":[\"=\",\"in\",\"not_in\"],"
                + "\"default_operator\":\"=\",\"unit\":\"NONE\",\"unit_scale\":1,"
                + "\"caliber_struct\":{\"statistic\":\"NONE\"},\"concept_candidate\":\"性别\","
                + "\"family_candidate\":\"性别|NONE|ALL|NONE|NONE|BASE\",\"caliber_variant\":\"BASE\","
                + "\"source\":\"RULE\",\"review_status\":\"DRAFT\",\"basis_hash\":\"abc\","
                + "\"authority\":{\"field_name\":\"GENDER\",\"business_caliber\":\"性别口径\","
                + "\"tech_caliber\":\"L_INDVCST_LABEL\",\"data_type\":\"text\"}}\n";
    }

    private String codeLine() {
        return "{\"kind\":\"code_value_semantic\",\"tag_id\":526,\"code\":\"M\",\"rank_no\":1,"
                + "\"source\":\"RULE\",\"review_status\":\"DRAFT\",\"basis_hash\":\"def\"}\n";
    }
}
