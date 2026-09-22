package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.*;

public interface TsAgentCapabilityMapper {
    @Select("select definition_json from ts_agent_capability c where library_id=#{library} and review_status='REVIEWED' and version=(select max(version) from ts_agent_capability v where v.library_id=c.library_id and v.capability_id=c.capability_id and v.review_status='REVIEWED') order by capability_id")
    List<String> reviewed(@Param("library") Long library);
    @Select("select definition_json from ts_agent_capability where library_id=#{library} and capability_id=#{id} and version=#{version}")
    String definition(@Param("library") Long library,@Param("id") String id,@Param("version") Integer version);
    @Insert("insert into ts_agent_capability(library_id,capability_id,version,definition_json,create_by) values(#{library},#{id},#{version},#{definition},#{user})")
    int insert(@Param("library") Long library,@Param("id") String id,@Param("version") Integer version,@Param("definition") String definition,@Param("user") String user);
    @Update("update ts_agent_capability set review_status='REVIEWED',review_by=#{user},review_time=now() where library_id=#{library} and capability_id=#{id} and version=#{version} and review_status='DRAFT'")
    int review(@Param("library") Long library,@Param("id") String id,@Param("version") Integer version,@Param("user") String user);
}
