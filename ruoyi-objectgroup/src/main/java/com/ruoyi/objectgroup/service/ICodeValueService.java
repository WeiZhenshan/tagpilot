package com.ruoyi.objectgroup.service;

import java.util.List;
import com.ruoyi.objectgroup.domain.TlTagCodeValue;
import com.ruoyi.objectgroup.domain.vo.CodeValueSyncVO;

public interface ICodeValueService {

    List<TlTagCodeValue> selectCodeValueList(TlTagCodeValue query);

    int insertCodeValue(TlTagCodeValue codeValue);

    int updateCodeValue(TlTagCodeValue codeValue);

    int deleteCodeValueByIds(Long[] valueIds);

    /** 从宽表 SELECT DISTINCT 同步码值：全量对齐（清理宽表已消失码值），超上限截断并标记 */
    CodeValueSyncVO syncCodeValue(Long libraryId, String fieldName);
}
