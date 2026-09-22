package com.ruoyi.taglibrary.mapper;
import java.util.*;
import org.apache.ibatis.annotations.*;
import com.ruoyi.taglibrary.domain.TsAgentThread;

public interface TsAgentThreadMapper {
    String COLUMNS="thread_id as threadId,user_id as userId,library_id as libraryId,title,archived,pinned,row_version as rowVersion,create_time as createTime,update_time as updateTime";
    @Select("select "+COLUMNS+" from ts_agent_thread where user_id=#{uid} and archived=#{archived} order by pinned desc,update_time desc")
    List<TsAgentThread> list(@Param("uid") Long uid, @Param("archived") String archived);
    @Select("select "+COLUMNS+",payload from ts_agent_thread where thread_id=#{id} and user_id=#{uid} for update")
    TsAgentThread lock(@Param("id") String id, @Param("uid") Long uid);
    @Insert("insert into ts_agent_thread(thread_id,user_id,library_id,title,archived,pinned,row_version,payload) values(#{threadId},#{userId},#{libraryId},#{title},'0','0',0,#{payload})")
    int insert(TsAgentThread row);
    @Update("update ts_agent_thread set title=#{title},archived=#{archived},pinned=#{pinned},payload=#{payload},row_version=row_version+1,update_time=now() where thread_id=#{threadId} and user_id=#{userId} and row_version=#{rowVersion}")
    int update(TsAgentThread row);
    @Select("select execution_id,group_id,revision,plan_hash from ts_agent_execution where thread_id=#{id} and user_id=#{uid} and revision=#{rev}")
    Map<String,Object> execution(@Param("id") String id,@Param("uid") Long uid,@Param("rev") Long rev);
    @Insert("insert into ts_agent_execution(execution_id,thread_id,user_id,revision,plan_hash,group_id) values(#{eid},#{id},#{uid},#{rev},#{hash},#{gid})")
    int executionInsert(@Param("eid") String eid,@Param("id") String id,@Param("uid") Long uid,@Param("rev") Long rev,@Param("hash") String hash,@Param("gid") Long gid);
    @Delete("delete from ts_agent_execution where thread_id=#{id} and user_id=#{uid}")
    int deleteExecutions(@Param("id") String id,@Param("uid") Long uid);
    @Delete("delete from ts_agent_thread where thread_id=#{id} and user_id=#{uid} and row_version=#{version}")
    int deleteThread(@Param("id") String id,@Param("uid") Long uid,@Param("version") Long version);
}
