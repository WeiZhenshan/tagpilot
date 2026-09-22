package com.ruoyi.taglibrary.mapper;

import java.util.List;
import com.ruoyi.taglibrary.domain.TsTagExample;

public interface TsTagExampleMapper {
    TsTagExample selectById(Long exampleId);

    List<TsTagExample> selectByTagId(Long tagId);

    int insertExample(TsTagExample example);

    int updateExample(TsTagExample example);
}
