package com.ruoyi.databroker.service.impl;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper;
import com.ruoyi.databroker.service.IDpDataSourceCatalogService;

@Service
public class DpDataSourceCatalogServiceImpl implements IDpDataSourceCatalogService {

    @Autowired
    private DpDataSourceCatalogMapper catalogMapper;

    @Override
    public List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog) {
        return catalogMapper.selectCatalogList(catalog);
    }

    @Override
    public DpDataSourceCatalog selectCatalogById(Long catalogId) {
        return catalogMapper.selectCatalogById(catalogId);
    }

    @Override
    public int insertCatalog(DpDataSourceCatalog catalog) {
        return catalogMapper.insertCatalog(catalog);
    }

    @Override
    public int updateCatalog(DpDataSourceCatalog catalog) {
        return catalogMapper.updateCatalog(catalog);
    }

    @Override
    public int deleteCatalogById(Long catalogId) {
        return catalogMapper.deleteCatalogById(catalogId);
    }
}
