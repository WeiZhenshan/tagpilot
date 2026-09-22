package com.ruoyi.taglibrary.mapper;
import com.ruoyi.taglibrary.domain.TsTagProfile;
public interface TsTagProfileMapper {
    TsTagProfile selectLatest(Long tagId);
    int upsert(TsTagProfile profile);
}
