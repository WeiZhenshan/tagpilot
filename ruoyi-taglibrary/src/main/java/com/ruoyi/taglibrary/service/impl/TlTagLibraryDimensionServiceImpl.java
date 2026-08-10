package com.ruoyi.taglibrary.service.impl;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TlTagLibraryDimension;
import com.ruoyi.taglibrary.domain.vo.DimensionCandidateVO;
import com.ruoyi.taglibrary.domain.vo.DimensionLibraryVO;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.service.ITlTagLibraryDimensionService;

/**
 * 标签库默认码表（维表关联）Service业务层处理
 *
 * @author ruoyi
 */
@Service
public class TlTagLibraryDimensionServiceImpl implements ITlTagLibraryDimensionService {

    /** 维表状态：0启用 */
    private static final String STATUS_ENABLED = "0";
    /** 删除标志：0存在 */
    private static final String DEL_FLAG_EXIST = "0";
    /** 物理表名合法性（仅字母数字下划线，防注入） */
    private static final Pattern TABLE_NAME_PATTERN = Pattern.compile("^[A-Za-z0-9_]+$");

    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DataBrokerProperties properties;

    @Override
    public List<DimensionCandidateVO> selectCandidates(Long libraryId, String dimensionName) {
        Long libraryDatasourceId = resolveLibraryDatasourceId(libraryId);
        List<DimensionCandidateVO> list = dimensionMapper.selectCandidates(libraryId, libraryDatasourceId, dimensionName);
        for (DimensionCandidateVO row : list) {
            boolean selectable = Boolean.TRUE.equals(row.getSameSource()) && STATUS_ENABLED.equals(row.getStatus());
            row.setSelectable(selectable);
            if (!selectable) {
                if (!Boolean.TRUE.equals(row.getSameSource())) {
                    row.setDisabledReason("与标签库数据源不同源");
                } else {
                    row.setDisabledReason("维表已停用");
                }
            }
        }
        return list;
    }

    @Override
    public List<Long> selectSelectedDimensionIds(Long libraryId) {
        return dimensionMapper.selectDimensionIdsByLibraryId(libraryId);
    }

    @Override
    @Transactional
    public int saveDimensions(Long libraryId, List<Long> dimensionIds) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        Long libraryDatasourceId = resolveLibraryDatasourceId(libraryId);

        // 去重并保持入参顺序
        List<Long> ids = new ArrayList<>(new LinkedHashSet<>(dimensionIds));
        if (!ids.isEmpty()) {
            List<DpDimensionTable> dims = dimensionMapper.selectDimensionsForConflictCheck(ids);
            Map<Long, DpDimensionTable> dimMap = new HashMap<>();
            for (DpDimensionTable dim : dims) {
                dimMap.put(dim.getDimensionId(), dim);
            }
            List<DpDimensionTable> ordered = new ArrayList<>();
            for (Long id : ids) {
                DpDimensionTable dim = dimMap.get(id);
                if (dim == null || !DEL_FLAG_EXIST.equals(dim.getDelFlag())) {
                    throw new ServiceException("维表[ID=" + id + "]不存在或已删除");
                }
                if (!STATUS_ENABLED.equals(dim.getStatus())) {
                    throw new ServiceException("维表[" + dim.getDimensionName() + "]已停用，不能设为默认码表");
                }
                if (!libraryDatasourceId.equals(dim.getDatasourceId())) {
                    throw new ServiceException("维表[" + dim.getDimensionName() + "]与标签库数据源不同源");
                }
                ordered.add(dim);
            }
            // 多张默认维表时做跨表码值冲突校验（表内唯一性由物理表唯一索引保证）
            if (ordered.size() >= 2) {
                checkCodeValueConflicts(libraryDatasourceId, ordered);
            }
        }

        // 覆盖保存：先清空再按入参顺序重建
        dimensionMapper.deleteByLibraryId(libraryId);
        if (ids.isEmpty()) {
            return 0;
        }
        String username = SecurityUtils.getUsername();
        List<TlTagLibraryDimension> relations = new ArrayList<>();
        int order = 0;
        for (Long id : ids) {
            TlTagLibraryDimension relation = new TlTagLibraryDimension();
            relation.setLibraryId(libraryId);
            relation.setDimensionId(id);
            relation.setOrderNum(++order);
            relation.setCreateBy(username);
            relations.add(relation);
        }
        dimensionMapper.batchInsert(relations);
        return relations.size();
    }

    @Override
    public List<DimensionLibraryVO> selectLibrariesByDimensionId(Long dimensionId) {
        return dimensionMapper.selectLibrariesByDimensionId(dimensionId);
    }

    // ---- private helpers ----

    /** 解析标签库的数据源ID，库不存在或数据集无效时报错 */
    private Long resolveLibraryDatasourceId(Long libraryId) {
        Long datasourceId = dimensionMapper.selectLibraryDatasourceId(libraryId);
        if (datasourceId == null) {
            throw new ServiceException("标签库不存在或关联的数据集无效");
        }
        return datasourceId;
    }

    /**
     * 码值冲突校验：连接标签库数据源逐表读取码值，
     * 同一 (tag_name_en, tag_code) 的 code_definition/tag_name_cn 必须完全一致，否则报错
     */
    private void checkCodeValueConflicts(Long datasourceId, List<DpDimensionTable> dims) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(datasourceId);
        if (ds == null) {
            throw new ServiceException("标签库数据源不存在");
        }
        String password = "";
        if (ds.getPasswordCipher() != null && !ds.getPasswordCipher().isEmpty()) {
            password = cryptoService.decrypt(ds.getPasswordCipher());
        }

        // key=(tag_name_en, tag_code) -> [code_definition, tag_name_cn, 来源维表名]
        Map<String, String[]> codeMap = new HashMap<>();
        try (Connection conn = connectionFactory.createConnection(
                ds.getHost(), ds.getPort(), ds.getDatabaseName(), ds.getUsername(), password)) {
            for (DpDimensionTable dim : dims) {
                String tableName = dim.getSourceTableName();
                if (tableName == null || !TABLE_NAME_PATTERN.matcher(tableName).matches()) {
                    throw new ServiceException("维表[" + dim.getDimensionName() + "]的物理表名非法：" + tableName);
                }
                String sql = "select tag_name_en, tag_code, tag_name_cn, code_definition from `" + tableName + "`";
                try (Statement stmt = conn.createStatement()) {
                    stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
                    try (ResultSet rs = stmt.executeQuery(sql)) {
                        while (rs.next()) {
                            String tagNameEn = rs.getString(1);
                            String tagCode = rs.getString(2);
                            if (tagNameEn == null || tagCode == null) {
                                continue;
                            }
                            String nameCn = rs.getString(3);
                            String definition = rs.getString(4);
                            String key = tagNameEn + "\u0001" + tagCode;
                            String[] exist = codeMap.get(key);
                            if (exist == null) {
                                codeMap.put(key, new String[]{definition, nameCn, dim.getDimensionName()});
                            } else if (!Objects.equals(exist[0], definition) || !Objects.equals(exist[1], nameCn)) {
                                throw new ServiceException("维表[" + exist[2] + "]与维表[" + dim.getDimensionName()
                                        + "]存在码值冲突：标签[" + tagNameEn + "]、码值[" + tagCode + "]的定义不一致（"
                                        + exist[0] + " / " + definition + "）");
                            }
                        }
                    }
                }
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            throw new ServiceException("码值冲突校验失败，无法读取维表数据：" + e.getMessage());
        }
    }
}
