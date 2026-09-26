package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsAlias;

public interface TsAliasMapper {
    TsAlias selectAliasById(Long aliasId);

    List<TsAlias> selectAliasList(@Param("targetType") String targetType, @Param("targetId") String targetId);

    List<TsAlias> selectAliasListByLibrary(@Param("libraryId") Long libraryId, @Param("targetType") String targetType,
            @Param("targetId") String targetId);

    TsAlias selectByTargetNorm(@Param("targetType") String targetType, @Param("targetId") String targetId,
            @Param("aliasNorm") String aliasNorm);

    int insertAlias(TsAlias alias);

    int updateAlias(TsAlias alias);
}
