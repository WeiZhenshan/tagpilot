package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsConcept;

public interface TsConceptMapper {
    TsConcept selectConceptById(Long conceptId);

    List<TsConcept> selectConceptList(TsConcept query);

    TsConcept selectByLibraryAndCode(@Param("libraryId") Long libraryId, @Param("conceptCode") String conceptCode);

    int insertConcept(TsConcept concept);

    int updateConcept(TsConcept concept);
}
