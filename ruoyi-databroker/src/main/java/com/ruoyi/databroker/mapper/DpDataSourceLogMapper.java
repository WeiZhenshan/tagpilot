package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceLog;

public interface DpDataSourceLogMapper {
    List<DpDataSourceLog> selectLogList(DpDataSourceLog log);
    int insertLog(DpDataSourceLog log);
}
