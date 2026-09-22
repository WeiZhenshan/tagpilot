package com.ruoyi.taglibrary.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

class TsSnapshotCanonicalizerTest {
    @Test
    @SuppressWarnings("unchecked")
    void javaHashMatchesSharedVector() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        try (InputStream in = getClass().getResourceAsStream("/semantic/hash_vector.json")) {
            Map<String, Object> payload = mapper.readValue(in, new TypeReference<Map<String, Object>>() { });
            List<Map<String, Object>> rows = (List<Map<String, Object>>) payload.get("rows");
            List<String> lines = (List<String>) payload.get("canonical_lines");
            assertEquals(lines.get(0), TsSnapshotCanonicalizer.dumps(rows.get(0)));
            assertEquals(lines.get(1), TsSnapshotCanonicalizer.dumps(rows.get(1)));
            assertEquals(String.valueOf(payload.get("expected_hash")), TsSnapshotCanonicalizer.contentHash(rows));
        }
    }

    @Test
    void envelopeFieldsAreExcluded() {
        java.util.LinkedHashMap<String, Object> row = new java.util.LinkedHashMap<String, Object>();
        row.put("kind", "meta");
        row.put("snapshot_id", "L107-X");
        row.put("content_hash", "abc");
        row.put("library_id", Integer.valueOf(107));
        String dumped = TsSnapshotCanonicalizer.dumps(row);
        org.junit.jupiter.api.Assertions.assertFalse(dumped.contains("snapshot_id"));
        org.junit.jupiter.api.Assertions.assertFalse(dumped.contains("content_hash"));
    }
}
