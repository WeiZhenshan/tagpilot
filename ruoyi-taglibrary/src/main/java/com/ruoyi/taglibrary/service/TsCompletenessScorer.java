package com.ruoyi.taglibrary.service;

import java.util.List;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsTagSemantic;

/**
 * 语义完整度 §9.1
 */
public final class TsCompletenessScorer {
    private TsCompletenessScorer() {
    }

    public static int score(TsTagSemantic tag, TsConcept concept, List<TsAlias> aliases,
            List<TsCodeValueSemantic> codes, boolean hasReviewedConfusable, boolean hasPosExample) {
        int score = 0;
        if (tag.getSemanticType() != null && ("ID_KEY".equals(tag.getSemanticType()) || notEmpty(tag.getAllowedOperators()))) {
            score += 15;
        }
        if (notEmpty(tag.getCaliberStruct())) {
            score += 20;
        }
        if (concept != null && "REVIEWED".equals(concept.getReviewStatus()) && "0".equals(concept.getStatus())
                && tag.getConceptId() != null) {
            score += 10;
        }
        int aliasCount = 0;
        if (aliases != null) {
            for (TsAlias alias : aliases) {
                if ("REVIEWED".equals(alias.getReviewStatus()) && !"NEGATIVE".equals(alias.getAliasType())) {
                    aliasCount++;
                }
            }
        }
        score += aliasCount >= 3 ? 20 : Math.min(20, aliasCount * 7);
        if ("REVIEWED".equals(tag.getReviewStatus()) && notEmpty(tag.getDefinitionLong()) && tag.getDefinitionLong().trim().length() >= 4) {
            score += 10;
        }
        if (isEnum(tag.getSemanticType())) {
            boolean allReviewed = codes != null && !codes.isEmpty();
            if (codes != null) {
                for (TsCodeValueSemantic code : codes) {
                    if (!"REVIEWED".equals(code.getReviewStatus())) {
                        allReviewed = false;
                        break;
                    }
                }
            }
            if (allReviewed) {
                score += 10;
            }
        } else {
            score += 10;
        }
        if (hasReviewedConfusable || "ID_KEY".equals(tag.getSemanticType()) || "TEXT_FREE".equals(tag.getSemanticType())) {
            score += 10;
        } else {
            score += 10;
        }
        if (hasPosExample) {
            score += 5;
        }
        return Math.min(100, score);
    }

    public static boolean publishReady(int score, boolean gold) {
        return score >= (gold ? 90 : 70);
    }

    private static boolean isEnum(String type) {
        return "BOOL".equals(type) || "ENUM_NOMINAL".equals(type) || "ENUM_ORDINAL".equals(type) || "ENUM_HIERARCHY".equals(type);
    }

    private static boolean notEmpty(String value) {
        return value != null && !value.isEmpty();
    }
}
