package com.ruoyi.taglibrary.service;

import java.sql.*;
import java.math.BigDecimal;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.databroker.domain.*;
import com.ruoyi.databroker.domain.vo.*;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;

/** 手动批处理入口；外部库只执行受控聚合，低频桶及敏感类型不输出。 */
@Service("tsProfileService")
public class TsProfileService {
    private static final int MIN_SAMPLE = 20;
    @Autowired private TsTagSemanticMapper semanticMapper;
    @Autowired private TlTagMapper tags;
    @Autowired private TlTagLibraryMapper libraries;
    @Autowired private TsTagProfileMapper profiles;
    @Autowired private TsCodeValueSemanticMapper codes;
    @Autowired private DpOnlineVersionResolver resolver;
    @Autowired private DpDataSourceMapper datasources;
    @Autowired private JdbcConnectionFactory connections;
    @Autowired private DataBrokerCryptoService crypto;

    public TsTagProfile latest(Long tagId) {
        validate(semanticMapper.selectByTagId(tagId));
        return profiles.selectLatest(tagId);
    }
    private void validate(TsTagSemantic semantic) {
        if (semantic == null || !"REVIEWED".equals(semantic.getReviewStatus()) || !"LOW".equals(semantic.getSensitivity())
                || Arrays.asList("TEXT_FREE", "ID_KEY", "UNKNOWN").contains(semantic.getSemanticType())) throw new ServiceException("仅允许已复核且 LOW 敏感级别的业务标签画像");
    }
    public TsTagProfile aggregate(Long tagId) {
        TsTagSemantic semantic = semanticMapper.selectByTagId(tagId); validate(semantic);
        TlTag tag = tags.selectTagById(tagId);
        if (tag == null || !"2".equals(tag.getStatus()) || !"AVAILABLE".equals(tag.getSourceStatus()) || "1".equals(tag.getIsObjectKey())) throw new ServiceException("标签来源不可用");
        TlTagLibrary library = libraries.selectLibraryById(tag.getLibraryId());
        DpResolvedVersion version = resolver.resolve(library.getDatasetId());
        if (version == null) throw new ServiceException("缺少在线版本");
        DpResolvedField field = resolver.listEnabledFields(version.getVersionId()).stream().filter(f -> tag.getFieldName().equals(f.getFieldAlias())).findFirst().orElseThrow(() -> new ServiceException("字段未启用"));
        String table = identifier(field.getTableName()), column = identifier(field.getFieldName());
        DpDataSource ds = datasources.selectDataSourceById(field.getDatasourceId());
        TsTagProfile profile = new TsTagProfile(); profile.setTagId(tagId); profile.setProfileDate(new java.util.Date()); profile.setSourceVersionId(version.getVersionId());
        profile.setSourceFingerprint(tag.getSourceFingerprint()); profile.setSampled(0); profile.setCreateBy(SecurityUtils.getUsername());
        String password = ds.getPasswordCipher() == null || ds.getPasswordCipher().isEmpty() ? "" : crypto.decrypt(ds.getPasswordCipher());
        try (Connection conn = connections.createConnection(ds, password)) {
            conn.setReadOnly(true); conn.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ); conn.setAutoCommit(false);
            long total, nonnull;
            try (Statement st = conn.createStatement()) {
                st.setQueryTimeout(60);
                try (ResultSet rs = st.executeQuery("select count(*) total, count(" + column + ") present, count(distinct " + column + ") distinct_count from " + table)) {
                    rs.next(); total = rs.getLong("total"); nonnull = rs.getLong("present");
                    if (nonnull < MIN_SAMPLE) throw new ServiceException("有效样本不足 20，已抑制画像");
                    profile.setRowCount(total); profile.setSampleSize(total); profile.setDistinctCount(rs.getInt("distinct_count"));
                    profile.setNullRate(BigDecimal.valueOf((double)(total - nonnull) / total).setScale(4, java.math.RoundingMode.HALF_UP));
                }
            }
            if ("BOOL".equals(semantic.getSemanticType()) || semantic.getSemanticType().startsWith("ENUM_")) {
                List<TsCodeValueSemantic> reviewed = codes.selectByTagId(tagId); List<String> allowed = new ArrayList<>();
                for (TsCodeValueSemantic code : reviewed) if ("REVIEWED".equals(code.getReviewStatus())) allowed.add(code.getCode());
                List<Map<String, Object>> frequencies = new ArrayList<>();
                if (!allowed.isEmpty()) {
                    String placeholders = String.join(",", Collections.nCopies(allowed.size(), "?"));
                    try (PreparedStatement st = conn.prepareStatement("select " + column + " code, count(*) n from " + table + " where " + column + " in (" + placeholders + ") group by " + column + " having count(*) >= 20 order by n desc limit 20")) {
                        st.setQueryTimeout(60); for (int i = 0; i < allowed.size(); i++) st.setString(i + 1, allowed.get(i));
                        try (ResultSet rs = st.executeQuery()) { while (rs.next()) if (allowed.contains(rs.getString("code"))) frequencies.add(TsSnapshotAssembler.map("code", rs.getString("code"), "count", rs.getLong("n"))); }
                    }
                }
                profile.setTopValues(TsSnapshotAssembler.json(frequencies));
            } else if (semantic.getSemanticType().startsWith("NUM_")) {
                profile.setP50(quantile(conn, table, column, nonnull, .5)); profile.setP90(quantile(conn, table, column, nonnull, .9)); profile.setP99(quantile(conn, table, column, nonnull, .99));
                profile.setMinVal(quantile(conn, table, column, nonnull, 0)); profile.setMaxVal(quantile(conn, table, column, nonnull, 1));
            }
            conn.commit();
        } catch (ServiceException e) { throw e; } catch (Exception e) { throw new ServiceException("画像聚合失败，未写入画像"); }
        profiles.upsert(profile); return profile;
    }
    private BigDecimal quantile(Connection conn, String table, String column, long n, double q) throws SQLException {
        long offset = Math.round((n - 1) * q);
        try (Statement st = conn.createStatement()) {
            st.setQueryTimeout(60);
            try (ResultSet rs = st.executeQuery("select " + column + " from " + table + " where " + column + " is not null order by " + column + " limit 1 offset " + offset)) { return rs.next() ? rs.getBigDecimal(1) : null; }
        }
    }
    private String identifier(String value) {
        if (value == null || !value.matches("[A-Za-z0-9_]+")) throw new ServiceException("物理标识符非法"); return "`" + value + "`";
    }
}
