package com.ruoyi.web.core.config;

import java.util.regex.Pattern;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;

/** 生产关闭文档时，静态 Swagger 资源与异常路径也统一返回 404。 */
@Configuration
@ConditionalOnProperty(name = "swagger.enabled", havingValue = "false", matchIfMissing = true)
public class DocumentationGuardConfig {
    private static final Pattern DOCS = Pattern.compile(
            "^/(v[23]/api-docs|swagger-ui|swagger-resources|webjars|doc\\.html)(/|$|\\.).*",
            Pattern.CASE_INSENSITIVE);

    @Bean
    public FilterRegistrationBean<javax.servlet.Filter> documentationGuard() {
        FilterRegistrationBean<javax.servlet.Filter> registration = new FilterRegistrationBean<>();
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        registration.setFilter((request, response, chain) -> {
            HttpServletRequest http = (HttpServletRequest) request;
            // 去掉矩阵参数后再匹配，不让分号路径进入文档栈/安全防火墙。
            String path = http.getRequestURI().substring(http.getContextPath().length())
                    .replaceAll(";[^/]*", "").replaceAll("/+", "/");
            if (DOCS.matcher(path).matches()) {
                ((HttpServletResponse) response).setStatus(HttpServletResponse.SC_NOT_FOUND);
                return;
            }
            chain.doFilter(request, response);
        });
        return registration;
    }
}
