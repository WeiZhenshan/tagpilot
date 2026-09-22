package com.ruoyi.taglibrary.service;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import com.ruoyi.common.exception.ServiceException;

/** 仅访问运维配置中的 Agent 编排层，不接受用户提供的 URL。 */
@Component
public class TsAgentClient {
    @Value("${tag.agent-url:http://127.0.0.1:8092}") private String baseUrl;
    @Value("${tag.runtime-token:}") private String token;
    public Map<String, Object> get(String path) { return exchange(path, HttpMethod.GET, null); }
    public Map<String, Object> post(String path, Object body) { return exchange(path, HttpMethod.POST, body); }
    public Map<String, Object> delete(String path) { return exchange(path, HttpMethod.DELETE, null); }
    @SuppressWarnings("unchecked")
    private Map<String, Object> exchange(String path, HttpMethod method, Object body) {
        if (token == null || token.isEmpty()) throw new ServiceException("编排层服务认证未配置");
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000); factory.setReadTimeout(60000);
        HttpHeaders headers = new HttpHeaders(); headers.setContentType(MediaType.APPLICATION_JSON); headers.setBearerAuth(token);
        try {
            Map<String, Object> response = new RestTemplate(factory).exchange(baseUrl + path, method, new HttpEntity<>(body, headers), Map.class).getBody();
            if (response == null) throw new ServiceException("编排层响应为空");
            return response;
        } catch (org.springframework.web.client.RestClientException e) {
            throw new ServiceException("编排层暂不可用或拒绝请求，请检查语义引擎与编排层日志");
        }
    }
}
