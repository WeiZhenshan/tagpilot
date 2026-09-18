package com.ruoyi.taglibrary.mapper;

import java.util.List;
import com.ruoyi.taglibrary.domain.TsIndexBuild;

public interface TsIndexBuildMapper {
    TsIndexBuild selectById(String buildId);

    TsIndexBuild selectActiveBySnapshotId(String snapshotId);

    List<TsIndexBuild> selectBySnapshotId(String snapshotId);

    int insertBuild(TsIndexBuild build);

    int updateBuild(TsIndexBuild build);

    int retireActiveBySnapshotId(String snapshotId);
}
