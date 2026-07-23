package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetLog;

public interface DpDatasetLogMapper {
    List<DpDatasetLog> selectLogList(DpDatasetLog log);
    int insertLog(DpDatasetLog log);
}
