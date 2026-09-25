package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.common.utils.html.EscapeUtil;

class XssOperatorCleanTest {

    @Test
    void htmlFilterTruncatesOperatorsWhenGreaterThanFollows() throws Exception {
        String operators = "[\">\",\">=\",\"<\",\"<=\",\"between\"]";
        ObjectMapper mapper = new ObjectMapper();
        String body = "{\"tagId\":1488,\"allowedOperators\":" + mapper.writeValueAsString(operators)
                + ",\"defaultOperator\":\">\"}";
        JsonNode cleaned = mapper.readTree(EscapeUtil.clean(body));
        assertEquals("[\"&gt;\",\"&gt;=\",\"&lt;\",\"", cleaned.get("allowedOperators").asText());
    }

    @Test
    void semanticDraftUrlsAreExcludedFromXss() throws Exception {
        String yml = new String(Files.readAllBytes(Paths.get("../ruoyi-admin/src/main/resources/application.yml")), StandardCharsets.UTF_8);
        assertTrue(yml.contains("/taglibrary/semantic/**"));
        assertTrue(StringUtils.isMatch("/taglibrary/semantic/**", "/taglibrary/semantic/tag"));
    }

    @Test
    void agentPlanUrlsAreExcludedFromXss() throws Exception {
        String yml = new String(Files.readAllBytes(Paths.get("../ruoyi-admin/src/main/resources/application.yml")), StandardCharsets.UTF_8);
        int excludes = yml.indexOf("excludes:");
        String line = yml.substring(excludes, yml.indexOf('\n', excludes));
        assertTrue(line.contains("/taglibrary/agent/**"), line);
        assertTrue(StringUtils.isMatch("/taglibrary/agent/**", "/taglibrary/agent/threads/abc/runs"));
        assertTrue(StringUtils.isMatch("/taglibrary/agent/**", "/taglibrary/agent/threads/abc/resume"));
    }
}
