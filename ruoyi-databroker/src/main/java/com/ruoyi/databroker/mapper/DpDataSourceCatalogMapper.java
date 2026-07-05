package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface DpDataSourceCatalogMapper {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);
}
