package com.ruoyi.taglibrary.service;

import java.net.URI;
import java.net.URLEncoder;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;

/**
 * Skill 引擎（Python tagpilot-agent）HTTP 客户端。
 *
 * <p>只访问运维配置中的服务地址与运行令牌，不接受用户提供的 URL；
 * 引擎未启动、超时或返回业务错误码时统一转成中文 {@link ServiceException}，
 * 前端看到的是可读提示而不是 500 堆栈。</p>
 */
@Component
public class SkillClient {

    private static final Logger log = LoggerFactory.getLogger(SkillClient.class);

    /** Skill 引擎地址（与编排层同址，默认 127.0.0.1:8092） */
    @Value("${tag.agent-url:http://127.0.0.1:8092}")
    private String baseUrl;

    @Value("${tag.runtime-token:}")
    private String token;

    private final ObjectMapper objectMapper = new ObjectMapper();

    public Map<String, Object> get(String path) {
        return exchange(path, HttpMethod.GET, null);
    }

    /** 带查询参数的 GET；空值参数自动跳过 */
    public Map<String, Object> get(String path, Map<String, String> query) {
        return exchange(withQuery(path, query), HttpMethod.GET, null);
    }

    public Map<String, Object> post(String path, Object body) {
        return exchange(path, HttpMethod.POST, body);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> exchange(String path, HttpMethod method, Object body) {
        if (token == null || token.isEmpty()) {
            throw new ServiceException("Skill 引擎服务认证未配置");
        }
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000);
        // 试运行需等待聚合计算，其余治理接口按普通超时
        factory.setReadTimeout(path.contains("/run") ? 120000 : 30000);
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);
        URI uri;
        try {
            uri = URI.create(baseUrl + path);
        } catch (IllegalArgumentException e) {
            throw new ServiceException("Skill 引擎请求地址非法");
        }
        try {
            ResponseEntity<Map> response = new RestTemplate(factory)
                    .exchange(uri, method, new HttpEntity<Object>(body, headers), Map.class);
            Map<String, Object> result = response.getBody();
            if (result == null) {
                throw new ServiceException("Skill 引擎响应为空");
            }
            return result;
        } catch (HttpStatusCodeException e) {
            throw new ServiceException(describe(e), e.getRawStatusCode());
        } catch (RestClientException e) {
            log.warn("Skill 引擎调用失败: {} {}", method, path, e);
            throw new ServiceException("Skill 引擎暂不可用或拒绝请求，请确认洞察技能服务已启动并配置了运行令牌");
        }
    }

    /** 把引擎的错误响应翻译成中文提示：优先取业务 detail，再按状态码兜底 */
    private String describe(HttpStatusCodeException e) {
        int code = e.getRawStatusCode();
        String detail = null;
        String body = e.getResponseBodyAsString();
        if (body != null && !body.isEmpty()) {
            try {
                JsonNode node = objectMapper.readTree(body);
                for (String key : new String[] { "detail", "message", "error", "msg" }) {
                    JsonNode value = node.get(key);
                    if (value != null && !value.isNull() && !value.asText().trim().isEmpty()) {
                        detail = value.asText().trim();
                        break;
                    }
                }
            } catch (Exception ignore) {
                // 非 JSON 响应，退化为状态码描述
            }
        }
        String prefix;
        switch (code) {
            case 400: prefix = "请求参数不合法"; break;
            case 403: prefix = "权限不足"; break;
            case 404: prefix = "技能不存在或技能引擎未提供该接口"; break;
            case 409: prefix = "当前状态不允许该操作"; break;
            case 422: prefix = "数据未就绪或样本不足"; break;
            default: prefix = "Skill 引擎返回错误（HTTP " + code + "）"; break;
        }
        return detail == null || detail.isEmpty() ? prefix : prefix + "：" + detail;
    }

    private String withQuery(String path, Map<String, String> query) {
        if (query == null || query.isEmpty()) {
            return path;
        }
        StringBuilder sb = new StringBuilder(path);
        char sep = path.contains("?") ? '&' : '?';
        for (Map.Entry<String, String> entry : query.entrySet()) {
            String value = entry.getValue();
            if (value == null || value.isEmpty()) {
                continue;
            }
            sb.append(sep).append(entry.getKey()).append('=').append(encode(value));
            sep = '&';
        }
        return sb.toString();
    }

    private String encode(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (Exception e) {
            return value;
        }
    }
}
