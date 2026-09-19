package com.ruoyi.taglibrary.service;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

@Service
public class TsIndexMaintenanceService {
    @Autowired private TsCatalogSnapshotMapper snapshots;
    @Autowired private TsIndexBuildMapper builds;
    @Autowired private TsRuntimeClient runtime;

    @Transactional
    public List<String> cleanup(Long libraryId) {
        if (snapshots.lockLibrary(libraryId) == null) throw new ServiceException("标签库不存在");
        List<TsIndexBuild> all = builds.selectByLibraryId(libraryId);
        Set<String> keep = new HashSet<>();
        int recent = 0;
        for (TsIndexBuild build : all) {
            if ("ACTIVE".equals(build.getStatus())) keep.add(build.getBuildId());
            if (Arrays.asList("ACTIVE", "READY", "RETIRED").contains(build.getStatus()) && recent++ < 3) keep.add(build.getBuildId());
        }
        List<String> purged = new ArrayList<>();
        for (TsIndexBuild build : all) if ("RETIRED".equals(build.getStatus()) && !keep.contains(build.getBuildId())) {
            runtime.post("/drop", map("library_id", libraryId, "snapshot_id", build.getSnapshotId(), "build_id", build.getBuildId(), "store_type", build.getStoreType()));
            build.setStatus("PURGED"); builds.updateBuild(build); purged.add(build.getBuildId());
        }
        return purged;
    }
    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.REQUIRES_NEW)
    public Map<String, Object> reconcile(Long libraryId) {
        if (snapshots.lockLibrary(libraryId) == null) throw new ServiceException("标签库不存在");
        TsCatalogSnapshot snapshot = snapshots.selectActiveByLibraryId(libraryId);
        if (snapshot == null) {
            // 首次激活后 JVM 崩溃可能只留下 alias；数据库没有 ACTIVE 即不得保留路由。
            List<String> checked = new ArrayList<>();
            for (TsIndexBuild candidate : builds.selectByLibraryId(libraryId)) {
                if (!"MILVUS".equals(candidate.getStoreType()) || "PURGED".equals(candidate.getStatus()) || "BUILDING".equals(candidate.getStatus()) || "FAILED".equals(candidate.getStatus())) continue;
                runtime.post("/deactivate", map("library_id", libraryId, "snapshot_id", candidate.getSnapshotId(), "build_id", candidate.getBuildId(), "store_type", candidate.getStoreType()));
                checked.add(candidate.getBuildId());
            }
            return map("status", "NO_ACTIVE", "checked_build_ids", checked);
        }
        TsIndexBuild build = builds.selectActiveBySnapshotId(snapshot.getSnapshotId());
        if (build == null) throw new ServiceException("无 ACTIVE 构建");
        if (!"MILVUS".equals(build.getStoreType())) {
            for (TsIndexBuild candidate : builds.selectByLibraryId(libraryId)) {
                if ("MILVUS".equals(candidate.getStoreType()) && Arrays.asList("READY", "ACTIVE", "RETIRED").contains(candidate.getStatus()))
                    runtime.post("/deactivate", map("library_id", libraryId, "snapshot_id", candidate.getSnapshotId(), "build_id", candidate.getBuildId(), "store_type", candidate.getStoreType()));
            }
        }
        return runtime.post("/activate", map("library_id", libraryId, "snapshot_id", snapshot.getSnapshotId(), "build_id", build.getBuildId(), "store_type", build.getStoreType()));
    }
}
