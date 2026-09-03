package com.ruoyi.taglibrary.service.impl;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.mapper.TlAuditLogMapper;

/**
 * 审计留痕写入器：独立事务落库，审批/提交等业务事务回滚时留痕不随之丢失。
 * 独立 bean 保证注入方经代理调用，REQUIRES_NEW 生效。
 */
@Service
public class AuditLogService {

    @Autowired
    private TlAuditLogMapper auditLogMapper;

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void record(TlAuditLog log) {
        auditLogMapper.insertAuditLog(log);
    }
}
