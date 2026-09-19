package com.ruoyi.taglibrary.service;

import java.util.*;
import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.domain.dto.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.*;

@ExtendWith(MockitoExtension.class)
class TsSnapshotAssemblerTest {
    @Mock ITsBootstrapService bootstrap;
    @Mock ITsSemanticService semantics;
    @Mock com.ruoyi.taglibrary.mapper.TsTagProfileMapper profiles;
    @InjectMocks TsSnapshotAssembler assembler;

    @Test void exportsClosedReviewedCatalogAndRejectsDrift() throws Exception {
        Map<String, Object> authority = map("kind", "tag", "tag_id", 1L, "library_id", 107L, "name", "性别", "field_name", "GENDER", "data_type", "varchar", "version", 1, "status", "2", "source_status", "AVAILABLE", "is_object_key", "0");
        Map<String, Object> code = map("kind", "code_value", "tag_id", 1L, "code", "01", "label", "女性", "definition", "女性客户");
        BootstrapExportResult freeze = new BootstrapExportResult();
        freeze.setJsonl(json(map("kind", "meta", "source_manifest", map("version_id", 12))) + "\n" + json(authority) + "\n" + json(code) + "\n");
        freeze.setContentHash("freeze"); freeze.setIssues(Collections.emptyList());
        when(bootstrap.exportFreeze(any())).thenReturn(freeze);
        TsConcept concept = new TsConcept(); concept.setConceptId(7L); concept.setConceptCode("GENDER"); concept.setConceptName("性别"); concept.setReviewStatus("REVIEWED"); concept.setStatus("0"); concept.setLibraryId(107L);
        when(semantics.selectConceptList(any())).thenReturn(Collections.singletonList(concept));
        TsTagSemantic tag = new TsTagSemantic(); tag.setTagId(1L); tag.setConceptId(7L); tag.setReviewStatus("REVIEWED"); tag.setSemanticType("ENUM_NOMINAL");
        tag.setAllowedOperators("[\"EQ\"]"); tag.setCaliberStruct("{\"statistic\":\"NONE\"}"); tag.setDefinitionLong("客户性别信息"); tag.setFamilyKey("GENDER|NONE|ALL|NONE|NONE|BASE");
        tag.setBasisHash(basisHash(authority, Collections.singletonList(code)));
        when(semantics.selectTagSemanticByLibraryId(107L)).thenReturn(Collections.singletonList(tag));
        TsCodeValueSemantic cv = new TsCodeValueSemantic(); cv.setTagId(1L); cv.setCode("01"); cv.setReviewStatus("REVIEWED"); cv.setBasisHash(codeBasisHash(1L, code, tag.getBasisHash()));
        when(semantics.selectCodeValuesByTagId(1L)).thenReturn(Collections.singletonList(cv));
        TsAlias alias = new TsAlias(); alias.setTargetType("TAG"); alias.setTargetId("1"); alias.setAliasText("性别信息"); alias.setAliasNorm("性别信息"); alias.setAliasType("SYNONYM"); alias.setReviewStatus("REVIEWED");
        TsAlias alias2 = new TsAlias(); alias2.setTargetType("TAG"); alias2.setTargetId("1"); alias2.setAliasText("客户性别"); alias2.setAliasNorm("客户性别"); alias2.setReviewStatus("REVIEWED");
        TsAlias alias3 = new TsAlias(); alias3.setTargetType("TAG"); alias3.setTargetId("1"); alias3.setAliasText("性别类别"); alias3.setAliasNorm("性别类别"); alias3.setReviewStatus("REVIEWED");
        when(semantics.selectAliasList("TAG", "1")).thenReturn(Arrays.asList(alias, alias2, alias3));
        TsBusinessTerm term = new TsBusinessTerm(); term.setTermId(1L); term.setTerm("最近"); term.setTermNorm("最近"); term.setTermType("TIME"); term.setOptions("[]"); term.setApplicableSemanticTypes("NUM_AMOUNT,BOOL"); term.setDefaultPolicy("CLARIFY"); term.setReviewStatus("REVIEWED");
        when(semantics.selectTermList(null, null)).thenReturn(Collections.singletonList(term));
        Result result = assembler.assemble(107L, "测试目录");
        assertEquals(1, result.codes); assertEquals(1, result.concepts); assertEquals(3, result.aliases);
        assertEquals("1/1", result.report.get("coverage"));
        result.rows.get(0).put("snapshot_id", "JAVA-CONTRACT");
        result.rows.get(0).put("content_hash", TsSnapshotCanonicalizer.contentHash(result.rows));
        StringBuilder lines = new StringBuilder(); for (Map<String, Object> row : result.rows) lines.append(json(row)).append('\n');
        String output = System.getProperty("semantic.contract.output");
        if (output != null) Files.write(Paths.get(output), lines.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        alias3.setAliasNorm("客户性别");
        assertTrue(assembler.assemble(107L, null).report.get("excluded").toString().contains("INSUFFICIENT_ALIASES"));
        alias3.setAliasNorm("性别类别");
        tag.setAllowedOperators("[]");
        assertTrue(assembler.assemble(107L, null).report.get("excluded").toString().contains("CORE_SEMANTICS_MISSING"));
        tag.setAllowedOperators("[\"EQ\"]");
        authority.put("name", "性别口径已变更");
        freeze.setJsonl(json(map("kind", "meta", "source_manifest", map("version_id", 12))) + "\n" + json(authority) + "\n" + json(code) + "\n");
        assertEquals(false, assembler.assemble(107L, null).report.get("publishable"));
    }

    @Test void ordinalIntervalsRejectGapsAndOverlaps() {
        TsCodeValueSemantic a = new TsCodeValueSemantic(), b = new TsCodeValueSemantic();
        for (TsCodeValueSemantic c : Arrays.asList(a, b)) { c.setReviewStatus("REVIEWED"); c.setBoundUnit("元"); c.setLowerInclusive(1); c.setUpperInclusive(0); }
        a.setRankNo(1); a.setLowerBound(java.math.BigDecimal.ZERO); a.setUpperBound(java.math.BigDecimal.TEN);
        b.setRankNo(2); b.setLowerBound(java.math.BigDecimal.TEN);
        TsSnapshotAssembler.validateIntervals(Arrays.asList(a, b));
        a.setUpperInclusive(1);
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> TsSnapshotAssembler.validateIntervals(Arrays.asList(a, b)));
        a.setUpperInclusive(0); b.setLowerBound(new java.math.BigDecimal("11"));
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> TsSnapshotAssembler.validateIntervals(Arrays.asList(a, b)));
    }

    @Test void ordinalRanksDoNotInventNumericIntervals() {
        TsCodeValueSemantic a = new TsCodeValueSemantic(), b = new TsCodeValueSemantic();
        a.setReviewStatus("REVIEWED"); b.setReviewStatus("REVIEWED");
        a.setRankNo(1); b.setRankNo(2);
        assertDoesNotThrow(() -> validateOrdinal(Arrays.asList(a, b)));
        b.setRankNo(1);
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> validateOrdinal(Arrays.asList(a, b)));
        b.setRankNo(2); b.setLowerBound(java.math.BigDecimal.TEN);
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> validateOrdinal(Arrays.asList(a, b)));
    }

    @Test void ordinalIntervalsAllowOpenEndedFirstAndLastBuckets() {
        TsCodeValueSemantic first = new TsCodeValueSemantic(), middle = new TsCodeValueSemantic(), last = new TsCodeValueSemantic();
        for (TsCodeValueSemantic c : Arrays.asList(first, middle, last)) { c.setReviewStatus("REVIEWED"); c.setBoundUnit("CNY"); }
        first.setRankNo(1); first.setUpperBound(new java.math.BigDecimal("500000")); first.setUpperInclusive(0);
        middle.setRankNo(2); middle.setLowerBound(new java.math.BigDecimal("500000")); middle.setLowerInclusive(1);
        middle.setUpperBound(new java.math.BigDecimal("1000000")); middle.setUpperInclusive(0);
        last.setRankNo(3); last.setLowerBound(new java.math.BigDecimal("1000000")); last.setLowerInclusive(1);
        assertDoesNotThrow(() -> validateIntervals(Arrays.asList(first, middle, last)));
    }

    @Test void reviewedDirectBooleanDoesNotRequireInventedCodeTable() {
        TsTagSemantic tag = new TsTagSemantic(); tag.setSemanticType("BOOL");
        assertTrue(codesReady(tag, Collections.emptyList(), Collections.emptyList()));
        tag.setSemanticType("ENUM_NOMINAL");
        assertFalse(codesReady(tag, Collections.emptyList(), Collections.emptyList()));
    }

    @Test void businessStatusAndNestedFieldsParticipateInHash() {
        Map<String, Object> row = map("kind", "tag", "tag_id", 1, "status", "2", "nested", map("status", "ACTIVE", "snapshot_id", "business-id"));
        String first = TsSnapshotCanonicalizer.contentHash(Collections.singletonList(row));
        row.put("status", "0"); assertNotEquals(first, TsSnapshotCanonicalizer.contentHash(Collections.singletonList(row)));
        row.put("status", "2"); row.put("nested", map("status", "ACTIVE", "snapshot_id", "changed"));
        assertNotEquals(first, TsSnapshotCanonicalizer.contentHash(Collections.singletonList(row)));
    }
}
