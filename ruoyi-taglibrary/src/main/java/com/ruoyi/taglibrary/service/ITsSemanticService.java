package com.ruoyi.taglibrary.service;

import java.util.List;
import com.ruoyi.taglibrary.domain.TsAlias;
import com.ruoyi.taglibrary.domain.TsBusinessTerm;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsConfusable;
import com.ruoyi.taglibrary.domain.TsTagExample;
import com.ruoyi.taglibrary.domain.TsTagSemantic;

/**
 * 标签语义草稿维护
 */
public interface ITsSemanticService {
    TsTagSemantic selectTagSemanticByTagId(Long tagId);

    List<TsTagSemantic> selectTagSemanticByLibraryId(Long libraryId);

    int saveTagSemantic(TsTagSemantic semantic);

    int reviewTagSemantic(Long tagId, String sourceRef);

    TsConcept selectConceptById(Long conceptId);

    List<TsConcept> selectConceptList(TsConcept query);

    int saveConcept(TsConcept concept);

    int reviewConcept(Long conceptId, String sourceRef);

    TsAlias selectAliasById(Long aliasId);

    List<TsAlias> selectAliasList(String targetType, String targetId);

    int saveAlias(TsAlias alias);

    int reviewAlias(Long aliasId, String sourceRef);

    List<TsCodeValueSemantic> selectCodeValuesByTagId(Long tagId);

    int saveCodeValue(TsCodeValueSemantic row);

    int reviewCodeValue(Long tagId, String code, String sourceRef);

    List<TsBusinessTerm> selectTermList(String termNorm, String termType);

    int saveTerm(TsBusinessTerm term);

    int reviewTerm(Long termId, String sourceRef);

    List<TsConfusable> selectConfusableByTagId(Long tagId);

    int saveConfusable(TsConfusable pair);

    int reviewConfusable(Long pairId, String sourceRef);

    int generateTimeFacetPairs(Long libraryId);

    List<TsTagExample> selectExamplesByTagId(Long tagId);

    int saveExample(TsTagExample example);

    int reviewExample(Long exampleId, String sourceRef);
}
