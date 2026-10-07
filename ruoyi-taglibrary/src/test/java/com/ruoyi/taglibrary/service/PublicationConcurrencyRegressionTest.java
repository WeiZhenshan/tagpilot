package com.ruoyi.taglibrary.service;
import java.sql.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import org.apache.ibatis.session.*;
import org.mybatis.spring.*;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.core.io.ClassPathResource;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.objectgroup.mapper.*;
import com.ruoyi.objectgroup.domain.TlObjectGroup;

/** 发布回归：只在隔离 H2 使用生产映射，不操作业务数据库。 */
class PublicationConcurrencyRegressionTest {
 @Test void lockedCurrentReadDiscardsSessionCache() throws Exception {
  String url="jdbc:h2:mem:review"+UUID.randomUUID()+";MODE=MySQL;DATABASE_TO_LOWER=TRUE";
  try(Connection keeper=DriverManager.getConnection(url);Statement st=keeper.createStatement()) {
   st.execute("create table tl_tag_library(library_id bigint primary key,del_flag char(1) default '0')");st.execute("insert into tl_tag_library(library_id) values(107)");
   st.execute("create table ts_index_build(build_id varchar(48) primary key,snapshot_id varchar(40),status varchar(16),embedding_dim int,doc_count int,build_time timestamp,build_duration_ms bigint,"+
    "doc_template_version varchar,analyzer_version varchar,embedding_model varchar,embedding_model_hash varchar,reranker_model varchar,reranker_model_hash varchar,retrieval_config_hash varchar,"+
    "store_type varchar,milvus_collection varchar,milvus_alias varchar,artifact_uri varchar,artifact_hash varchar,doc_id_hash varchar,eval_summary varchar)");
   st.execute("insert into ts_index_build(build_id,snapshot_id,status) values('b1','S6','READY')");
   SimpleDriverDataSource ds=new SimpleDriverDataSource(new org.h2.Driver(),url);
   SqlSessionFactoryBean fb=new SqlSessionFactoryBean();fb.setDataSource(ds);
   fb.setMapperLocations(new ClassPathResource("mapper/taglibrary/TsIndexBuildMapper.xml"),new ClassPathResource("mapper/taglibrary/TsCatalogSnapshotMapper.xml"));
   SqlSessionTemplate session=new SqlSessionTemplate(fb.getObject());TsIndexBuildMapper builds=session.getMapper(TsIndexBuildMapper.class);TsCatalogSnapshotMapper snaps=session.getMapper(TsCatalogSnapshotMapper.class);
   new TransactionTemplate(new DataSourceTransactionManager(ds)).execute(s->{
    assertEquals("READY",builds.selectById("b1").getStatus());
    try(Connection other=DriverManager.getConnection(url);Statement os=other.createStatement()){os.executeUpdate("update ts_index_build set status='PURGED' where build_id='b1'");}catch(Exception e){throw new RuntimeException(e);}
    snaps.lockLibrary(107L);
    assertEquals("PURGED",builds.selectByIdForUpdate("b1").getStatus());
    return null;
   });
   try(ResultSet rs=st.executeQuery("select status from ts_index_build where build_id='b1'")){rs.next();assertEquals("PURGED",rs.getString(1));}
   System.out.println("REGRESSION: current read sees committed state after library lock.");
  }
 }
 @Test void staleWholeRowWriterCannotUndoCommittedRebind() throws Exception {
  String url="jdbc:h2:mem:review"+UUID.randomUUID()+";MODE=MySQL;DATABASE_TO_LOWER=TRUE";
  try(Connection keeper=DriverManager.getConnection(url);Statement st=keeper.createStatement()) {
   st.execute("create table tl_object_group(group_id bigint primary key, group_name varchar(64),group_desc varchar(500),library_id bigint,rule_json clob,group_sql clob,user_count bigint,del_flag char(1),create_by varchar,create_time timestamp,update_by varchar,update_time timestamp,remark varchar)");
   try(PreparedStatement ps=keeper.prepareStatement("insert into tl_object_group(group_id,library_id,rule_json,del_flag) values(132,107,?,'0')")){ps.setString(1,TsAudiencePlanRebinderTest.group(132,"S6","old","old-h").getRuleJson());ps.executeUpdate();}
   SimpleDriverDataSource ds=new SimpleDriverDataSource(new org.h2.Driver(),url);SqlSessionFactoryBean fb=new SqlSessionFactoryBean();fb.setDataSource(ds);fb.setTypeAliases(TlObjectGroup.class);
   String xml=new String(org.springframework.util.StreamUtils.copyToByteArray(new ClassPathResource("mapper/objectgroup/TlObjectGroupMapper.xml").getInputStream()),java.nio.charset.StandardCharsets.UTF_8).replace("sysdate()","current_timestamp");
   fb.setMapperLocations(new org.springframework.core.io.ByteArrayResource(xml.getBytes(java.nio.charset.StandardCharsets.UTF_8)));TlObjectGroupMapper mapper=new SqlSessionTemplate(fb.getObject()).getMapper(TlObjectGroupMapper.class);
   TsAudiencePlanRebinder rebinder=new TsAudiencePlanRebinder();org.springframework.test.util.ReflectionTestUtils.setField(rebinder,"groups",mapper);
   // 模拟通用保存请求在激活前已持有旧 rule_json，激活后才调用无 CAS 的更新映射。
   TlObjectGroup stale=TsAudiencePlanRebinderTest.group(132,"S6","old","old-h");
   new TransactionTemplate(new DataSourceTransactionManager(ds)).execute(s->rebinder.rebindSameSnapshot(107L,TsAudiencePlanRebinderTest.build("new","S6","new-h")));
   stale.getParams().put("expectedRuleJson", stale.getRuleJson());
   assertEquals(0,mapper.updateObjectGroup(stale));
   try(ResultSet rs=st.executeQuery("select rule_json from tl_object_group where group_id=132")){rs.next();assertTrue(rs.getString(1).contains("\"build_id\":\"new\""));}
   System.out.println("REGRESSION: production CAS rejected stale rule_json after committed rebind.");
  }
 }
}
