package com.ruoyi.databroker.service.impl;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataset;
import com.ruoyi.databroker.domain.DpDatasetCatalog;
import com.ruoyi.databroker.domain.DpDatasetDependency;
import com.ruoyi.databroker.domain.DpDatasetField;
import com.ruoyi.databroker.domain.DpDatasetLog;
import com.ruoyi.databroker.domain.DpDatasetVersion;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.CopyVersionRequest;
import com.ruoyi.databroker.domain.dto.PreviewRequest;
import com.ruoyi.databroker.domain.dto.PublishRequest;
import com.ruoyi.databroker.domain.dto.SaveDraftRequest;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.PreviewResultVO;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.mapper.DpDatasetCatalogMapper;
import com.ruoyi.databroker.mapper.DpDatasetDependencyMapper;
import com.ruoyi.databroker.mapper.DpDatasetFieldMapper;
import com.ruoyi.databroker.mapper.DpDatasetLogMapper;
import com.ruoyi.databroker.mapper.DpDatasetMapper;
import com.ruoyi.databroker.mapper.DpDatasetVersionMapper;
import com.ruoyi.databroker.mapper.DpMetaColumnMapper;
import com.ruoyi.databroker.mapper.DpMetaTableMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.IDpDatasetService;

@Service
public class DpDatasetServiceImpl implements IDpDatasetService {

    @Autowired
    private DpDatasetMapper datasetMapper;
    @Autowired
    private DpDatasetCatalogMapper catalogMapper;
    @Autowired
    private DpDatasetVersionMapper versionMapper;
    @Autowired
    private DpDatasetFieldMapper fieldMapper;
    @Autowired
    private DpDatasetDependencyMapper dependencyMapper;
    @Autowired
    private DpDatasetLogMapper logMapper;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DpMetaTableMapper tableMapper;
    @Autowired
    private DpMetaColumnMapper columnMapper;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerProperties properties;
    @Autowired
    private DpDatasetServiceImpl self;

    @Override
    public List<TreeNode> buildTree() {
        // Load catalogs and build a map keyed by "cat_<id>" for O(1) lookup
        List<DpDatasetCatalog> catalogs = catalogMapper.selectCatalogList(new DpDatasetCatalog());
        // 保留 SQL 的 order_num 顺序，避免 HashMap 遍历导致目录刷新后随机跳位
        Map<String, TreeNode> catalogNodeMap = new LinkedHashMap<>();
        for (DpDatasetCatalog cat : catalogs) {
            TreeNode node = new TreeNode();
            node.setId("cat_" + cat.getCatalogId());
            node.setParentId(cat.getParentId() != null && cat.getParentId() != 0L
                ? "cat_" + cat.getParentId() : "0");
            node.setLabel(cat.getCatalogName());
            node.setNodeType("catalog");
            node.setCatalogId(cat.getCatalogId());
            node.setOrderNum(cat.getOrderNum());
            node.setStatus(cat.getStatus());
            node.setChildren(new ArrayList<>());
            catalogNodeMap.put(node.getId(), node);
        }

        // Build nested catalog tree: attach each catalog to its parent (if any)
        List<TreeNode> tree = new ArrayList<>();
        for (TreeNode catNode : catalogNodeMap.values()) {
            TreeNode parent = catalogNodeMap.get(catNode.getParentId());
            if (parent != null) {
                parent.getChildren().add(catNode);
            } else {
                tree.add(catNode); // root catalog (parentId = 0)
            }
        }

        // Load datasets and attach to their catalog leaf
        List<DpDataset> datasets = datasetMapper.selectDatasetList(new DpDataset());
        for (DpDataset ds : datasets) {
            TreeNode node = new TreeNode();
            node.setId("ds_" + ds.getDatasetId());
            node.setParentId("cat_" + ds.getCatalogId());
            node.setLabel(ds.getDatasetName());
            node.setNodeType("dataset");
            node.setDatasetId(ds.getDatasetId());
            node.setCatalogId(ds.getCatalogId());
            node.setStatus(ds.getStatus());
            node.setChildren(new ArrayList<>());

            TreeNode parent = catalogNodeMap.get(node.getParentId());
            if (parent != null) {
                parent.getChildren().add(node);
            }
        }

        return tree;
    }

    @Override
    public DpDataset selectDatasetById(Long datasetId) {
        DpDataset dataset = datasetMapper.selectDatasetById(datasetId);
        if (dataset != null) {
            DpDataSource ds = dataSourceMapper.selectDataSourceById(dataset.getDatasourceId());
            dataset.setDatasourceName(ds != null ? ds.getSourceName() : "");
        }
        return dataset;
    }

    /**
     * 新增数据集：校验编码唯一（uk 为 code + del_flag），并自动创建 V1 草稿（空定义）。
     */
    @Override
    @Transactional
    public int insertDataset(DpDataset dataset) {
        if (datasetMapper.selectDatasetByCode(dataset.getDatasetCode()) != null) {
            throw new ServiceException("数据集编码已存在：" + dataset.getDatasetCode());
        }
        DpDataSource ds = dataSourceMapper.selectDataSourceById(dataset.getDatasourceId());
        if (ds == null) {
            throw new ServiceException("数据源不存在");
        }

        dataset.setLatestVersionNo(1);
        dataset.setCreateBy(SecurityUtils.getUsername());
        int rows = datasetMapper.insertDataset(dataset);

        // 自动创建 V1 DRAFT（空定义）
        JSONObject def = new JSONObject();
        def.put("schemaVersion", 2);
        def.put("datasourceId", dataset.getDatasourceId());
        def.put("tableId", null);
        def.put("fields", new JSONArray());

        DpDatasetVersion v1 = new DpDatasetVersion();
        v1.setDatasetId(dataset.getDatasetId());
        v1.setVersionNo(1);
        v1.setVersionName("V1");
        v1.setDefinitionJson(def.toJSONString());
        v1.setSchemaVersion(2);
        v1.setVersionStatus("DRAFT");
        v1.setHealthStatus("INVALID");
        v1.setValidationMessage("");
        v1.setCreateBy(SecurityUtils.getUsername());
        versionMapper.insertVersion(v1);

        writeLog(dataset.getDatasetId(), v1.getVersionId(), "INSERT", "1",
                "新增数据集：" + dataset.getDatasetName(), null);
        return rows;
    }

    /**
     * 修改数据集：仅允许改名称/负责人/目录/状态/备注，编码与数据源不可改（XML 层面已限制）。
     */
    @Override
    @Transactional
    public int updateDataset(DpDataset dataset) {
        DpDataset old = datasetMapper.selectDatasetById(dataset.getDatasetId());
        if (old == null) {
            throw new ServiceException("数据集不存在");
        }
        dataset.setUpdateBy(SecurityUtils.getUsername());
        int rows = datasetMapper.updateDataset(dataset);
        writeLog(dataset.getDatasetId(), null, "UPDATE", "1",
                "修改数据集：" + (dataset.getDatasetName() != null ? dataset.getDatasetName() : old.getDatasetName()), null);
        return rows;
    }

    /**
     * 删除数据集：逻辑删除（del_flag = '2'）。
     */
    @Override
    @Transactional
    public int deleteDatasetByIds(Long[] datasetIds) {
        if (datasetIds == null || datasetIds.length == 0) {
            return 0;
        }
        // 阻断式保护：仍被标签库关联的数据集拒绝删除，防止标签库 dataset_id 悬空
        for (Long id : datasetIds) {
            DpDataset ds = datasetMapper.selectDatasetById(id);
            if (ds == null) {
                continue;
            }
            int libraryCount = datasetMapper.countLibrariesByDatasetId(id);
            if (libraryCount > 0) {
                throw new ServiceException("数据集[" + ds.getDatasetName() + "]仍被 " + libraryCount
                        + " 个标签库关联，不能删除");
            }
        }
        int rows = 0;
        for (Long id : datasetIds) {
            DpDataset ds = datasetMapper.selectDatasetById(id);
            if (ds != null) {
                rows += datasetMapper.deleteDatasetById(id);
                writeLog(id, null, "DELETE", "1", "删除数据集：" + ds.getDatasetName(), null);
            }
        }
        return rows;
    }

    /**
     * 移动/排序数据集（拖拽排序用）：跨目录则更新 catalog_id；dp_dataset 无 order_num 列，同目录重排无需落库。
     */
    @Override
    @Transactional
    public int updateDatasetOrder(DpDataset dataset) {
        DpDataset old = datasetMapper.selectDatasetById(dataset.getDatasetId());
        if (old == null) {
            throw new ServiceException("数据集不存在");
        }
        if (dataset.getCatalogId() != null && !dataset.getCatalogId().equals(old.getCatalogId())) {
            int rows = datasetMapper.moveDataset(dataset);
            writeLog(dataset.getDatasetId(), null, "UPDATE", "1",
                    "移动数据集：" + old.getDatasetName() + " 至目录 " + dataset.getCatalogId(), null);
            return rows;
        }
        return 1;
    }

    /**
     * 版本列表：不含 definition_json，附 isDefault 标记。
     */
    @Override
    public List<DpDatasetVersion> selectVersionList(Long datasetId) {
        DpDataset dataset = datasetMapper.selectDatasetById(datasetId);
        Long defaultId = dataset != null ? dataset.getDefaultVersionId() : null;
        List<DpDatasetVersion> versions = versionMapper.selectVersionListByDatasetId(datasetId);
        for (DpDatasetVersion version : versions) {
            version.setIsDefault(defaultId != null && defaultId.equals(version.getVersionId()));
        }
        return versions;
    }

    /**
     * 版本详情：definitionJson + dp_dataset_field 明细。
     */
    @Override
    public DpDatasetVersion selectVersionDetail(Long versionId) {
        DpDatasetVersion version = versionMapper.selectVersionById(versionId);
        if (version != null) {
            version.setFields(fieldMapper.selectFieldsByVersionId(versionId));
        }
        return version;
    }

    /**
     * 保存草稿：仅 DRAFT 可保存；重写 definition_json，按 version_id 删插 dp_dataset_field 与
     * dp_dataset_dependency；校验结果写 health_status/validation_message（DRAFT 允许 INVALID 保存）。
     */
    @Override
    @Transactional
    public DpDatasetVersion saveDraft(SaveDraftRequest request) {
        DpDatasetVersion version = versionMapper.selectVersionById(request.getVersionId());
        if (version == null) {
            throw new ServiceException("版本不存在");
        }
        if (!"DRAFT".equals(version.getVersionStatus())) {
            throw new ServiceException("仅草稿版本可保存定义");
        }
        DpDataset dataset = datasetMapper.selectDatasetById(version.getDatasetId());
        if (dataset == null) {
            throw new ServiceException("数据集不存在");
        }

        // 重建 definition_json（字段按 orderNum 升序）
        List<SaveDraftRequest.FieldItem> items = request.getFields() == null
            ? new ArrayList<>() : new ArrayList<>(request.getFields());
        items.sort(Comparator.comparing(SaveDraftRequest.FieldItem::getOrderNum,
            Comparator.nullsLast(Comparator.naturalOrder())));
        JSONObject def = buildDefinition(dataset.getDatasourceId(), request.getTableId(), items);

        // 校验并写健康状态（DRAFT 允许 INVALID 保存）
        List<String> problems = validateDefinition(dataset, def);
        version.setDefinitionJson(def.toJSONString());
        version.setVersionName(request.getVersionName());
        version.setHealthStatus(problems.isEmpty() ? "VALID" : "INVALID");
        version.setValidationMessage(truncate(String.join("；", problems), 2000));
        version.setUpdateBy(SecurityUtils.getUsername());
        versionMapper.updateVersion(version);

        // dp_dataset_field 按 version_id 全量重写
        fieldMapper.deleteFieldsByVersionId(version.getVersionId());
        if (!items.isEmpty()) {
            List<DpDatasetField> rows = new ArrayList<>();
            for (SaveDraftRequest.FieldItem item : items) {
                DpDatasetField row = new DpDatasetField();
                row.setVersionId(version.getVersionId());
                row.setFieldAlias(item.getAlias());
                row.setSourceTableId(request.getTableId());
                row.setSourceColumnId(item.getColumnId());
                row.setDataType(item.getDataType());
                row.setEnabled(Boolean.TRUE.equals(item.getEnabled()) ? "1" : "0");
                row.setOrderNum(item.getOrderNum());
                DpMetaColumn column = item.getColumnId() == null ? null : columnMapper.selectColumnById(item.getColumnId());
                row.setFieldName(column != null ? column.getColumnName() : "");
                rows.add(row);
            }
            fieldMapper.insertFields(rows);
        }

        // dp_dataset_dependency 按 version_id 全量重写：1 条 TABLE 依赖 + N 条 COLUMN 依赖
        dependencyMapper.deleteDependenciesByVersionId(version.getVersionId());
        if (request.getTableId() != null) {
            List<DpDatasetDependency> deps = new ArrayList<>();
            deps.add(buildDependency(dataset, version.getVersionId(), request.getTableId(), null, "TABLE"));
            for (SaveDraftRequest.FieldItem item : items) {
                deps.add(buildDependency(dataset, version.getVersionId(), request.getTableId(),
                    item.getColumnId(), "COLUMN"));
            }
            dependencyMapper.insertDependencies(deps);
        }

        writeLog(dataset.getDatasetId(), version.getVersionId(), "SAVE", "1",
                "保存草稿：V" + version.getVersionNo() + (problems.isEmpty() ? "（校验通过）" : "（校验未通过）"),
                version.getValidationMessage());
        return version;
    }

    /**
     * 复制版本：基于任意版本生成新 DRAFT（version_no = latest + 1），已有 DRAFT 时拒绝。
     */
    @Override
    @Transactional
    public DpDatasetVersion copyVersion(Long datasetId, CopyVersionRequest request) {
        DpDataset dataset = datasetMapper.selectDatasetById(datasetId);
        if (dataset == null) {
            throw new ServiceException("数据集不存在");
        }
        DpDatasetVersion source = versionMapper.selectVersionById(request.getSourceVersionId());
        if (source == null || !datasetId.equals(source.getDatasetId())) {
            throw new ServiceException("源版本不存在");
        }
        if (versionMapper.countDraftByDatasetId(datasetId) > 0) {
            throw new ServiceException("已存在草稿版本，请先发布后再复制");
        }

        int newNo = dataset.getLatestVersionNo() == null ? 1 : dataset.getLatestVersionNo() + 1;
        DpDatasetVersion draft = new DpDatasetVersion();
        draft.setDatasetId(datasetId);
        draft.setVersionNo(newNo);
        draft.setVersionName("V" + newNo);
        draft.setDefinitionJson(source.getDefinitionJson());
        draft.setSchemaVersion(source.getSchemaVersion());
        draft.setVersionStatus("DRAFT");
        draft.setHealthStatus(source.getHealthStatus());
        draft.setValidationMessage(source.getValidationMessage());
        draft.setCreateBy(SecurityUtils.getUsername());
        versionMapper.insertVersion(draft);

        // 复制字段与依赖明细
        List<DpDatasetField> fields = fieldMapper.selectFieldsByVersionId(source.getVersionId());
        if (!fields.isEmpty()) {
            for (DpDatasetField field : fields) {
                field.setFieldId(null);
                field.setVersionId(draft.getVersionId());
            }
            fieldMapper.insertFields(fields);
        }
        List<DpDatasetDependency> deps = dependencyMapper.selectDependenciesByVersionId(source.getVersionId());
        if (!deps.isEmpty()) {
            for (DpDatasetDependency dep : deps) {
                dep.setDependencyId(null);
                dep.setVersionId(draft.getVersionId());
            }
            dependencyMapper.insertDependencies(deps);
        }

        DpDataset upd = new DpDataset();
        upd.setDatasetId(datasetId);
        upd.setLatestVersionNo(newNo);
        datasetMapper.updateLatestVersionNo(upd);

        writeLog(datasetId, draft.getVersionId(), "COPY", "1",
                "复制版本：V" + source.getVersionNo() + " -> 新草稿 V" + newNo, null);
        return draft;
    }

    /**
     * 发布版本：仅 DRAFT 或 OFFLINE（已下线重新上线）可发布，且重校验必须 VALID；
     * 写 release_note/publish_by/publish_time；setDefault 时更新 dp_dataset.default_version_id。
     */
    @Override
    @Transactional
    public int publishVersion(Long versionId, PublishRequest request) {
        DpDatasetVersion version = versionMapper.selectVersionById(versionId);
        if (version == null) {
            throw new ServiceException("版本不存在");
        }
        if (!"DRAFT".equals(version.getVersionStatus()) && !"OFFLINE".equals(version.getVersionStatus())) {
            throw new ServiceException("仅草稿或已下线版本可发布");
        }
        DpDataset dataset = datasetMapper.selectDatasetById(version.getDatasetId());
        if (dataset == null) {
            throw new ServiceException("数据集不存在");
        }

        // 发布前重校验，必须 VALID（失败时健康状态与错误日志独立事务落库）
        List<String> problems = validateDefinition(dataset, JSON.parseObject(version.getDefinitionJson()));
        if (!problems.isEmpty()) {
            String message = truncate(String.join("；", problems), 2000);
            self.recordPublishInvalid(versionId, message);
            throw new ServiceException("校验未通过：" + message);
        }

        version.setVersionName(request.getVersionName());
        version.setVersionStatus("ONLINE");
        version.setHealthStatus("VALID");
        version.setValidationMessage("");
        version.setReleaseNote(request.getReleaseNote());
        version.setPublishBy(SecurityUtils.getUsername());
        version.setPublishTime(new Date());
        version.setUpdateBy(SecurityUtils.getUsername());
        int rows = versionMapper.updateVersion(version);

        if (Boolean.TRUE.equals(request.getSetDefault())) {
            datasetMapper.updateDefaultVersionId(version.getDatasetId(), versionId);
        }

        writeLog(version.getDatasetId(), versionId, "PUBLISH", "1",
                "发布版本：V" + version.getVersionNo()
                    + (Boolean.TRUE.equals(request.getSetDefault()) ? "（设为默认）" : ""), null);
        return rows;
    }

    /**
     * 下线版本：ONLINE -> OFFLINE；若为默认版本则自动提升最新 ONLINE 版本为默认，
     * 无其他在线版本时才清空 default_version_id。
     */
    @Override
    @Transactional
    public int offlineVersion(Long versionId) {
        DpDatasetVersion version = versionMapper.selectVersionById(versionId);
        if (version == null) {
            throw new ServiceException("版本不存在");
        }
        if (!"ONLINE".equals(version.getVersionStatus())) {
            throw new ServiceException("仅在线版本可下线");
        }

        DpDatasetVersion upd = new DpDatasetVersion();
        upd.setVersionId(versionId);
        upd.setVersionStatus("OFFLINE");
        upd.setUpdateBy(SecurityUtils.getUsername());
        int rows = versionMapper.updateVersion(upd);

        // 若为默认版本：优先提升剩余最新 ONLINE 版本为默认，没有再清空
        DpDataset dataset = datasetMapper.selectDatasetById(version.getDatasetId());
        if (dataset != null && versionId.equals(dataset.getDefaultVersionId())) {
            Long successorId = versionMapper.selectLatestOnlineVersionId(version.getDatasetId(), versionId);
            datasetMapper.updateDefaultVersionId(version.getDatasetId(), successorId);
            if (successorId != null) {
                DpDatasetVersion successor = versionMapper.selectVersionById(successorId);
                writeLog(version.getDatasetId(), successorId, "SET_DEFAULT", "1",
                        "下线默认版本 V" + version.getVersionNo() + "，自动提升 V"
                            + (successor != null ? successor.getVersionNo() : successorId) + " 为默认版本", null);
            }
        }

        writeLog(version.getDatasetId(), versionId, "OFFLINE", "1",
                "下线版本：V" + version.getVersionNo(), null);
        return rows;
    }

    /**
     * 设为默认版本：仅 ONLINE 版本可设为默认，更新 dp_dataset.default_version_id。
     */
    @Override
    @Transactional
    public int setDefaultVersion(Long versionId) {
        DpDatasetVersion version = versionMapper.selectVersionById(versionId);
        if (version == null) {
            throw new ServiceException("版本不存在");
        }
        if (!"ONLINE".equals(version.getVersionStatus())) {
            throw new ServiceException("仅在线版本可设为默认");
        }
        DpDataset dataset = datasetMapper.selectDatasetById(version.getDatasetId());
        if (dataset == null) {
            throw new ServiceException("数据集不存在");
        }
        if (versionId.equals(dataset.getDefaultVersionId())) {
            return 0;
        }
        int rows = datasetMapper.updateDefaultVersionId(version.getDatasetId(), versionId);
        writeLog(version.getDatasetId(), versionId, "SET_DEFAULT", "1",
                "设为默认版本：V" + version.getVersionNo(), null);
        return rows;
    }

    /**
     * 数据预览：重校验须 VALID，用 JdbcConnectionFactory 对该数据集的数据源建短连接，
     * 拼 SELECT `物理列` AS `别名`, ... FROM `宽表` LIMIT 100（只取启用字段、按 orderNum 排序）。
     */
    @Override
    public PreviewResultVO preview(PreviewRequest request) {
        DpDatasetVersion version = versionMapper.selectVersionById(request.getVersionId());
        if (version == null) {
            throw new ServiceException("版本不存在");
        }
        DpDataset dataset = datasetMapper.selectDatasetById(version.getDatasetId());
        if (dataset == null) {
            throw new ServiceException("数据集不存在");
        }

        // 预览前重校验，必须 VALID
        JSONObject def = JSON.parseObject(version.getDefinitionJson());
        List<String> problems = validateDefinition(dataset, def);
        if (!problems.isEmpty()) {
            String message = truncate(String.join("；", problems), 1000);
            writeLog(dataset.getDatasetId(), version.getVersionId(), "PREVIEW", "0",
                    "预览失败：校验未通过", message);
            throw new ServiceException("版本校验未通过：" + message);
        }

        // 启用字段按 orderNum 升序，物理列名/表名从 dp_meta_column/dp_meta_table 取
        DpMetaTable table = tableMapper.selectTableById(def.getLong("tableId"));
        DpDataSource ds = dataSourceMapper.selectDataSourceById(dataset.getDatasourceId());

        JSONArray fields = def.getJSONArray("fields");
        List<JSONObject> enabledFields = new ArrayList<>();
        for (int i = 0; i < fields.size(); i++) {
            JSONObject field = fields.getJSONObject(i);
            if (field.getBooleanValue("enabled")) {
                enabledFields.add(field);
            }
        }
        enabledFields.sort(Comparator.comparing((JSONObject f) -> f.getInteger("orderNum"),
            Comparator.nullsLast(Comparator.naturalOrder())));

        StringBuilder sql = new StringBuilder("select ");
        List<PreviewResultVO.PreviewColumn> columns = new ArrayList<>();
        List<String> aliases = new ArrayList<>();
        for (int i = 0; i < enabledFields.size(); i++) {
            JSONObject field = enabledFields.get(i);
            DpMetaColumn column = columnMapper.selectColumnById(field.getLong("columnId"));
            String alias = field.getString("alias");
            if (i > 0) {
                sql.append(", ");
            }
            sql.append('`').append(escapeIdentifier(column.getColumnName()))
               .append("` as `").append(escapeIdentifier(alias)).append('`');
            columns.add(new PreviewResultVO.PreviewColumn(alias, field.getString("dataType")));
            aliases.add(alias);
        }
        sql.append(" from `").append(escapeIdentifier(table.getObjectName())).append("` limit 100");

        String password = "";
        if (StringUtils.isNotEmpty(ds.getPasswordCipher())) {
            password = cryptoService.decrypt(ds.getPasswordCipher());
        }

        PreviewResultVO result = new PreviewResultVO();
        result.setColumns(columns);
        List<Map<String, Object>> rows = new ArrayList<>();
        try (Connection conn = connectionFactory.createConnection(
                ds.getHost(), ds.getPort(), ds.getDatabaseName(), ds.getUsername(), password);
             Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            try (ResultSet rs = stmt.executeQuery(sql.toString())) {
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (String alias : aliases) {
                        row.put(alias, rs.getObject(alias));
                    }
                    rows.add(row);
                }
            }
        } catch (Exception e) {
            writeLog(dataset.getDatasetId(), version.getVersionId(), "PREVIEW", "0",
                    truncate("预览失败：" + e.getMessage(), 1000), null);
            throw new RuntimeException("预览失败：" + e.getMessage(), e);
        }
        result.setRows(rows);

        writeLog(dataset.getDatasetId(), version.getVersionId(), "PREVIEW", "1",
                "数据预览：V" + version.getVersionNo() + "，返回 " + rows.size() + " 行", null);
        return result;
    }

    @Override
    public List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query) {
        query.setDatasourceId(datasourceId);
        return tableMapper.selectTableList(query);
    }

    @Override
    public List<DpMetaColumn> listColumns(Long tableId) {
        return columnMapper.selectColumnsByTableId(tableId);
    }

    @Override
    public List<DpDatasetLog> listLogs(Long datasetId, DpDatasetLog query) {
        query.setDatasetId(datasetId);
        return logMapper.selectLogList(query);
    }

    // ---- private helpers ----

    /**
     * 构建 definition_json（schemaVersion=2，单宽表）。
     */
    private JSONObject buildDefinition(Long datasourceId, Long tableId, List<SaveDraftRequest.FieldItem> items) {
        JSONObject def = new JSONObject();
        def.put("schemaVersion", 2);
        def.put("datasourceId", datasourceId);
        def.put("tableId", tableId);
        JSONArray fields = new JSONArray();
        for (SaveDraftRequest.FieldItem item : items) {
            JSONObject field = new JSONObject();
            field.put("columnId", item.getColumnId());
            field.put("alias", item.getAlias());
            field.put("dataType", item.getDataType());
            field.put("enabled", Boolean.TRUE.equals(item.getEnabled()));
            field.put("orderNum", item.getOrderNum());
            fields.add(field);
        }
        def.put("fields", fields);
        return def;
    }

    /**
     * 校验规则：数据源存在且正常；tableId 在 dp_meta_table 中属于该数据源且 status=0；
     * 启用字段的 columnId 在该表 dp_meta_column 中存在；alias 非空且版本内唯一；至少 1 个启用字段。
     */
    private List<String> validateDefinition(DpDataset dataset, JSONObject def) {
        List<String> problems = new ArrayList<>();

        DpDataSource ds = dataSourceMapper.selectDataSourceById(dataset.getDatasourceId());
        if (ds == null) {
            problems.add("数据源不存在");
        } else if (!"0".equals(ds.getStatus())) {
            problems.add("数据源[" + ds.getSourceName() + "]已停用");
        }

        Long tableId = def.getLong("tableId");
        DpMetaTable table = null;
        if (tableId == null) {
            problems.add("未选择宽表");
        } else {
            table = tableMapper.selectTableById(tableId);
            if (table == null || !dataset.getDatasourceId().equals(table.getDatasourceId())) {
                problems.add("宽表不存在或不属于该数据源");
                table = null;
            } else if (!"0".equals(table.getStatus())) {
                problems.add("宽表[" + table.getObjectName() + "]已失效，请重新同步元数据");
            }
        }

        JSONArray fields = def.getJSONArray("fields");
        Set<String> aliases = new HashSet<>();
        int enabledCount = 0;
        if (fields != null) {
            for (int i = 0; i < fields.size(); i++) {
                JSONObject field = fields.getJSONObject(i);
                String alias = field.getString("alias");
                if (alias == null || alias.trim().isEmpty()) {
                    problems.add("第" + (i + 1) + "个字段别名不能为空");
                } else if (!aliases.add(alias)) {
                    problems.add("字段别名[" + alias + "]重复");
                }
                if (field.getBooleanValue("enabled")) {
                    enabledCount++;
                    Long columnId = field.getLong("columnId");
                    if (columnId == null) {
                        problems.add("启用字段[" + alias + "]缺少来源字段");
                    } else if (table != null) {
                        DpMetaColumn column = columnMapper.selectColumnById(columnId);
                        if (column == null || !table.getTableId().equals(column.getTableId())) {
                            problems.add("启用字段[" + alias + "]在宽表元数据中不存在");
                        }
                    }
                }
            }
        }
        if (enabledCount == 0) {
            problems.add("至少需要1个启用字段");
        }
        return problems;
    }

    private DpDatasetDependency buildDependency(DpDataset dataset, Long versionId, Long tableId,
                                                Long columnId, String dependencyType) {
        DpDatasetDependency dep = new DpDatasetDependency();
        dep.setDatasetId(dataset.getDatasetId());
        dep.setVersionId(versionId);
        dep.setDatasourceId(dataset.getDatasourceId());
        dep.setTableId(tableId);
        dep.setColumnId(columnId);
        dep.setDependencyType(dependencyType);
        return dep;
    }

    /** 标识符反引号转义（` -> ``） */
    private String escapeIdentifier(String name) {
        return name.replace("`", "``");
    }

    private String truncate(String text, int maxLength) {
        if (text == null || text.length() <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength);
    }

    private void writeLog(Long datasetId, Long versionId, String operType, String result,
                          String message, String detailJson) {
        DpDatasetLog log = new DpDatasetLog();
        log.setDatasetId(datasetId);
        log.setVersionId(versionId);
        log.setOperType(operType);
        log.setOperatorName(SecurityUtils.getUsername());
        log.setResult(result);
        log.setMessage(message);
        log.setDetailJson(detailJson);
        logMapper.insertLog(log);
    }

    /**
     * 发布校验未通过：独立事务回写健康状态并记录失败日志（避免随主事务回滚丢失）。
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordPublishInvalid(Long versionId, String message) {
        DpDatasetVersion version = versionMapper.selectVersionById(versionId);
        if (version != null) {
            DpDatasetVersion upd = new DpDatasetVersion();
            upd.setVersionId(versionId);
            upd.setHealthStatus("INVALID");
            upd.setValidationMessage(message);
            upd.setUpdateBy(SecurityUtils.getUsername());
            versionMapper.updateVersion(upd);
            writeLog(version.getDatasetId(), versionId, "PUBLISH", "0",
                    "发布失败：校验未通过", message);
        }
    }
}
