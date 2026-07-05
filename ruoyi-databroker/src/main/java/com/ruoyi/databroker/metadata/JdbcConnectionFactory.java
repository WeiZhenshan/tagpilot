package com.ruoyi.databroker.metadata;

import java.sql.Connection;
import java.sql.DriverManager;
import java.util.Properties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import com.ruoyi.databroker.config.DataBrokerProperties;

@Component
public class JdbcConnectionFactory {

    @Autowired
    private DataBrokerProperties properties;

    public Connection createConnection(String host, int port, String databaseName,
                                        String username, String password) throws Exception {
        String url = String.format("jdbc:mysql://%s:%d/%s?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai",
                host, port, databaseName);

        Properties props = new Properties();
        props.setProperty("user", username);
        props.setProperty("password", password);
        props.setProperty("connectTimeout", String.valueOf(properties.getJdbc().getConnectTimeout()));
        props.setProperty("socketTimeout", String.valueOf(properties.getJdbc().getSocketTimeout()));

        return DriverManager.getConnection(url, props);
    }
}
