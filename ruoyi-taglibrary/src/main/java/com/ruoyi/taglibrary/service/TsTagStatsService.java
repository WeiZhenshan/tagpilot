package com.ruoyi.taglibrary.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.*;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;
import com.ruoyi.objectgroup.service.impl.RuleTagValidator;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/**
 * 标签 chip 取数：按所选标签从当前已核验客群取聚合统计与脱敏明细，供 Skill 分析上下文使用。
 * 浏览器与 Python 都不能提供 SQL、物理列或单位；列名一律由已发布元数据解析并过白名单。
 * 单个标签失败只降级该条，不中断其余取数与技能运行。
 */
@Service
public class TsTagStatsService {
    private static final Logger log = LoggerFactory.getLogger(TsTagStatsService.class);

    /** 平台隐私抑制阈值：低于该人数的客群不下发统计与明细。 */
    static final int SUPPRESS_BELOW = 20;
    /** 分类取值上限，超出要求治理合并，不造「其他」桶。 */
    static final int CATEGORY_LIMIT = 24;
    /** 明细行上限，与对象群样例预览保持一致。 */
    static final int SAMPLE_LIMIT = 100;
    private static final int STATEMENT_SECONDS = 15;

    @Autowired private TlObjectGroupExtMapper ext;
    @Autowired private TlTagMapper tags;
    @Autowired private TsTagSemanticMapper semantics;
    @Autowired private DpOnlineVersionResolver versions;
    @Autowired private IRuleSqlBuilder rules;
    @Autowired private RuleTagValidator ruleValidator;
    @Autowired private IDimensionCodeOptionService codeOptions;
    @Autowired private JdbcConnectionFactory connections;
    @Autowired private DataBrokerCryptoService crypto;
    @Autowired private ObjectMapper json;
    @Value("${tagpilot.agent.tag-stats-seconds:20}") private long budgetSeconds = 20;

    private final ThreadLocal<Long> deadline = new ThreadLocal<>();

    /**
     * @param verifiedCount 服务端已核验的客群人数；取数前后都比对，漂移则不产出任何统计
     * @return tag_stats（每标签一条）/ sample_rows（脱敏明细，可能为 null）/ stats_note（降级说明，正常为空串）
     */
    public Map<String,Object> collect(Long libraryId, RulePayload cohortRule, Long verifiedCount,
            List<Long> tagIds, Set<Long> eligible, Set<Long> planTagIds) {
        List<Map<String,Object>> stats = new ArrayList<>();
        if (tagIds == null || tagIds.isEmpty())
            return map("tag_stats", stats, "sample_rows", null, "stats_note", "");
        if (verifiedCount == null)
            return map("tag_stats", stats, "sample_rows", null, "stats_note", "客群尚未统计人数，本轮不提供标签统计与明细");
        if (verifiedCount < SUPPRESS_BELOW)
            return map("tag_stats", stats, "sample_rows", null, "stats_note",
                "客群人数不足 " + SUPPRESS_BELOW + " 人，本轮不提供标签统计与明细");

        Long dataset = ext.selectDatasetIdByLibrary(libraryId);
        DpResolvedVersion resolved = dataset == null ? null : versions.resolve(dataset);
        if (resolved == null)
            return map("tag_stats", stats, "sample_rows", null, "stats_note", "标签库数据集没有在线版本，本轮无标签统计");
        Long version = resolved.getVersionId();
        DpDataSource source = ext.selectDataSourceByDataset(dataset);
        if (source == null)
            return map("tag_stats", stats, "sample_rows", null, "stats_note", "数据源不可用，本轮无标签统计");

        // 字段与码值在打开连接前先由权威校验器拦一道，撤权或来源漂移不会进入取数。
        ruleValidator.validateRule(libraryId, version, cohortRule);
        ruleValidator.validateCodeValues(libraryId, cohortRule);
        String key = quote(rules.resolveObjectKeyColumn(version, cohortRule));
        String table = quote(tableName(version));
        String cohort = rules.buildSql(version, cohortRule, IRuleSqlBuilder.MODE_IDS);

        deadline.set(System.nanoTime() + Math.max(1, budgetSeconds) * 1_000_000_000L);
        try (Connection connection = open(source)) {
            connection.setReadOnly(true);
            connection.setAutoCommit(false);
            try {
                if (cohortCount(connection, cohort) != verifiedCount) {
                    for (Long tagId : tagIds) stats.add(unavailable(tagId, "客群人数在运行期间发生变化，请重新统计后再分析"));
                    return map("tag_stats", stats, "sample_rows", null, "stats_note", "客群人数已变化，本轮无标签统计");
                }
                Map<Long,Translate> translate = new LinkedHashMap<>();
                List<TlTag> usable = new ArrayList<>();
                for (Long tagId : tagIds) {
                    Map<String,Object> entry = new LinkedHashMap<>();
                    entry.put("tag_id", tagId);
                    TlTag tag = null;
                    try {
                        tag = verifiedTag(tagId, libraryId, version, eligible);
                        Governed governed = governed(tag.getTagId());
                        entry.putAll(describe(tag, governed, planTagIds != null && planTagIds.contains(tagId)));
                        entry.put("sample_size", verifiedCount);
                        String column = column(version, tag);
                        if (isNumeric(tag)) stats.add(numeric(connection, entry, table, key, cohort, column, governed.factor));
                        else if (isCategory(tag)) stats.add(category(connection, entry, table, key, cohort, column, libraryId, tag, translate));
                        else stats.add(entryWith(entry, "UNSUPPORTED", "该标签类型不支持统计"));
                        usable.add(tag);
                    } catch (Exception e) {
                        if (tag == null) entry.putAll(map("label", "", "tag_type", "", "unit", null, "unit_source", "none", "plan_tag", false));
                        log.warn("标签统计失败 tag_id={}: {}", tagId, e.getMessage());
                        stats.add(entryWith(entry, "MISSING", "该标签取数失败，请稍后重试或检查字段状态"));
                    }
                }
                return map("tag_stats", stats, "sample_rows",
                    sample(connection, table, key, cohort, usable, libraryId, version, translate), "stats_note", "");
            } finally {
                connection.rollback();
            }
        } catch (Exception e) {
            log.warn("标签统计整体降级: {}", e.getMessage());
            return map("tag_stats", new ArrayList<>(), "sample_rows", null, "stats_note", "标签统计取数失败，本轮不提供标签统计");
        } finally {
            deadline.remove();
        }
    }

    // ---- 单个标签 ----

    private Map<String,Object> numeric(Connection connection, Map<String,Object> entry, String table, String key,
            String cohort, String column, double factor) throws SQLException {
        try (Statement st = connection.createStatement()) {
            st.setQueryTimeout(timeout());
            try (ResultSet rs = st.executeQuery("select count(*) n, count(" + column + ") nn, min(" + column + ") mn, max(" + column + ") mx, sum(" + column + ") sm, avg(" + column + ") av from "
                    + table + " where " + key + " in (" + cohort + ")")) {
                if (!rs.next()) return entryWith(entry, "MISSING", "聚合没有返回结果");
                Map<String,Object> values = new LinkedHashMap<>();
                values.put("n", rs.getLong("nn"));
                values.put("missing", rs.getLong("n") - rs.getLong("nn"));
                put(values, "min", scaled(rs.getObject("mn"), factor));
                put(values, "max", scaled(rs.getObject("mx"), factor));
                put(values, "sum", scaled(rs.getObject("sm"), factor));
                put(values, "avg", scaled(rs.getObject("av"), factor));
                Double median = median(connection, table, key, cohort, column);
                if (median != null) values.put("median", scaled(median, factor));
                entry.put("numeric", values);
                entry.put("categories", new ArrayList<>());
                entry.put("truncated", false);
                return entryWith(entry, "AVAILABLE", "");
            }
        }
    }

    /** 中位数走窗口函数；个别方言不支持时降级为不产出，不影响均值等统计。 */
    private Double median(Connection connection, String table, String key, String cohort, String column) {
        String sql = "select avg(v) m from (select " + column + " v, row_number() over (order by " + column + ") rn, count(*) over () c from "
            + table + " where " + key + " in (" + cohort + ") and " + column + " is not null) x where rn in (floor((c+1)/2), floor((c+2)/2))";
        try (Statement st = connection.createStatement()) {
            st.setQueryTimeout(timeout());
            try (ResultSet rs = st.executeQuery(sql)) {
                if (!rs.next()) return null;
                Object value = rs.getObject(1);
                return value instanceof Number ? ((Number) value).doubleValue() : null;
            }
        } catch (Exception e) {
            log.debug("中位数不可用，已降级: {}", e.getMessage());
            return null;
        }
    }

    private Map<String,Object> category(Connection connection, Map<String,Object> entry, String table, String key,
            String cohort, String column, Long libraryId, TlTag tag, Map<Long,Translate> translate) throws SQLException {
        Translate map = translate.computeIfAbsent(tag.getTagId(), id -> lookupCodeOptions(libraryId, tag.getFieldName()));
        List<Map<String,Object>> categories = new ArrayList<>();
        long total = 0;
        boolean overflow = false;
        try (Statement st = connection.createStatement()) {
            st.setQueryTimeout(timeout());
            st.setMaxRows(CATEGORY_LIMIT + 1);
            try (ResultSet rs = st.executeQuery("select " + column + " d0, count(*) n from " + table + " where " + key + " in (" + cohort + ") group by " + column + " order by n desc")) {
                while (rs.next()) {
                    if (categories.size() >= CATEGORY_LIMIT) { overflow = true; break; }
                    Object raw = rs.getObject("d0");
                    long count = rs.getLong("n");
                    total += count;
                    String code = raw == null ? "" : String.valueOf(raw);
                    categories.add(map("code", code, "label", map.label(code), "count", count));
                }
            }
        }
        if (overflow || categories.size() > CATEGORY_LIMIT) return entryWith(entry, "MISSING", "分类取值过多，需要先治理合并后再分析");
        boolean small = false;
        for (Map<String,Object> row : categories) {
            long count = ((Number) row.get("count")).longValue();
            if (count < SUPPRESS_BELOW || total - count < SUPPRESS_BELOW) small = true;
        }
        if (small) return entryWith(entry, "SUPPRESSED", "存在小于 " + SUPPRESS_BELOW + " 人的分类，整组已抑制");
        for (Map<String,Object> row : categories) {
            long count = ((Number) row.get("count")).longValue();
            row.put("share", total <= 0 ? 0d : Math.round(count * 1000d / total) / 10d);
        }
        entry.put("numeric", null);
        entry.put("categories", categories);
        entry.put("truncated", false);
        return entryWith(entry, "AVAILABLE", "");
    }

    private Map<String,Object> sample(Connection connection, String table, String key, String cohort, List<TlTag> selected,
            Long libraryId, Long version, Map<Long,Translate> translate) throws SQLException {
        List<String> labels = new ArrayList<>(), columns = new ArrayList<>();
        List<TlTag> usable = new ArrayList<>();
        for (TlTag tag : selected) {
            if (!isSupported(tag)) continue;
            usable.add(tag); labels.add(tag.getTagName()); columns.add(column(version, tag));
        }
        if (usable.isEmpty()) return null;
        List<List<Object>> rows = new ArrayList<>();
        try (Statement st = connection.createStatement()) {
            st.setQueryTimeout(timeout());
            st.setMaxRows(SAMPLE_LIMIT);
            try (ResultSet rs = st.executeQuery("select " + key + ", " + String.join(", ", columns) + " from " + table + " where " + key + " in (" + cohort + ") limit " + SAMPLE_LIMIT)) {
                while (rs.next()) {
                    List<Object> row = new ArrayList<>();
                    row.add(mask(String.valueOf(rs.getObject(1))));
                    for (int i = 0; i < usable.size(); i++) {
                        Object raw = rs.getObject(i + 2);
                        TlTag tag = usable.get(i);
                        if (raw != null && isCategory(tag)) {
                            Translate codeLabels = translate.computeIfAbsent(tag.getTagId(), id -> lookupCodeOptions(libraryId, tag.getFieldName()));
                            row.add(codeLabels.label(String.valueOf(raw)));
                        } else row.add(raw);
                    }
                    rows.add(row);
                }
            }
        }
        return map("columns", labels, "rows", rows, "limit", SAMPLE_LIMIT, "masked", true,
            "note", "客户号已脱敏；仅含所选标签列，最多 " + SAMPLE_LIMIT + " 行");
    }

    // ---- 元数据与校验 ----

    private TlTag verifiedTag(Long tagId, Long libraryId, Long version, Set<Long> eligible) {
        TlTag tag = tags.selectTagById(tagId);
        if (tag == null || !Objects.equals(tag.getLibraryId(), libraryId) || !"2".equals(tag.getStatus())
                || !"AVAILABLE".equals(tag.getSourceStatus()) || !Objects.equals(tag.getSourceVersionId(), version))
            throw new IllegalStateException("标签来源或发布版本已变化");
        if (eligible != null && !eligible.contains(tagId)) throw new IllegalStateException("标签已不可用");
        return tag;
    }

    private Map<String,Object> describe(TlTag tag, Governed governed, boolean planTag) {
        return map("label", tag.getTagName(), "tag_type", tag.getTagType(), "unit", governed.unit,
            "unit_source", governed.unit == null ? "none" : "ts_tag_semantic", "plan_tag", planTag);
    }

    /** 单位来自已复核的标签语义层；平台事实只接受 人/元/%/pp/分，其余量纲一律返回 null，该标签数值统计不得成为事实。 */
    private Governed governed(Long tagId) {
        TsTagSemantic semantic = semantics.selectByTagId(tagId);
        String unit = semantic == null ? null : semantic.getUnit();
        BigDecimal scale = semantic == null || semantic.getUnitScale() == null ? BigDecimal.ONE : semantic.getUnitScale();
        if (unit == null) return new Governed(null, 1d);
        double factor = scale.doubleValue();
        switch (unit) {
            // 比率量纲的物理值是 0~1 的小数，换成平台 % 还要再乘 100；其余量纲按语义层登记的换算系数折算。
            case "RATIO":
            case "SHARE": return new Governed("%", factor * 100d);
            case "CNY": return new Governed("元", factor);
            case "COUNT":
            case "PERSON": return new Governed("人", factor);
            case "POINT": return new Governed("分", factor);
            default: return new Governed(null, 1d);
        }
    }

    /** 按换算系数折算并保留两位小数；两个原始统计量 n/missing 是人数，不参与折算。 */
    private static Double scaled(Object value, double factor) {
        if (!(value instanceof Number)) return null;
        return BigDecimal.valueOf(((Number) value).doubleValue() * factor).setScale(2, RoundingMode.HALF_UP).doubleValue();
    }

    private static final class Governed {
        private final String unit;
        private final double factor;
        private Governed(String unit, double factor) { this.unit = unit; this.factor = factor; }
    }

    private Translate lookupCodeOptions(Long libraryId, String fieldName) {
        try {
            Map<String,String> map = new LinkedHashMap<>();
            for (Map<String,Object> option : codeOptions.listCodeOptions(libraryId, fieldName)) {
                Object code = option.get("code"), definition = option.get("codeDefinition");
                if (code != null && definition != null && !String.valueOf(definition).isEmpty())
                    map.putIfAbsent(String.valueOf(code), String.valueOf(definition));
            }
            return new Translate(map);
        } catch (Exception e) {
            log.warn("码值翻译不可用 field={}: {}", fieldName, e.getMessage());
            return new Translate(Collections.emptyMap());
        }
    }

    private static final class Translate {
        private final Map<String,String> labels;
        Translate(Map<String,String> labels) { this.labels = labels; }
        String label(String code) { return code == null || code.isEmpty() ? code : labels.getOrDefault(code, code); }
    }

    private boolean isSupported(TlTag tag) { return isNumeric(tag) || isCategory(tag); }
    private boolean isNumeric(TlTag tag) { return "数值型".equals(tag.getTagType()); }
    private boolean isCategory(TlTag tag) { return "选项型".equals(tag.getTagType()) || "布尔型".equals(tag.getTagType()); }

    private String column(Long version, TlTag tag) {
        if ("1".equals(tag.getIsObjectKey())) throw new IllegalStateException("客户号列不参与分析取数");
        return quote(ext.selectColumnNameByAlias(version, tag.getFieldName()));
    }

    private String tableName(Long version) {
        String definition = ext.selectVersionDefinitionJson(version);
        if (definition == null || definition.isEmpty()) throw new IllegalStateException("数据集定义缺失");
        String name;
        try { name = ext.selectTableObjectName(json.readTree(definition).path("tableId").asLong()); }
        catch (IllegalStateException e) { throw e; }
        catch (Exception e) { throw new IllegalStateException("数据集定义格式错误"); }
        if (name == null) throw new IllegalStateException("无法定位规则执行宽表");
        return name;
    }

    private Connection open(DpDataSource source) throws Exception {
        return connections.createConnection(source, source.getPasswordCipher() == null ? "" : crypto.decrypt(source.getPasswordCipher()));
    }

    private long cohortCount(Connection connection, String cohort) throws SQLException {
        try (Statement st = connection.createStatement()) {
            st.setQueryTimeout(timeout());
            try (ResultSet rs = st.executeQuery("select count(*) n from (" + cohort + ") _cohort")) {
                return rs.next() ? rs.getLong("n") : -1L;
            }
        }
    }

    private int timeout() {
        Long until = deadline.get();
        if (until == null) return STATEMENT_SECONDS;
        long remaining = (until - System.nanoTime()) / 1_000_000_000L;
        if (remaining < 1) throw new IllegalStateException("标签取数预算耗尽");
        return (int) Math.min(STATEMENT_SECONDS, remaining);
    }

    /** 标识符白名单：物理列名只能来自元数据，且必须是普通标识符。 */
    private static String quote(String name) {
        if (name == null || !name.matches("[A-Za-z_][A-Za-z0-9_]{0,127}")) throw new IllegalStateException("标签物理列名非法");
        return "`" + name + "`";
    }

    private static String mask(String key) {
        if (key == null || key.isEmpty()) return key;
        StringBuilder masked = new StringBuilder();
        if (key.length() < 6) {
            for (int i = 0; i < key.length(); i++) masked.append('*');
            return masked.toString();
        }
        for (int i = 0; i < key.length() - 5; i++) masked.append('*');
        return key.charAt(0) + masked.toString() + key.substring(key.length() - 4);
    }

    private static void put(Map<String,Object> target, String name, Object value) {
        target.put(name, value instanceof Number ? value : null);
    }

    private static Map<String,Object> entryWith(Map<String,Object> entry, String status, String reason) {
        entry.put("status", status);
        entry.put("reason", reason);
        return entry;
    }

    private static Map<String,Object> unavailable(Long tagId, String reason) {
        return entryWith(new LinkedHashMap<>(map("tag_id", tagId, "label", "", "tag_type", "", "unit", null,
            "unit_source", "none", "plan_tag", false, "numeric", null, "categories", new ArrayList<>(), "truncated", false,
            "sample_size", null)), "MISSING", reason);
    }
}
