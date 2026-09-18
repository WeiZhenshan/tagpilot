package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertTrue;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.service.TsCompletenessScorer;

class TsCompletenessScorerTest {
    @Test
    void goldTagReachesNinety() {
        TsTagSemantic tag = new TsTagSemantic();
        tag.setSemanticType("NUM_AMOUNT");
        tag.setAllowedOperators("[\">\"]");
        tag.setCaliberStruct("{\"statistic\":\"EOP\",\"scope\":\"ALL\"}");
        tag.setConceptId(1L);
        tag.setReviewStatus("REVIEWED");
        tag.setDefinitionLong("当前时点资产管理规模");
        TsConcept concept = new TsConcept();
        concept.setReviewStatus("REVIEWED");
        concept.setStatus("0");
        TsAlias a = new TsAlias();
        a.setReviewStatus("REVIEWED");
        a.setAliasType("FORMAL");
        TsAlias b = new TsAlias();
        b.setReviewStatus("REVIEWED");
        b.setAliasType("COLLOQUIAL");
        TsAlias c = new TsAlias();
        c.setReviewStatus("REVIEWED");
        c.setAliasType("COLLOQUIAL");
        int score = TsCompletenessScorer.score(tag, concept, Arrays.asList(a, b, c), null, true, true);
        assertTrue(score >= 90);
        assertTrue(TsCompletenessScorer.publishReady(score, true));
    }
}
