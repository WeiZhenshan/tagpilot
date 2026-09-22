package com.ruoyi.taglibrary.service;

import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportResult;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportResult;

/**
 * 语义冻结导出 / 规则草稿导入
 */
public interface ITsBootstrapService {
    BootstrapExportResult exportFreeze(BootstrapExportRequest request);

    BootstrapImportResult importDrafts(BootstrapImportRequest request);
}
