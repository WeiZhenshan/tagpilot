package com.ruoyi.taglibrary.service;

import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.domain.dto.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/** 同一冻结批次完成依据校验、门禁和导出；权限只在请求时计算。 */
@Component
public class TsSnapshotAssembler {
    private static final ObjectMapper JSON = new ObjectMapper().setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).enable(com.fasterxml.jackson.databind.DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
    @Autowired private ITsBootstrapService bootstrap;
    @Autowired private ITsSemanticService semantics;
    @Autowired private com.ruoyi.taglibrary.mapper.TsTagProfileMapper profiles;

    public static class Result {
        public final List<Map<String, Object>> rows = new ArrayList<>();
        public final Map<String, Object> report = new LinkedHashMap<>();
        public Map<String, Object> sourceManifest;
        public final Set<Long> tagIds = new TreeSet<>();
        public int concepts, codes, aliases;
    }

    @SuppressWarnings("unchecked")
    public Result assemble(Long libraryId, String coverageNote) {
        BootstrapExportRequest request = new BootstrapExportRequest();
        request.setLibraryId(libraryId);
        BootstrapExportResult freeze = bootstrap.exportFreeze(request);
        if (!freeze.getIssues().isEmpty()) throw new ServiceException("来源冻结存在异常，拒绝发布：" + json(freeze.getIssues()));
        Result result = new Result();
        Map<Long, Map<String, Object>> authority = new LinkedHashMap<>();
        Map<Long, List<Map<String, Object>>> codesByTag = new HashMap<>();
        List<Map<String, Object>> domains = new ArrayList<>();
        try {
            for (String line : freeze.getJsonl().split("\\n")) {
                Map<String, Object> row = JSON.readValue(line, Map.class);
                if ("meta".equals(row.get("kind"))) result.sourceManifest = (Map<String, Object>) row.get("source_manifest");
                if ("domain".equals(row.get("kind"))) domains.add(row);
                if ("tag".equals(row.get("kind"))) authority.put(id(row.get("tag_id")), row);
                if ("code_value".equals(row.get("kind"))) codesByTag.computeIfAbsent(id(row.get("tag_id")), k -> new ArrayList<>()).add(row);
            }
        } catch (Exception e) { throw new ServiceException("冻结内容无法解析"); }
        result.sourceManifest.put("freeze_sha256", freeze.getContentHash());
        Map<Long, TsConcept> conceptMap = new HashMap<>();
        TsConcept query = new TsConcept(); query.setLibraryId(libraryId);
        for (TsConcept c : semantics.selectConceptList(query)) conceptMap.put(c.getConceptId(), c);
        Map<Long, TsTagSemantic> selected = new LinkedHashMap<>();
        Map<Long, List<TsCodeValueSemantic>> semanticCodes = new HashMap<>();
        List<Map<String, Object>> excluded = new ArrayList<>();
        int denominator = 0, scoreSum = 0;
        for (Map<String, Object> a : authority.values()) if (!"1".equals(a.get("is_object_key"))) denominator++;
        for (TsTagSemantic tag : semantics.selectTagSemanticByLibraryId(libraryId)) {
            Map<String, Object> a = authority.get(tag.getTagId());
            String reason = null;
            if (a == null || "1".equals(a.get("is_object_key")) || "ID_KEY".equals(tag.getSemanticType())) continue;
            List<TsCodeValueSemantic> cv = semantics.selectCodeValuesByTagId(tag.getTagId());
            List<Map<String, Object>> sourceCodes = codesByTag.getOrDefault(tag.getTagId(), Collections.emptyList());
            TsConcept concept = conceptMap.get(tag.getConceptId());
            List<TsAlias> tagAliases = semantics.selectAliasList("TAG", String.valueOf(tag.getTagId()));
            if (!"REVIEWED".equals(tag.getReviewStatus())) reason = "NOT_REVIEWED";
            else if (!"2".equals(a.get("status")) || !"AVAILABLE".equals(a.get("source_status"))) reason = "SOURCE_UNAVAILABLE";
            else if (!conceptReady(concept, conceptMap, new HashSet<>())) reason = "CONCEPT_NOT_READY";
            else if (!domains.isEmpty() && domains.stream().noneMatch(d -> Objects.equals(concept.getDomainDirId(), id(d.get("dir_id"))))) reason = "DOMAIN_NOT_READY";
            else if (!Objects.equals(tag.getBasisHash(), basisHash(a, sourceCodes))) reason = "BASIS_DRIFT";
            else if (tag.getFamilyKey() == null || tag.getFamilyKey().split("\\|", -1).length != 6) reason = "INVALID_FAMILY";
            else if (!coreReady(tag)) reason = "CORE_SEMANTICS_MISSING";
            else if (reviewedAliasCount(tagAliases) < 3) reason = "INSUFFICIENT_ALIASES";
            else if (!codesReady(tag, sourceCodes, cv)) reason = "CODE_NOT_READY";
            int score = TsCompletenessScorer.score(tag, concept, tagAliases, cv,
                    semantics.selectConfusableByTagId(tag.getTagId()).stream().anyMatch(p -> "REVIEWED".equals(p.getReviewStatus())),
                    semantics.selectExamplesByTagId(tag.getTagId()).stream().anyMatch(e -> "REVIEWED".equals(e.getReviewStatus()) && "POS".equals(e.getExampleType())));
            if (reason == null && score < 70) reason = "LOW_COMPLETENESS";
            if (reason != null) { excluded.add(map("tag_id", tag.getTagId(), "code", reason)); continue; }
            scoreSum += score;
            selected.put(tag.getTagId(), tag); semanticCodes.put(tag.getTagId(), cv); result.tagIds.add(tag.getTagId());
        }
        for (Long tid : authority.keySet()) if (!selected.containsKey(tid) && !"1".equals(authority.get(tid).get("is_object_key"))
                && excluded.stream().noneMatch(e -> tid.equals(e.get("tag_id")))) excluded.add(map("tag_id", tid, "code", "NO_SEMANTIC"));
        if (selected.isEmpty()) {
            result.report.putAll(map("published_tag_ids", result.tagIds, "excluded", excluded, "tag_count", 0, "denominator", denominator, "coverage", "0/" + denominator, "publishable", false));
            return result;
        }
        Map<String, Object> meta = map("kind", "meta", "library_id", libraryId, "schema_version", "v1", "scope", selected.size() == denominator ? "FULL" : "PARTIAL",
                "coverage_note", coverageNote == null ? "覆盖以真实分母为准" : coverageNote);
        meta.put("source_manifest", result.sourceManifest);
        for (Map<String, Object> a : authority.values()) if ("1".equals(a.get("is_object_key"))) meta.put("object_key_binding", a.get("binding"));
        result.rows.add(meta); result.rows.addAll(domains);
        Set<Long> conceptIds = new TreeSet<>();
        for (TsTagSemantic tag : selected.values()) {
            TsConcept c = conceptMap.get(tag.getConceptId());
            while (c != null && conceptIds.add(c.getConceptId())) c = conceptMap.get(c.getParentId());
        }
        for (Long cid : conceptIds) {
            TsConcept c = conceptMap.get(cid);
            Map<String, Object> row = project(c, "concept_id", "concept_code", "library_id", "domain_dir_id", "definition", "parent_id", "status", "review_status");
            row.put("kind", "concept"); row.put("name", c.getConceptName()); row.put("aliases", aliases("CONCEPT", String.valueOf(cid), result));
            result.rows.add(row); result.concepts++;
        }
        for (TsTagSemantic tag : selected.values()) {
            Long tid = tag.getTagId(); Map<String, Object> a = authority.get(tid);
            Map<String, Object> row = project(tag, "tag_id", "semantic_type", "family_key", "caliber_variant", "concept_id", "unit", "unit_scale", "definition_long", "sensitivity", "basis_hash", "review_status", "semantic_version", "source_ref");
            for (String key : Arrays.asList("field_name", "name", "status", "source_status", "dir_path", "dir_id", "binding", "data_type", "tag_type", "business_caliber", "tech_caliber", "update_cycle", "version", "source_fingerprint", "confirmed_fingerprint")) row.put(key, a.get(key));
            row.put("kind", "tag"); row.put("caliber_struct", parse(tag.getCaliberStruct(), Collections.emptyMap()));
            row.put("allowed_operators", parse(tag.getAllowedOperators(), Collections.emptyList())); row.put("default_operator", tag.getDefaultOperator());
            row.put("concept_name", conceptMap.get(tag.getConceptId()).getConceptName());
            row.put("concept_code", conceptMap.get(tag.getConceptId()).getConceptCode());
            row.put("concept_definition", conceptMap.get(tag.getConceptId()).getDefinition());
            row.put("aliases", aliases("TAG", String.valueOf(tid), result));
            List<Map<String, Object>> pairs = new ArrayList<>(), examples = new ArrayList<>();
            for (TsConfusable p : semantics.selectConfusableByTagId(tid)) if ("REVIEWED".equals(p.getReviewStatus()) && selected.containsKey(p.getTagIdA()) && selected.containsKey(p.getTagIdB()))
                pairs.add(project(p, "pair_id", "tag_id_a", "tag_id_b", "confusion_type", "difference_note", "disambiguation_hint", "review_status", "source_ref"));
            for (TsTagExample e : semantics.selectExamplesByTagId(tid)) if ("REVIEWED".equals(e.getReviewStatus()))
                examples.add(project(e, "example_id", "tag_id", "example_type", "utterance", "expected_condition", "review_status", "source_ref"));
            if ("LOW".equals(tag.getSensitivity()) && !Arrays.asList("TEXT_FREE", "ID_KEY", "UNKNOWN").contains(tag.getSemanticType())) {
                TsTagProfile profile = profiles.selectLatest(tid);
                if (profile != null && profile.getSampleSize() != null && profile.getSampleSize() >= 20
                        && Objects.equals(profile.getSourceVersionId(), result.sourceManifest.get("version_id") == null ? null : id(result.sourceManifest.get("version_id")))
                        && Objects.equals(profile.getSourceFingerprint(), a.get("source_fingerprint"))) {
                    // 仅聚合摘要进入快照；码值频次由聚合服务先做低频抑制。
                    Map<String, Object> summary = project(profile, "profile_date", "row_count", "null_rate", "distinct_count", "min_val", "max_val", "p50", "p90", "p99", "sample_size", "sampled", "source_version_id", "source_fingerprint");
                    summary.put("top_values", parse(profile.getTopValues(), Collections.emptyList())); row.put("profile", summary);
                }
            }
            row.put("confusable", pairs); row.put("examples", examples); result.rows.add(row);
            for (TsCodeValueSemantic cv : semanticCodes.get(tid)) if ("REVIEWED".equals(cv.getReviewStatus())) {
                Map<String, Object> code = project(cv, "tag_id", "code", "rank_no", "lower_bound", "upper_bound", "lower_inclusive", "upper_inclusive", "bound_unit", "parent_tag_id", "parent_code", "level_no", "is_unknown_bucket", "review_status", "basis_hash");
                Map<String, Object> source = codesByTag.getOrDefault(tid, Collections.emptyList()).stream().filter(x -> cv.getCode().equals(x.get("code"))).findFirst().orElseThrow(() -> new ServiceException("码值依据缺失"));
                code.put("kind", "code_value"); code.put("label", source.get("definition"));
                for (String key : Arrays.asList("definition", "code_sort", "sources", "last_update_time")) code.put(key, source.get(key));
                code.put("aliases", aliases("CODE_VALUE", tid + "#" + cv.getCode(), result)); result.rows.add(code); result.codes++;
            }
        }
        for (TsBusinessTerm term : semantics.selectTermList(null, null)) if ("REVIEWED".equals(term.getReviewStatus())) {
            Map<String, Object> row = project(term, "term_id", "term", "term_norm", "review_status", "tag_object", "source_ref");
            row.put("kind", "term"); row.put("type", term.getTermType()); row.put("options", parse(term.getOptions(), Collections.emptyList())); row.put("policy", term.getDefaultPolicy()); row.put("applicable_semantic_types", parseTypes(term.getApplicableSemanticTypes())); result.rows.add(row);
        }
        meta.put("counts", map("tag", selected.size(), "concept", result.concepts, "code_value", result.codes, "domain", domains.size(), "term", result.rows.stream().filter(r -> "term".equals(r.get("kind"))).count()));
        result.report.putAll(map("published_tag_ids", result.tagIds, "excluded", excluded, "tag_count", selected.size(), "denominator", denominator,
                "coverage", selected.size() + "/" + denominator, "scope", meta.get("scope"), "mean_completeness", scoreSum / selected.size(), "minimum_completeness", 70));
        result.report.put("publishable", true);
        validateReferences(result.rows);
        return result;
    }

    @SuppressWarnings("unchecked")
    private void validateReferences(List<Map<String, Object>> rows) {
        Map<String, Map<String, Object>> codes = new HashMap<>();
        Set<Long> tags = new HashSet<>();
        for (Map<String, Object> row : rows) {
            if ("tag".equals(row.get("kind"))) tags.add(id(row.get("tag_id")));
            if ("code_value".equals(row.get("kind"))) codes.put(row.get("tag_id") + "#" + row.get("code"), row);
        }
        for (Map<String, Object> row : codes.values()) {
            List<Object> path = new ArrayList<>(); path.add(row.get("code"));
            Map<String, Object> current = row; Set<String> seen = new HashSet<>();
            seen.add(row.get("tag_id") + "#" + row.get("code"));
            while (current.get("parent_code") != null) {
                String key = (current.get("parent_tag_id") == null ? current.get("tag_id") : current.get("parent_tag_id")) + "#" + current.get("parent_code");
                if (!seen.add(key) || !codes.containsKey(key)) throw new ServiceException("码值层级引用缺失或成环，拒绝发布");
                current = codes.get(key); path.add(0, current.get("code"));
            }
            row.put("path", path);
            if (row.get("lower_bound") != null && row.get("upper_bound") != null && new java.math.BigDecimal(row.get("lower_bound").toString()).compareTo(new java.math.BigDecimal(row.get("upper_bound").toString())) >= 0) throw new ServiceException("码值区间端点非法");
        }
        Map<String, String> pairContent = new HashMap<>(); Map<String, Integer> pairCount = new HashMap<>();
        for (Map<String, Object> row : rows) {
            Set<String> local = new HashSet<>();
            for (Map<String, Object> pair : (List<Map<String, Object>>) row.getOrDefault("confusable", Collections.emptyList())) {
                Long a = id(pair.get("tag_id_a")), b = id(pair.get("tag_id_b"));
                String key = Math.min(a, b) + "#" + Math.max(a, b), value = TsSnapshotCanonicalizer.dumps(pair);
                if (a.equals(b) || !tags.contains(a) || !tags.contains(b) || !local.add(key) || (pairContent.containsKey(key) && !value.equals(pairContent.get(key)))) throw new ServiceException("易混淆引用重复或不一致");
                pairContent.put(key, value); pairCount.put(key, pairCount.getOrDefault(key, 0) + 1);
            }
        }
        if (pairCount.values().stream().anyMatch(n -> n != 2)) throw new ServiceException("易混淆对两端必须对称导出");
    }

    private boolean conceptReady(TsConcept c, Map<Long, TsConcept> all, Set<Long> seen) {
        if (c == null || !"REVIEWED".equals(c.getReviewStatus()) || !"0".equals(c.getStatus()) || !seen.add(c.getConceptId())) return false;
        return c.getParentId() == null || c.getParentId() == 0 || conceptReady(all.get(c.getParentId()), all, seen);
    }
    private boolean codesReady(TsTagSemantic tag, List<Map<String, Object>> source, List<TsCodeValueSemantic> codes) {
        boolean requires = "BOOL".equals(tag.getSemanticType()) || (tag.getSemanticType() != null && tag.getSemanticType().startsWith("ENUM_"));
        if (requires && source.isEmpty()) return false;
        Map<String, TsCodeValueSemantic> byCode = new HashMap<>();
        for (TsCodeValueSemantic c : codes) if ("REVIEWED".equals(c.getReviewStatus())) byCode.put(c.getCode(), c);
        if (byCode.size() != source.size()) return false;
        for (Map<String, Object> s : source) {
            TsCodeValueSemantic c = byCode.get(String.valueOf(s.get("code")));
            if (c == null || !Objects.equals(c.getBasisHash(), codeBasisHash(tag.getTagId(), s, tag.getBasisHash()))) return false;
        }
        if ("ENUM_ORDINAL".equals(tag.getSemanticType())) {
            try { validateOrdinal(codes); } catch (ServiceException e) { return false; }
        }
        return true;
    }
    private static boolean coreReady(TsTagSemantic tag) {
        if (tag.getSemanticType() == null || "UNKNOWN".equals(tag.getSemanticType())) return false;
        try {
            com.fasterxml.jackson.databind.JsonNode caliber = JSON.readTree(tag.getCaliberStruct());
            com.fasterxml.jackson.databind.JsonNode operators = JSON.readTree(tag.getAllowedOperators());
            if (caliber == null || !caliber.isObject() || caliber.size() == 0 || operators == null || !operators.isArray() || operators.size() == 0) return false;
            for (com.fasterxml.jackson.databind.JsonNode operator : operators) if (!operator.isTextual() || operator.asText().trim().isEmpty()) return false;
            return true;
        } catch (Exception e) { return false; }
    }
    static long reviewedAliasCount(List<TsAlias> aliases) {
        return aliases.stream().filter(a -> "REVIEWED".equals(a.getReviewStatus()) && !"NEGATIVE".equals(a.getAliasType()))
                .map(a -> a.getAliasNorm() == null ? a.getAliasText() : a.getAliasNorm()).filter(Objects::nonNull)
                .map(String::trim).filter(s -> !s.isEmpty()).distinct().count();
    }
    /** 等级码可以只有经确认的秩序；一旦配置数值边界，整组必须通过区间校验。 */
    static void validateOrdinal(List<TsCodeValueSemantic> all) {
        Set<Integer> ranks = new HashSet<>();
        boolean hasBounds = false;
        for (TsCodeValueSemantic c : all) if ("REVIEWED".equals(c.getReviewStatus()) && !Integer.valueOf(1).equals(c.getIsUnknownBucket())) {
            if (c.getRankNo() == null || !ranks.add(c.getRankNo())) throw new ServiceException("有序码值必须具备唯一顺序");
            hasBounds |= c.getLowerBound() != null || c.getUpperBound() != null || c.getBoundUnit() != null || c.getLowerInclusive() != null || c.getUpperInclusive() != null;
        }
        if (ranks.isEmpty()) throw new ServiceException("有序码值缺少有效顺序");
        if (hasBounds) validateIntervals(all);
    }
    /** 未知桶不参与区间；有序档位必须有一致单位、秩序及无缝且不重叠的边界。 */
    static void validateIntervals(List<TsCodeValueSemantic> all) {
        List<TsCodeValueSemantic> rows = new ArrayList<>();
        for (TsCodeValueSemantic c : all) if ("REVIEWED".equals(c.getReviewStatus()) && !Integer.valueOf(1).equals(c.getIsUnknownBucket())) rows.add(c);
        if (rows.isEmpty()) throw new ServiceException("有序码值缺少有效区间");
        rows.sort(Comparator.comparing(TsCodeValueSemantic::getRankNo, Comparator.nullsFirst(Comparator.naturalOrder())));
        Set<Integer> ranks = new HashSet<>();
        TsCodeValueSemantic previous = null;
        for (TsCodeValueSemantic row : rows) {
            if (row.getRankNo() == null || !ranks.add(row.getRankNo()) || row.getBoundUnit() == null
                    || row.getLowerInclusive() == null || row.getUpperInclusive() == null) throw new ServiceException("有序码值的顺序、单位和端点包含性必须明确");
            if (row.getLowerBound() != null && row.getUpperBound() != null && row.getLowerBound().compareTo(row.getUpperBound()) >= 0) throw new ServiceException("码值区间端点非法");
            if (previous != null && (!Objects.equals(previous.getBoundUnit(), row.getBoundUnit()) || previous.getUpperBound() == null || row.getLowerBound() == null
                    || previous.getUpperBound().compareTo(row.getLowerBound()) != 0
                    || previous.getUpperInclusive() + row.getLowerInclusive() != 1)) throw new ServiceException("有序码值存在单位冲突、重叠或缺口");
            previous = row;
        }
    }
    private List<Map<String, Object>> aliases(String type, String id, Result result) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (TsAlias a : semantics.selectAliasList(type, id)) if ("REVIEWED".equals(a.getReviewStatus())) rows.add(project(a, "alias_id", "target_type", "target_id", "alias_text", "alias_norm", "alias_type", "weight", "review_status", "source_ref"));
        result.aliases += rows.size(); return rows;
    }
    public static String basisHash(Map<String, Object> tag, List<Map<String, Object>> codes) {
        Map<String, Object> payload = map("field_name", tag.get("field_name"), "name", tag.get("name"), "data_type", tag.get("data_type"),
                "business_caliber", nz(tag.get("business_caliber")), "tech_caliber", nz(tag.get("tech_caliber")), "version", tag.get("version"), "source_fingerprint", nz(tag.get("source_fingerprint")));
        List<Map<String, Object>> list = new ArrayList<>();
        codes.stream().sorted(Comparator.comparing(c -> String.valueOf(c.get("code")))).forEach(c -> list.add(map("code", c.get("code"), "definition", nz(c.get("definition")), "label", nz(c.get("label")))));
        payload.put("codes", list);
        // codes 已按 code 排序；依据哈希不使用快照的无序对象数组排序规则。
        try { return TsSnapshotCanonicalizer.sha256(new ObjectMapper().configure(com.fasterxml.jackson.databind.SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true).writeValueAsString(payload)); }
        catch (Exception e) { throw new ServiceException("依据哈希失败"); }
    }
    public static String codeBasisHash(Long tagId, Map<String, Object> code, String tagBasis) {
        return TsSnapshotCanonicalizer.sha256(TsSnapshotCanonicalizer.dumps(map("tag_id", tagId, "code", code.get("code"), "definition", nz(code.get("definition")), "tag_basis", tagBasis)));
    }
    private static Object nz(Object v) { return v == null ? "" : v; }
    private static Object parseTypes(String value) {
        if (value == null || value.trim().isEmpty()) return Collections.emptyList();
        if (value.trim().startsWith("[")) return parse(value, Collections.emptyList());
        return Arrays.asList(value.split("\\s*,\\s*"));
    }
    public static Object parse(String value, Object fallback) {
        if (value == null || value.isEmpty()) return fallback;
        try { return JSON.readValue(value, Object.class); } catch (Exception e) { throw new ServiceException("语义 JSON 格式错误"); }
    }
    @SuppressWarnings("unchecked")
    private static Map<String, Object> project(Object bean, String... keys) {
        Map<String, Object> raw = JSON.convertValue(bean, Map.class), out = new LinkedHashMap<>();
        for (String key : keys) { Object v = raw.get(key); out.put(key, v instanceof java.math.BigDecimal ? ((java.math.BigDecimal)v).toPlainString() : v); }
        return out;
    }
    public static Map<String, Object> map(Object... pairs) {
        Map<String, Object> out = new LinkedHashMap<>(); for (int i = 0; i < pairs.length; i += 2) out.put(String.valueOf(pairs[i]), pairs[i + 1]); return out;
    }
    private static Long id(Object v) { return Long.valueOf(String.valueOf(v)); }
    public static String json(Object value) { try { return JSON.writeValueAsString(value); } catch (Exception e) { throw new ServiceException("序列化失败"); } }
}
