package com.ruoyi.taglibrary.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.UUID;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.SqlSessionFactoryBean;
import org.mybatis.spring.SqlSessionTemplate;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.SimpleDriverDataSource;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionTemplate;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.taglibrary.domain.TsIndexBuild;

/** 用真实 MyBatis 映射 + H2 事务验证：改绑随外层激活事务提交/回滚，不同快照不动，重复提交幂等。 */
class TsAudiencePlanRebinderTxTest {

    private Connection keeper;
    private TransactionTemplate tx;
    private TsAudiencePlanRebinder rebinder;
    private String url;

    @BeforeEach
    void setup() throws Exception {
        url = "jdbc:h2:mem:rebind" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE";
        keeper = DriverManager.getConnection(url);
        try (Statement st = keeper.createStatement()) {
            st.execute("create table tl_object_group(group_id bigint primary key, group_name varchar(64), group_desc varchar(500), library_id bigint,"
                    + " rule_json clob, group_sql clob, user_count bigint, del_flag char(1) default '0', create_by varchar(64), create_time timestamp,"
                    + " update_by varchar(64), update_time timestamp, remark varchar(500))");
        }
        insert(132, 107, TsAudiencePlanRebinderTest.group(132, "S6", "p3g", "h-old").getRuleJson(), "0");
        insert(131, 107, TsAudiencePlanRebinderTest.group(131, "S6", "p3g", "h-old").getRuleJson(), "0");
        insert(120, 107, TsAudiencePlanRebinderTest.group(120, "S2", "r3", "h2").getRuleJson(), "0");
        insert(119, 107, TsAudiencePlanRebinderTest.group(119, "S6", "p3g", "h-old").getRuleJson(), "2");
        insert(200, 108, TsAudiencePlanRebinderTest.group(200, "S6", "p3g", "h-old").getRuleJson(), "0");

        SimpleDriverDataSource ds = new SimpleDriverDataSource(new org.h2.Driver(), url);
        SqlSessionFactoryBean factory = new SqlSessionFactoryBean();
        factory.setDataSource(ds);
        factory.setTypeAliases(TlObjectGroup.class);
        // 使用生产映射文件；仅把 MySQL 的 sysdate() 换成 H2 可识别的 current_timestamp。
        String xml = new String(org.springframework.util.StreamUtils.copyToByteArray(new ClassPathResource("mapper/objectgroup/TlObjectGroupMapper.xml").getInputStream()),
                java.nio.charset.StandardCharsets.UTF_8).replace("sysdate()", "current_timestamp");
        factory.setMapperLocations(new org.springframework.core.io.ByteArrayResource(xml.getBytes(java.nio.charset.StandardCharsets.UTF_8), "TlObjectGroupMapper.xml"));
        SqlSessionFactory sessions = factory.getObject();
        TlObjectGroupMapper mapper = new SqlSessionTemplate(sessions).getMapper(TlObjectGroupMapper.class);
        rebinder = new TsAudiencePlanRebinder();
        ReflectionTestUtils.setField(rebinder, "groups", mapper);
        tx = new TransactionTemplate(new DataSourceTransactionManager(ds));
    }

    @AfterEach
    void close() throws Exception { keeper.close(); }

    private void insert(long id, long library, String rule, String delFlag) throws Exception {
        try (PreparedStatement ps = keeper.prepareStatement("insert into tl_object_group(group_id,group_name,library_id,rule_json,del_flag,update_by) values(?,?,?,?,?,'seed')")) {
            ps.setLong(1, id); ps.setString(2, "g" + id); ps.setLong(3, library); ps.setString(4, rule); ps.setString(5, delFlag); ps.executeUpdate();
        }
    }

    private String buildOf(long id) throws Exception {
        try (Statement st = keeper.createStatement(); ResultSet rs = st.executeQuery("select rule_json from tl_object_group where group_id=" + id)) {
            rs.next();
            Object plan = new com.fasterxml.jackson.databind.ObjectMapper().readValue(rs.getString(1), java.util.Map.class).get("audiencePlan");
            return String.valueOf(((java.util.Map<?, ?>) plan).get("build_id"));
        }
    }

    @Test
    void commitRebindsOnlySameSnapshotLiveGroupsAndIsIdempotent() throws Exception {
        TsIndexBuild sf1 = TsAudiencePlanRebinderTest.build("sf1", "S6", "h-new");
        assertEquals(Integer.valueOf(2), tx.execute(s -> rebinder.rebindSameSnapshot(107L, sf1)));
        assertEquals("sf1", buildOf(132)); assertEquals("sf1", buildOf(131));
        assertEquals("r3", buildOf(120));   // 不同快照：保持原样
        assertEquals("p3g", buildOf(119));  // 已删除：不动
        assertEquals("p3g", buildOf(200));  // 其它库：不动
        assertEquals(Integer.valueOf(0), tx.execute(s -> rebinder.rebindSameSnapshot(107L, sf1)));

        // 同快照来回切：切回 p3g 再切回 sf1，客群跟着走
        TsIndexBuild p3g = TsAudiencePlanRebinderTest.build("p3g", "S6", "h-old");
        assertEquals(Integer.valueOf(2), tx.execute(s -> rebinder.rebindSameSnapshot(107L, p3g)));
        assertEquals("p3g", buildOf(132));
        assertEquals(Integer.valueOf(2), tx.execute(s -> rebinder.rebindSameSnapshot(107L, sf1)));
        assertEquals("sf1", buildOf(132)); assertEquals("r3", buildOf(120));
    }

    @Test
    void failureLaterInActivationRollsBackRebind() throws Exception {
        TsIndexBuild sf1 = TsAudiencePlanRebinderTest.build("sf1", "S6", "h-new");
        assertThrows(IllegalStateException.class, () -> tx.execute(s -> {
            assertEquals(2, rebinder.rebindSameSnapshot(107L, sf1));
            throw new IllegalStateException("激活事务后续步骤失败");
        }));
        assertEquals("p3g", buildOf(132)); assertEquals("p3g", buildOf(131));
    }
}
