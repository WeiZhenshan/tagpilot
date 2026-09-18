package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsCodeValueSemantic;

public interface TsCodeValueSemanticMapper {
    TsCodeValueSemantic selectByTagIdAndCode(@Param("tagId") Long tagId, @Param("code") String code);

    List<TsCodeValueSemantic> selectByTagId(Long tagId);

    int insertCodeValue(TsCodeValueSemantic row);

    int updateCodeValue(TsCodeValueSemantic row);

    int upsertCodeValueBatch(@Param("list") List<TsCodeValueSemantic> list);
}
