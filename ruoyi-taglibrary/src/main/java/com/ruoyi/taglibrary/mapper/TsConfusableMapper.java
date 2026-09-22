package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsConfusable;

public interface TsConfusableMapper {
    TsConfusable selectById(Long pairId);

    TsConfusable selectByPair(@Param("tagIdA") Long tagIdA, @Param("tagIdB") Long tagIdB);

    List<TsConfusable> selectByTagId(Long tagId);

    int insertPair(TsConfusable pair);

    int updatePair(TsConfusable pair);
}
