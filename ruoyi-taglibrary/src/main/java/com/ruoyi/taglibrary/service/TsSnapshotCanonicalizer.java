package com.ruoyi.taglibrary.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.ruoyi.common.exception.ServiceException;

/**
 * 与 Python tag_semantic.snapshot.canonicalize 对齐：信封字段不参与内容哈希。
 */
public final class TsSnapshotCanonicalizer {
    private static final Set<String> ENVELOPE = new TreeSet<String>();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    static {
        ENVELOPE.add("snapshot_id");
        ENVELOPE.add("snapshot_no");
        ENVELOPE.add("generated_at");
        ENVELOPE.add("content_hash");
        ENVELOPE.add("status");
        ENVELOPE.add("hit_count");
        MAPPER.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
        MAPPER.configure(JsonGenerator.Feature.ESCAPE_NON_ASCII, false);
        MAPPER.configure(JsonGenerator.Feature.WRITE_BIGDECIMAL_AS_PLAIN, true);
    }

    private TsSnapshotCanonicalizer() {
    }

    @SuppressWarnings("unchecked")
    public static Object canonicalize(Object value) { return canonicalize(value, false); }

    private static Object canonicalize(Object value, boolean ordered) {
        if (value instanceof Map) {
            Map<String, Object> cleaned = new LinkedHashMap<String, Object>();
            Map<?, ?> raw = (Map<?, ?>) value;
            List<String> keys = new ArrayList<String>();
            for (Object key : raw.keySet()) {
                String name = String.valueOf(key);
                keys.add(name);
            }
            Collections.sort(keys);
            for (String key : keys) {
                cleaned.put(key, canonicalize(raw.get(key), ordered));
            }
            return cleaned;
        }
        if (value instanceof List) {
            List<?> list = (List<?>) value;
            List<Object> mapped = new ArrayList<Object>();
            boolean allMaps = !list.isEmpty();
            boolean allScalars = true;
            for (Object item : list) {
                Object next = canonicalize(item, ordered);
                mapped.add(next);
                if (!(next instanceof Map)) {
                    allMaps = false;
                }
                if (item instanceof Map || item instanceof List) {
                    allScalars = false;
                }
            }
            if (allMaps && !ordered) {
                mapped.sort(new Comparator<Object>() {
                    @Override
                    public int compare(Object a, Object b) {
                        try { return MAPPER.writeValueAsString(a).compareTo(MAPPER.writeValueAsString(b)); }
                        catch (Exception e) { throw new ServiceException("规范化排序失败"); }
                    }
                });
            }
            if (allScalars) {
                return new ArrayList<Object>(list);
            }
            return mapped;
        }
        if (value instanceof java.math.BigDecimal) return ((java.math.BigDecimal) value).stripTrailingZeros();
        if (value instanceof Double || value instanceof Float) return new java.math.BigDecimal(value.toString()).stripTrailingZeros();
        return value;
    }

    public static String dumps(Object value) {
        try {
            if (value instanceof Map) {
                Map<?, ?> raw = (Map<?, ?>) value;
                Map<String, Object> row = new LinkedHashMap<String, Object>();
                for (Map.Entry<?, ?> entry : raw.entrySet()) {
                    String key = String.valueOf(entry.getKey());
                    if (("meta".equals(raw.get("kind")) && ENVELOPE.contains(key)) || "hit_count".equals(key)) continue;
                    row.put(key, entry.getValue());
                }
                if ("meta".equals(raw.get("kind")) && row.get("source_manifest") instanceof Map) {
                    Map<Object, Object> manifest = new LinkedHashMap<Object, Object>((Map<?, ?>) row.get("source_manifest"));
                    manifest.remove("frozen_at"); manifest.remove("freeze_sha256"); row.put("source_manifest", manifest);
                }
                value = row;
            }
            return MAPPER.writeValueAsString(canonicalize(value, value instanceof Map && "capability".equals(((Map<?,?>) value).get("kind"))));
        } catch (Exception e) {
            throw new ServiceException("规范化 JSON 失败");
        }
    }

    public static String contentHash(List<Map<String, Object>> rows) {
        List<Map<String, Object>> ordered = new ArrayList<Map<String, Object>>(rows);
        ordered.sort(new Comparator<Map<String, Object>>() {
            @Override
            public int compare(Map<String, Object> a, Map<String, Object> b) {
                String[] left = sortKey(a), right = sortKey(b);
                for (int i = 0; i < left.length; i++) { int cmp = left[i].compareTo(right[i]); if (cmp != 0) return cmp; }
                return 0;
            }
        });
        StringBuilder payload = new StringBuilder();
        for (Map<String, Object> row : ordered) {
            payload.append(dumps(row)).append('\n');
        }
        return sha256(payload.toString());
    }

    private static String[] sortKey(Map<String, Object> row) {
        String kind = stringVal(row.get("kind"));
        if ("meta".equals(kind)) {
            return new String[] {"0", "", ""};
        }
        if ("domain".equals(kind)) {
            return new String[] {"1", stringVal(row.get("dir_id")), ""};
        }
        if ("concept".equals(kind)) {
            return new String[] {"2", first(row, "concept_id", "concept_code"), ""};
        }
        if ("tag".equals(kind)) {
            return new String[] {"3", stringVal(row.get("tag_id")), ""};
        }
        if ("code_value".equals(kind)) {
            return new String[] {"4", stringVal(row.get("tag_id")), stringVal(row.get("code"))};
        }
        if ("term".equals(kind)) {
            return new String[] {"5", first(row, "term_id", "term_norm"), ""};
        }
        if ("capability".equals(kind)) return new String[]{"6",stringVal(row.get("capability_id")),""};
        return new String[] {"9", kind, dumps(row)};
    }

    private static String first(Map<String, Object> row, String a, String b) {
        String left = stringVal(row.get(a));
        return left.isEmpty() ? stringVal(row.get(b)) : left;
    }

    private static String stringVal(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    public static String sha256(String content) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(content.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new ServiceException("计算哈希失败");
        }
    }
}
