package com.ruoyi.objectgroup.service;

import java.util.List;
import com.ruoyi.objectgroup.domain.TlTagCodeValue;

public interface ICodeValueService {

    List<TlTagCodeValue> selectCodeValueList(TlTagCodeValue query);

    int insertCodeValue(TlTagCodeValue codeValue);

    int updateCodeValue(TlTagCodeValue codeValue);

    int deleteCodeValueByIds(Long[] valueIds);

    /** 从宽表 SELECT DISTINCT 同步码值 */
    int syncCodeValue(Long libraryId, String fieldName);
}
