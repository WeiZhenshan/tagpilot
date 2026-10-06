package com.ruoyi.taglibrary.service;

import java.sql.*;
import java.util.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.taglibrary.service.impl.TsCatalogRuntimeServiceImpl;
import org.mybatis.spring.*;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.core.io.*;
import org.springframework.jdbc.datasource.*;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;

/** 真实 Spring 事务代理 + 生产 XML；隔离 H2 验证构建、快照、客群共同提交/回滚与 MANDATORY。 */
class ActivationTransactionRegressionTest {
    Connection db;
    SimpleDriverDataSource ds;
    TlObjectGroupMapper groups;
    TsAudiencePlanRebinder rebinder;
    TsCatalogRuntimeServiceImpl service;
    TsRuntimeClient runtime;
    TsIndexMaintenanceService maintenance;

    @BeforeEach void setup() throws Exception {
        String url="jdbc:h2:mem:activation"+UUID.randomUUID()+";MODE=MySQL;DATABASE_TO_LOWER=TRUE";
        db=DriverManager.getConnection(url); ds=new SimpleDriverDataSource(new org.h2.Driver(),url);
        try(Statement st=db.createStatement()) {
            st.execute("create table tl_tag_library(library_id bigint primary key,del_flag char(1),library_name varchar); insert into tl_tag_library values(107,'0','test')");
            st.execute("create table ts_catalog_snapshot(snapshot_id varchar primary key,library_id bigint,snapshot_no int,tag_count int,concept_count int,alias_count int,code_value_count int,content_hash varchar,file_sha256 varchar,storage_uri varchar,schema_version int,status varchar,source_manifest varchar,quality_report varchar,publish_by varchar,publish_time timestamp,update_time timestamp)");
            st.execute("insert into ts_catalog_snapshot(snapshot_id,library_id,status,content_hash) values('S6',107,'ACTIVE','content')");
            st.execute("create table ts_index_build(build_id varchar primary key,snapshot_id varchar,status varchar,embedding_dim int,doc_count int,build_time timestamp,build_duration_ms bigint,doc_template_version varchar,analyzer_version varchar,embedding_model varchar,embedding_model_hash varchar,reranker_model varchar,reranker_model_hash varchar,retrieval_config_hash varchar,store_type varchar,milvus_collection varchar,milvus_alias varchar,artifact_uri varchar,artifact_hash varchar,doc_id_hash varchar,eval_summary varchar,create_time timestamp,update_time timestamp)");
            st.execute("insert into ts_index_build(build_id,snapshot_id,status,artifact_hash,doc_id_hash,store_type) values('old','S6','ACTIVE','old-h','ids','MILVUS'),('new','S6','READY','new-h','ids','MILVUS')");
            st.execute("create table tl_object_group(group_id bigint auto_increment primary key,group_name varchar,group_desc varchar,library_id bigint,rule_json clob,group_sql clob,user_count bigint,del_flag char(1),create_by varchar,create_time timestamp,update_by varchar,update_time timestamp,remark varchar)");
            for(int id: new int[]{131,132}) try(PreparedStatement p=db.prepareStatement("insert into tl_object_group(group_id,library_id,rule_json,del_flag) values(?,107,?,'0')")) {
                p.setInt(1,id);p.setString(2,TsAudiencePlanRebinderTest.group(id,"S6","old","old-h").getRuleJson());p.executeUpdate();
            }
        }
        SqlSessionFactoryBean factory=new SqlSessionFactoryBean();factory.setDataSource(ds);factory.setTypeAliases(TlObjectGroup.class);
        List<Resource> xmls=new ArrayList<>();
        for(String name: new String[]{"objectgroup/TlObjectGroupMapper","taglibrary/TsIndexBuildMapper","taglibrary/TsCatalogSnapshotMapper"}) {
            String xml=new String(org.springframework.util.StreamUtils.copyToByteArray(new ClassPathResource("mapper/"+name+".xml").getInputStream()),java.nio.charset.StandardCharsets.UTF_8).replace("sysdate()","current_timestamp");
            // H2 不支持 MySQL UPDATE JOIN；仅改测试方言，条件仍按库退休。
            xml=xml.replace("update ts_index_build b join ts_catalog_snapshot s on s.snapshot_id = b.snapshot_id\n        set b.status = 'RETIRED', b.update_time = current_timestamp\n        where s.library_id = #{libraryId} and b.status = 'ACTIVE'", "update ts_index_build set status='RETIRED',update_time=current_timestamp where status='ACTIVE' and snapshot_id in (select snapshot_id from ts_catalog_snapshot where library_id=#{libraryId})");
            xmls.add(new ByteArrayResource(xml.getBytes(java.nio.charset.StandardCharsets.UTF_8),name+".xml"));
        }
        factory.setMapperLocations(xmls.toArray(new Resource[0]));SqlSessionTemplate session=new SqlSessionTemplate(factory.getObject());
        groups=session.getMapper(TlObjectGroupMapper.class);
        TsAudiencePlanRebinder target=new TsAudiencePlanRebinder();ReflectionTestUtils.setField(target,"groups",groups);rebinder=proxy(target);
        TsCatalogRuntimeServiceImpl impl=new TsCatalogRuntimeServiceImpl();
        ReflectionTestUtils.setField(impl,"snapshotMapper",session.getMapper(TsCatalogSnapshotMapper.class));
        ReflectionTestUtils.setField(impl,"indexBuildMapper",session.getMapper(TsIndexBuildMapper.class));
        runtime=mock(TsRuntimeClient.class);maintenance=mock(TsIndexMaintenanceService.class);
        ReflectionTestUtils.setField(impl,"runtime",runtime);ReflectionTestUtils.setField(impl,"maintenance",maintenance);ReflectionTestUtils.setField(impl,"planRebinder",rebinder);
        when(runtime.get("/stats?build_id=new")).thenReturn(TsSnapshotAssembler.map("id_reconciled",true,"library_id",107,"snapshot_id","S6","build_id","new","content_hash","content","store_type","MILVUS","artifact_hash","new-h","doc_id_hash","ids"));
        service=proxy(impl);
    }
    @SuppressWarnings("unchecked") <T> T proxy(T target) {
        ProxyFactory p=new ProxyFactory(target);p.setProxyTargetClass(true);
        p.addAdvice(new TransactionInterceptor(new DataSourceTransactionManager(ds),new AnnotationTransactionAttributeSource()));return (T)p.getProxy();
    }
    @AfterEach void close() throws Exception {db.close();}
    String value(String sql) throws Exception {try(Statement s=db.createStatement();ResultSet rs=s.executeQuery(sql)){rs.next();return rs.getString(1);}}
    @Test void mandatoryProxyRejectsCallWithoutTransaction() {
        assertThrows(org.springframework.transaction.IllegalTransactionStateException.class,()->rebinder.rebindSameSnapshot(107L,TsAudiencePlanRebinderTest.build("new","S6","new-h")));
    }
    @Test void completeActivationCommitsAndRetryDoesNotActivateAgain() throws Exception {
        assertEquals("ACTIVE",service.activate("new").getStatus());
        assertEquals("ACTIVE",service.activate("new").getStatus());
        assertEquals("RETIRED",value("select status from ts_index_build where build_id='old'"));
        assertTrue(value("select rule_json from tl_object_group where group_id=132").contains("\"build_id\":\"new\""));
        verify(runtime,times(1)).post(eq("/activate"),any());
    }
    @Test void lostGroupWriteRollsBackAllRowsAndReconciles() throws Exception {
        // 第二个改绑失败：第一条客群与构建/快照写入都必须回滚。
        TlObjectGroupMapper failing=mock(TlObjectGroupMapper.class, i -> i.getMethod().invoke(groups, i.getArguments()));
        doAnswer(i->{TlObjectGroup g=i.getArgument(0);if(g.getGroupId()==132L)throw new ServiceException("test write failure");return groups.updateObjectGroup(g);}).when(failing).updateObjectGroup(any());
        TsAudiencePlanRebinder target=new TsAudiencePlanRebinder();ReflectionTestUtils.setField(target,"groups",failing);
        Object impl = org.springframework.test.util.AopTestUtils.getTargetObject(service);
        ReflectionTestUtils.setField(impl,"planRebinder",proxy(target));
        assertThrows(ServiceException.class,()->service.activate("new"));
        assertEquals("READY",value("select status from ts_index_build where build_id='new'"));assertEquals("ACTIVE",value("select status from ts_index_build where build_id='old'"));
        assertEquals("ACTIVE",value("select status from ts_catalog_snapshot where snapshot_id='S6'"));
        assertTrue(value("select rule_json from tl_object_group where group_id=131").contains("\"build_id\":\"old\""));
        verify(maintenance).reconcile(107L);
    }
    @Test void compensationFailurePreservesRollbackAndRaisesRecoveryAlert() throws Exception {
        when(runtime.post(eq("/activate"),any())).thenThrow(new ServiceException("test RPC timeout"));
        when(maintenance.reconcile(107L)).thenThrow(new ServiceException("test reconcile unavailable"));
        assertThrows(ServiceException.class,()->service.activate("new"));
        assertEquals("READY",value("select status from ts_index_build where build_id='new'"));verify(maintenance).reconcile(107L);
    }
    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={"library_id","snapshot_id","build_id","content_hash","store_type","artifact_hash","doc_id_hash"})
    void manifestMismatchNeverCallsActivation(String field) {
        Map<String,Object> stats=new HashMap<>(runtime.get("/stats?build_id=new"));stats.put(field,"wrong");when(runtime.get("/stats?build_id=new")).thenReturn(stats);
        assertThrows(ServiceException.class,()->service.activate("new"));verify(runtime,never()).post(anyString(),any());
    }
    com.ruoyi.objectgroup.service.impl.TlObjectGroupServiceImpl saveService() {
        com.ruoyi.objectgroup.service.impl.TlObjectGroupServiceImpl impl=new com.ruoyi.objectgroup.service.impl.TlObjectGroupServiceImpl();
        ReflectionTestUtils.setField(impl,"groupMapper",groups);
        ReflectionTestUtils.setField(impl,"objectMapper",new com.fasterxml.jackson.databind.ObjectMapper());
        com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper ext=mock(com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper.class);
        when(ext.selectDatasetIdByLibrary(107L)).thenReturn(null);
        ReflectionTestUtils.setField(impl,"extMapper",ext);
        return proxy(impl);
    }
    TlObjectGroup newGroup() {
        TlObjectGroup g=TsAudiencePlanRebinderTest.group(133,"S6","old","old-h");g.setGroupName("new cohort");
        g.setRuleJson(g.getRuleJson().replace("\"conditions\":[{\"tagId\":7,\"ratio\":0.406600}]","\"conditions\":[]"));return g;
    }
    void loginForTest() {
        com.ruoyi.common.core.domain.entity.SysUser u=new com.ruoyi.common.core.domain.entity.SysUser();u.setUserName("test-save");u.setUserId(2L);
        org.springframework.security.core.context.SecurityContextHolder.getContext().setAuthentication(new org.springframework.security.authentication.UsernamePasswordAuthenticationToken(new com.ruoyi.common.core.domain.model.LoginUser(u,new HashSet<String>()),null));
    }
    @Test void saveWithOldReadViewAfterActivationRejectsOldBinding() throws Exception {
        java.util.concurrent.CountDownLatch read=new java.util.concurrent.CountDownLatch(1),activated=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.ExecutorService pool=java.util.concurrent.Executors.newSingleThreadExecutor();
        com.ruoyi.objectgroup.service.impl.TlObjectGroupServiceImpl save=saveService();
        try {
            java.util.concurrent.Future<?> writer=pool.submit(()->new org.springframework.transaction.support.TransactionTemplate(new DataSourceTransactionManager(ds)).execute(t->{
                groups.selectObjectGroupList(new TlObjectGroup());read.countDown();
                try {assertTrue(activated.await(5,java.util.concurrent.TimeUnit.SECONDS));} catch(InterruptedException e){throw new RuntimeException(e);}
                assertThrows(ServiceException.class,()->save.insertObjectGroup(newGroup()));t.setRollbackOnly();return null;
            }));
            assertTrue(read.await(5,java.util.concurrent.TimeUnit.SECONDS));service.activate("new");activated.countDown();writer.get(5,java.util.concurrent.TimeUnit.SECONDS);
            assertEquals("2",value("select count(*) from tl_object_group"));
        } finally {activated.countDown();pool.shutdownNow();}
    }
    @Test void insertHoldingLibraryLockIsIncludedInWaitingActivation() throws Exception {
        java.util.concurrent.CountDownLatch locked=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.ExecutorService pool=java.util.concurrent.Executors.newFixedThreadPool(2);
        com.ruoyi.objectgroup.service.impl.TlObjectGroupServiceImpl save=saveService();
        try {
            java.util.concurrent.Future<?> writer=pool.submit(()->{
                loginForTest();
                try {return new org.springframework.transaction.support.TransactionTemplate(new DataSourceTransactionManager(ds)).execute(t->{
                    groups.lockLibrary(107L);locked.countDown();
                    try {assertTrue(release.await(5,java.util.concurrent.TimeUnit.SECONDS));}catch(InterruptedException e){throw new RuntimeException(e);}
                    return save.insertObjectGroup(newGroup());
                });} finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
            });
            assertTrue(locked.await(5,java.util.concurrent.TimeUnit.SECONDS));
            java.util.concurrent.Future<?> activation=pool.submit(()->service.activate("new"));
            // Future 不能在持锁保存前完成；超时充当屏障检查，非等待服务启动。
            assertThrows(java.util.concurrent.TimeoutException.class,()->activation.get(100,java.util.concurrent.TimeUnit.MILLISECONDS));
            release.countDown();writer.get(5,java.util.concurrent.TimeUnit.SECONDS);activation.get(5,java.util.concurrent.TimeUnit.SECONDS);
            assertEquals("3",value("select count(*) from tl_object_group"));
            assertTrue(value("select rule_json from tl_object_group where group_id=133").contains("\"build_id\":\"new\""));
        } finally {release.countDown();pool.shutdownNow();}
    }

    @Test void explicitNullExpectedAllowsFirstRuleButMissingExpectedDoesNot() throws Exception {
        db.createStatement().execute("update tl_object_group set rule_json=null where group_id=131");
        TlObjectGroup missing = new TlObjectGroup();missing.setGroupId(131L);missing.setRuleJson("{\"conditions\":[]}");
        assertEquals(0,groups.updateObjectGroup(missing));
        assertNull(value("select rule_json from tl_object_group where group_id=131"));
        loginForTest();
        try {
            missing.getParams().put("expectedRuleJson",null);
            assertEquals(1,saveService().updateObjectGroup(missing));
            assertEquals("{\"conditions\":[]}",value("select rule_json from tl_object_group where group_id=131"));
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void sameBuildStaleEditorCannotReplaceNewRuleAndMatchingEditorCanSave() throws Exception {
        String original=value("select rule_json from tl_object_group where group_id=131");
        String revised=original.replace("0.406600","0.500000");
        TlObjectGroup newer=new TlObjectGroup();newer.setGroupId(131L);newer.setRuleJson(revised);
        newer.getParams().put("expectedRuleJson",original);assertEquals(1,groups.updateObjectGroup(newer));
        TlObjectGroup stale=new TlObjectGroup();stale.setGroupId(131L);stale.setRuleJson(original);
        stale.getParams().put("expectedRuleJson",original);
        loginForTest();
        try {
            ServiceException failure=assertThrows(ServiceException.class,()->saveService().updateObjectGroup(stale));
            assertEquals(Integer.valueOf(409),failure.getCode());
            assertEquals(original,stale.getParams().get("expectedRuleJson"));
            assertEquals(revised,value("select rule_json from tl_object_group where group_id=131"));
            // 同一发布、匹配用户读版本的合法修改仍可保存。
            TlObjectGroup valid=newGroup();valid.setGroupId(131L);valid.getParams().put("expectedRuleJson",revised);
            assertEquals(1,saveService().updateObjectGroup(valid));
            assertEquals(valid.getRuleJson(),value("select rule_json from tl_object_group where group_id=131"));
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void serviceRejectsMissingExpectedButAllowsNameOnlyPatch() throws Exception {
        TlObjectGroup missing=newGroup();missing.setGroupId(131L);
        loginForTest();
        try {
            assertThrows(ServiceException.class,()->saveService().updateObjectGroup(missing));
            TlObjectGroup name=new TlObjectGroup();name.setGroupId(131L);name.setGroupName("新名称");
            String original=value("select rule_json from tl_object_group where group_id=131");
            assertEquals(1,saveService().updateObjectGroup(name));
            assertEquals(original,value("select rule_json from tl_object_group where group_id=131"));
            assertEquals("新名称",value("select group_name from tl_object_group where group_id=131"));
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void oldBuildEditorIsRejectedEvenWithMatchingCurrentRawText() throws Exception {
        String old=value("select rule_json from tl_object_group where group_id=131");
        service.activate("new");
        TlObjectGroup stale=newGroup();stale.setGroupId(131L);stale.setRuleJson(old);
        stale.getParams().put("expectedRuleJson",value("select rule_json from tl_object_group where group_id=131"));
        assertThrows(ServiceException.class,()->saveService().updateObjectGroup(stale));
        assertTrue(value("select rule_json from tl_object_group where group_id=131").contains("\"build_id\":\"new\""));
    }

}
