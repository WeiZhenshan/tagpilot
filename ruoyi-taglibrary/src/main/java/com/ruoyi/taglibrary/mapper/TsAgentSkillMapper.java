package com.ruoyi.taglibrary.mapper;

import java.util.*;
import org.apache.ibatis.annotations.*;

public interface TsAgentSkillMapper {
    @Select("select * from ts_agent_skill order by update_time desc, name")
    List<Map<String,Object>> list();
    @Select("select * from ts_agent_skill where name=#{name} for update")
    Map<String,Object> lock(String name);
    @Insert("insert into ts_agent_skill(name,draft_json,create_by,update_by) values(#{name},#{draft},#{user},#{user})")
    int insert(@Param("name") String name,@Param("draft") String draft,@Param("user") String user);
    @Update("update ts_agent_skill set draft_json=#{draft},row_version=row_version+1,update_by=#{user},update_time=now() where name=#{name} and row_version=#{revision}")
    int save(@Param("name") String name,@Param("draft") String draft,@Param("revision") long revision,@Param("user") String user);
    @Update("update ts_agent_skill set published_json=#{published},row_version=row_version+1,update_by=#{user},update_time=now(),publish_time=now() where name=#{name} and row_version=#{revision}")
    int publish(@Param("name") String name,@Param("published") String published,@Param("revision") long revision,@Param("user") String user);
    @Update("update ts_agent_skill set published_json=null,row_version=row_version+1,update_by=#{user},update_time=now() where name=#{name} and row_version=#{revision}")
    int retire(@Param("name") String name,@Param("revision") long revision,@Param("user") String user);
}
