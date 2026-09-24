package com.ruoyi.taglibrary.domain.agent;

import com.ruoyi.common.exception.ServiceException;

/** 可回灌 Agent 的结构化诊断；沿用 ServiceException 的外部异常语义。 */
public class TsPlanValidationException extends ServiceException {
    private final String diagnosticCode;
    private final String clauseId;
    public TsPlanValidationException(String code, String clauseId, String message) {
        super(message); this.diagnosticCode=code; this.clauseId=clauseId;
    }
    public String getDiagnosticCode() { return diagnosticCode; }
    public String getClauseId() { return clauseId; }
    public TsPlanValidationException atClause(String id) {
        return new TsPlanValidationException(diagnosticCode, id, getMessage());
    }
}
