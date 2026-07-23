package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetCatalog;

public interface IDpDatasetCatalogService {
    List<DpDatasetCatalog> selectCatalogList(DpDatasetCatalog catalog);
    DpDatasetCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDatasetCatalog catalog);
    int updateCatalog(DpDatasetCatalog catalog);
    int deleteCatalogById(Long catalogId);

    /** 更新目录排序/父子关系（拖拽排序用） */
    int updateCatalogOrder(DpDatasetCatalog catalog);
}
