package com.ruoyi.taglibrary.mapper;

import java.util.List;
import com.ruoyi.taglibrary.domain.TlAuditLog;

public interface TlAuditLogMapper {
    int insertAuditLog(TlAuditLog auditLog);

    List<TlAuditLog> selectAuditLogList(TlAuditLog query);
}
