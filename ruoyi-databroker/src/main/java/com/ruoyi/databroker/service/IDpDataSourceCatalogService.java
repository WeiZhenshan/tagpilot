package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface IDpDataSourceCatalogService {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);
}
