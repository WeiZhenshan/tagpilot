package com.ruoyi.taglibrary.service;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.domain.agent.TsPlanValidationException;
import com.ruoyi.taglibrary.mapper.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class TsAudiencePlanCompilerTest {
    @Mock ITsCatalogRuntimeService catalog;
    @Mock TsCatalogSnapshotMapper snapshots;
    @Mock TsSnapshotArtifactStore artifacts;
    @Mock TlTagMapper tags;
    @Spy ObjectMapper json=new ObjectMapper();
    @InjectMocks TsAudiencePlanCompiler compiler;
    @TempDir Path dir;
    @BeforeEach void setup() throws Exception {
        lenient().when(catalog.activeBundle(107L)).thenReturn(map("build_id","b1","snapshot_id","s1","artifact_hash","h1"));
        lenient().when(catalog.eligibleTagIds(107L,"s1")).thenReturn(Arrays.asList(1L));
        Path file=dir.resolve("snapshot.jsonl");
        Files.write(file,(json.writeValueAsString(map("kind","tag","tag_id",1,"unit","CNY","unit_scale",1,"allowed_operators",Arrays.asList(">","<"),"caliber_struct",map("calendar_mode","ROLLING")))+"\n").getBytes(StandardCharsets.UTF_8));
        TsCatalogSnapshot snapshot=new TsCatalogSnapshot();
        lenient().when(snapshots.selectById("s1")).thenReturn(snapshot);lenient().when(artifacts.verifiedPath(snapshot)).thenReturn(file);
        TlTag tag=new TlTag();tag.setTagId(1L);tag.setLibraryId(107L);tag.setFieldName("trusted_amount");tag.setTagName("金额");tag.setTagType("数值型");
        lenient().when(tags.selectTagById(1L)).thenReturn(tag);
    }
    Map<String,Object> leaf(String id){return map("clause_id",id,"tag_id",1,"operator",">","values",Arrays.asList("500000"),"value_unit","CNY","value_scale","1","fieldName","forged_column");}
    Map<String,Object> plan(Object tree){return map("build_id","b1","snapshot_id","s1","artifact_hash","h1","tree",tree);}
    @Test void nestedLogicPreservesParenthesesAndUsesTrustedFields() {
        Map<String,Object> tree=map("logic","AND","children",Arrays.asList(leaf("a"),map("logic","OR","children",Arrays.asList(leaf("b"),leaf("c")))));
        RulePayload r=compiler.compile(107L,plan(tree));
        assertEquals(3,r.getSchemaVersion());assertEquals(3,r.getConditions().size());
        assertEquals("trusted_amount",r.getConditions().get(0).getFieldName());
        assertEquals("AND",r.getConditions().get(1).getConnector());assertEquals("OR",r.getConditions().get(2).getConnector());
        assertEquals(1,r.getConditions().get(0).getOpenParen());assertEquals(1,r.getConditions().get(1).getOpenParen());assertEquals(2,r.getConditions().get(2).getCloseParen());
        assertEquals(1,r.getPreviewColumns().size());
    }
    @Test void currentVersionAndEligibilityAreRechecked() {
        Map<String,Object> p=plan(leaf("a"));p.put("build_id","old");
        assertThrows(ServiceException.class,()->compiler.compile(107L,p));
        when(catalog.eligibleTagIds(107L,"s1")).thenReturn(Collections.emptyList());
        assertThrows(ServiceException.class,()->compiler.compile(107L,plan(leaf("a"))));
    }
    @Test void unitsTimeAndRepeatedClauseCannotBeForged() {
        Map<String,Object> leaf=leaf("a");leaf.put("value_scale","10000");
        assertThrows(ServiceException.class,()->compiler.compile(107L,plan(leaf)));
        leaf.put("value_scale","1");leaf.put("time_constraint","上月");leaf.put("expected_caliber",map("calendar_mode","CALENDAR"));
        assertThrows(ServiceException.class,()->compiler.compile(107L,plan(leaf)));
        assertThrows(ServiceException.class,()->compiler.compile(107L,plan(map("logic","AND","children",Arrays.asList(leaf("a"),leaf("a"))))));
    }
    @Test void modernIntentAndLogicalStructureAreMandatory() {
        Map<String,Object> p=plan(leaf("a"));p.put("schema_version",3);
        assertThrows(ServiceException.class,()->compiler.compile(107L,p));
        p.put("intent_plan",map("requirements",Arrays.asList(map("requirement_id","a")),"logic_tree",map("requirement_id","a")));
        assertEquals(4,compiler.compile(107L,p).getSchemaVersion());
        p.put("tree",map("logic","OR","children",Arrays.asList(leaf("a"),leaf("b"))));
        p.put("intent_plan",map("requirements",Arrays.asList(map("requirement_id","a"),map("requirement_id","b")),"logic_tree",map("logic","AND","children",Arrays.asList(map("requirement_id","a"),map("requirement_id","b")))));
        assertThrows(ServiceException.class,()->compiler.compile(107L,p));
    }

    @Test void structuredDiagnosticsCarryCodeAndClause() {
        Map<String,Object> scaled=leaf("a");scaled.put("value_scale","10000");
        TsPlanValidationException unit=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,plan(scaled)));
        assertEquals("UNIT_MISMATCH",unit.getDiagnosticCode());assertEquals("a",unit.getClauseId());

        Map<String,Object> op=leaf("a");op.put("operator",">=");
        TsPlanValidationException operator=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,plan(op)));
        assertEquals("INVALID_OPERATOR",operator.getDiagnosticCode());assertEquals("a",operator.getClauseId());

        Map<String,Object> gap=leaf("a");gap.put("status","GAP");
        TsPlanValidationException missing=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,plan(gap)));
        assertEquals("REQUIREMENT_MISSING",missing.getDiagnosticCode());assertEquals("a",missing.getClauseId());

        Map<String,Object> assumed=leaf("a");assumed.put("status","ASSUMED");
        TsPlanValidationException decision=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,plan(assumed)));
        assertEquals("BUSINESS_AMBIGUITY",decision.getDiagnosticCode());assertEquals("a",decision.getClauseId());

        when(catalog.eligibleTagIds(107L,"s1")).thenReturn(Collections.emptyList());
        TsPlanValidationException ineligible=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,plan(leaf("a"))));
        assertEquals("INELIGIBLE_TAG",ineligible.getDiagnosticCode());assertEquals("a",ineligible.getClauseId());

        Map<String,Object> version=plan(leaf("a"));version.put("build_id","old");
        TsPlanValidationException mismatch=assertThrows(TsPlanValidationException.class,()->compiler.compile(107L,version));
        assertEquals("VERSION_MISMATCH",mismatch.getDiagnosticCode());assertNull(mismatch.getClauseId());
    }
}
