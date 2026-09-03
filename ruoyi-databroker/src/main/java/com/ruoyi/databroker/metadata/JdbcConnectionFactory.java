package com.ruoyi.databroker.metadata;

import java.sql.Connection;
import java.sql.DriverManager;
import java.util.Properties;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.domain.DpDataSource;

@Component
public class JdbcConnectionFactory implements DisposableBean {

    /** use_pool='1' 且已入库的数据源，按 datasourceId 缓存 HikariCP 连接池 */
    private final ConcurrentMap<Long, HikariDataSource> pools = new ConcurrentHashMap<>();

    @Autowired
    private DataBrokerProperties properties;

    public Connection createConnection(DpDataSource ds, String password) throws Exception {
        if (ds.getDatasourceId() != null && "1".equals(ds.getUsePool())) {
            return obtainPool(ds, password).getConnection();
        }
        return createDirectConnection(ds, password);
    }

    /** 使数据源的连接池失效（配置变更/删除后调用），下次访问按最新配置重建 */
    public void evictPool(Long datasourceId) {
        if (datasourceId == null) {
            return;
        }
        HikariDataSource pool = pools.remove(datasourceId);
        if (pool != null) {
            pool.close();
        }
    }

    private HikariDataSource obtainPool(DpDataSource ds, String password) {
        return pools.computeIfAbsent(ds.getDatasourceId(), id -> createPool(ds, password));
    }

    private HikariDataSource createPool(DpDataSource ds, String password) {
        HikariConfig config = new HikariConfig();
        config.setPoolName("dp-pool-" + ds.getDatasourceId());
        config.setDriverClassName("com.mysql.cj.jdbc.Driver");
        config.setJdbcUrl(buildUrl(ds));
        config.setUsername(ds.getUsername());
        config.setPassword(password);
        config.setMaximumPoolSize(properties.getJdbc().getPoolMaxSize());
        // 借出超时沿用 connectTimeout：数据源不可用时快速失败，避免交互操作长时间等待
        config.setConnectionTimeout(Math.max(1000, properties.getJdbc().getConnectTimeout()));
        return new HikariDataSource(config);
    }

    private Connection createDirectConnection(DpDataSource ds, String password) throws Exception {
        Properties props = new Properties();
        props.setProperty("user", ds.getUsername());
        props.setProperty("password", password);
        return DriverManager.getConnection(buildUrl(ds), props);
    }

    /** connectTimeout/socketTimeout 直接写入 URL，保证直连与池化两条路径超时行为一致 */
    private String buildUrl(DpDataSource ds) {
        return String.format("jdbc:mysql://%s:%d/%s?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai"
                        + "&connectTimeout=%d&socketTimeout=%d",
                ds.getHost(), ds.getPort(), ds.getDatabaseName(),
                properties.getJdbc().getConnectTimeout(), properties.getJdbc().getSocketTimeout());
    }

    @Override
    public void destroy() {
        pools.values().forEach(HikariDataSource::close);
        pools.clear();
    }
}
