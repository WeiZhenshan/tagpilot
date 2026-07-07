package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface IDpDataSourceCatalogService {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);

    /** 更新目录排序/父子关系（拖拽排序用） */
    int updateCatalogOrder(DpDataSourceCatalog catalog);
}
