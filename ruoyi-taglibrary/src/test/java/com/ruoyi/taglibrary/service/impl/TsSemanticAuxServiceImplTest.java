package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.taglibrary.domain.TsBusinessTerm;
import com.ruoyi.taglibrary.domain.TsConfusable;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsAliasMapper;
import com.ruoyi.taglibrary.mapper.TsBusinessTermMapper;
import com.ruoyi.taglibrary.mapper.TsCodeValueSemanticMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsConfusableMapper;
import com.ruoyi.taglibrary.mapper.TsTagExampleMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;

@ExtendWith(MockitoExtension.class)
class TsSemanticAuxServiceImplTest extends BaseServiceTest {

    @Mock private TlTagMapper tagMapper;
    @Mock private TsTagSemanticMapper tagSemanticMapper;
    @Mock private TsConceptMapper conceptMapper;
    @Mock private TsAliasMapper aliasMapper;
    @Mock private TsCodeValueSemanticMapper codeValueMapper;
    @Mock private TsBusinessTermMapper termMapper;
    @Mock private TsConfusableMapper confusableMapper;
    @Mock private TsTagExampleMapper exampleMapper;

    @InjectMocks
    private TsSemanticServiceImpl semanticService;

    @Test
    void saveTermForcesDraftAndNormalizes() {
        when(termMapper.insertTerm(any(TsBusinessTerm.class))).thenReturn(1);
        TsBusinessTerm term = new TsBusinessTerm();
        term.setTerm(" 最 近 ");
        term.setTermType("FUZZY_TIME");
        term.setDefaultPolicy("ASK");
        semanticService.saveTerm(term);
        ArgumentCaptor<TsBusinessTerm> captor = ArgumentCaptor.forClass(TsBusinessTerm.class);
        verify(termMapper).insertTerm(captor.capture());
        assertEquals("DRAFT", captor.getValue().getReviewStatus());
        assertEquals("最近", captor.getValue().getTermNorm());
        assertEquals("客户", captor.getValue().getTagObject());
    }

    @Test
    void generateTimeFacetPairsInsertsOrderedPair() {
        TsTagSemantic a = member(709L, "近30天异名跨行转入标志", "FUND_INFLOW_INTERBANK|FLAG|ALL|NONE|NONE|BASE", "近30天");
        TsTagSemantic b = member(708L, "近7天异名跨行转入标志", "FUND_INFLOW_INTERBANK|FLAG|ALL|NONE|NONE|BASE", "近7天");
        when(tagSemanticMapper.selectByLibraryId(107L)).thenReturn(Arrays.asList(a, b));
        when(confusableMapper.selectByPair(708L, 709L)).thenReturn(null);
        when(confusableMapper.insertPair(any(TsConfusable.class))).thenReturn(1);
        assertEquals(1, semanticService.generateTimeFacetPairs(107L));
        ArgumentCaptor<TsConfusable> captor = ArgumentCaptor.forClass(TsConfusable.class);
        verify(confusableMapper).insertPair(captor.capture());
        assertEquals(Long.valueOf(708L), captor.getValue().getTagIdA());
        assertEquals(Long.valueOf(709L), captor.getValue().getTagIdB());
        assertEquals("TIME_FACET", captor.getValue().getConfusionType());
        assertEquals("RULE", captor.getValue().getSource());
        assertEquals("DRAFT", captor.getValue().getReviewStatus());
    }

    private TsTagSemantic member(Long tagId, String name, String family, String time) {
        TsTagSemantic row = new TsTagSemantic();
        row.setTagId(tagId);
        row.setTagName(name);
        row.setFamilyKey(family);
        row.setSemanticType("BOOL");
        row.setCaliberStruct("{\"time_anchor_label\":\"" + time + "\"}");
        return row;
    }
}
