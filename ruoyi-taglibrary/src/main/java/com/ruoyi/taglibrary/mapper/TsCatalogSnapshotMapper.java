package com.ruoyi.taglibrary.mapper;

import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;

public interface TsCatalogSnapshotMapper {
    TsCatalogSnapshot selectById(String snapshotId);

    TsCatalogSnapshot selectActiveByLibraryId(Long libraryId);

    Integer selectMaxSnapshotNo(Long libraryId);

    int insertSnapshot(TsCatalogSnapshot snapshot);

    int updateSnapshot(TsCatalogSnapshot snapshot);

    int retireActive(@Param("libraryId") Long libraryId, @Param("exceptId") String exceptId);
}
