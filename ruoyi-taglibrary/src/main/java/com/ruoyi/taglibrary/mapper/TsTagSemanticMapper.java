package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsTagSemantic;

public interface TsTagSemanticMapper {
    TsTagSemantic selectByTagId(Long tagId);

    List<TsTagSemantic> selectByLibraryId(Long libraryId);

    int insertTagSemantic(TsTagSemantic semantic);

    int updateTagSemantic(TsTagSemantic semantic);

    int upsertTagSemanticBatch(@Param("list") List<TsTagSemantic> list);
}
