package com.ruoyi.databroker.metadata;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class MySqlMetadataCollector {

    private static final String SQL_TABLES =
        "select table_name, table_type, table_comment, table_rows " +
        "from information_schema.tables " +
        "where table_schema = ? and table_type in ('BASE TABLE', 'VIEW') " +
        "order by table_name";

    private static final String SQL_COLUMNS =
        "select table_name, column_name, ordinal_position, column_type, data_type, " +
        "is_nullable, column_default, column_comment, column_key " +
        "from information_schema.columns " +
        "where table_schema = ? order by table_name, ordinal_position";

    private static final String SQL_FK =
        "select table_name, column_name, referenced_table_name, referenced_column_name " +
        "from information_schema.KEY_COLUMN_USAGE " +
        "where table_schema = ? and referenced_table_name is not null";

    private static final String SQL_VERSION = "select version()";

    public String fetchVersion(Connection conn) throws Exception {
        try (Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(SQL_VERSION)) {
            if (rs.next()) {
                return rs.getString(1);
            }
            return "";
        }
    }

    public MetadataSyncResult collect(Connection conn, String databaseName) throws Exception {
        MetadataSyncResult result = new MetadataSyncResult();

        // Collect tables
        List<MetadataTable> tables = new ArrayList<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_TABLES)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    MetadataTable t = new MetadataTable();
                    t.setTableName(rs.getString("table_name"));
                    t.setTableType(rs.getString("table_type"));
                    t.setTableComment(rs.getString("table_comment"));
                    t.setTableRows(rs.getLong("table_rows"));
                    tables.add(t);
                    if ("BASE TABLE".equals(t.getTableType())) {
                        result.setTableCount(result.getTableCount() + 1);
                    } else {
                        result.setViewCount(result.getViewCount() + 1);
                    }
                }
            }
        }

        // Collect columns
        List<MetadataColumn> columns = new ArrayList<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_COLUMNS)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    MetadataColumn c = new MetadataColumn();
                    c.setTableName(rs.getString("table_name"));
                    c.setColumnName(rs.getString("column_name"));
                    c.setOrdinalPosition(rs.getInt("ordinal_position"));
                    c.setColumnType(rs.getString("column_type"));
                    c.setDataType(rs.getString("data_type"));
                    c.setIsNullable(rs.getString("is_nullable"));
                    c.setColumnDefault(rs.getString("column_default"));
                    c.setColumnComment(rs.getString("column_comment"));
                    c.setColumnKey(rs.getString("column_key"));
                    columns.add(c);
                    result.setColumnCount(result.getColumnCount() + 1);
                }
            }
        }

        // Collect foreign keys
        Map<String, Map<String, String[]>> fkMap = new HashMap<>();
        try (PreparedStatement ps = conn.prepareStatement(SQL_FK)) {
            ps.setString(1, databaseName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    String tableName = rs.getString("table_name");
                    String columnName = rs.getString("column_name");
                    String refTable = rs.getString("referenced_table_name");
                    String refColumn = rs.getString("referenced_column_name");
                    fkMap.computeIfAbsent(tableName, k -> new HashMap<>())
                          .put(columnName, new String[]{refTable, refColumn});
                }
            }
        }

        // Set FK info on columns
        for (MetadataColumn col : columns) {
            Map<String, String[]> tableFks = fkMap.get(col.getTableName());
            if (tableFks != null && tableFks.containsKey(col.getColumnName())) {
                col.setColumnKey("FK");
            }
        }

        result.setTables(tables);
        result.setColumns(columns);
        return result;
    }
}
