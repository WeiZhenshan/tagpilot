package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsBusinessTerm;

public interface TsBusinessTermMapper {
    TsBusinessTerm selectTermById(Long termId);

    List<TsBusinessTerm> selectTermList(@Param("termNorm") String termNorm, @Param("termType") String termType);

    TsBusinessTerm selectByNorm(@Param("termNorm") String termNorm, @Param("termType") String termType,
            @Param("tagObject") String tagObject);

    int insertTerm(TsBusinessTerm term);

    int updateTerm(TsBusinessTerm term);
}
