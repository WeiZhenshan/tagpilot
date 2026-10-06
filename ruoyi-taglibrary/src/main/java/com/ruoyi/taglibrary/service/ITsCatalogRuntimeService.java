package com.ruoyi.taglibrary.service;

import java.util.List;
import java.util.Map;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import com.ruoyi.taglibrary.domain.TsIndexBuild;

public interface ITsCatalogRuntimeService {
    TsCatalogSnapshot publish(Long libraryId, String coverageNote);

    List<Long> eligibleTagIds(Long libraryId, String snapshotId);

    TsCatalogSnapshot activeSnapshot(Long libraryId);

    TsIndexBuild registerBuild(TsIndexBuild build);

    TsIndexBuild updateBuildStatus(String buildId, String status, String evalSummary);

    TsIndexBuild activate(String buildId);

    Map<String, Object> activeBundle(Long libraryId);

    /** 必须在保存事务内调用，按 library → snapshot → build 取得当前发布信封。 */
    Map<String, Object> activeBundleForUpdate(Long libraryId);
}
