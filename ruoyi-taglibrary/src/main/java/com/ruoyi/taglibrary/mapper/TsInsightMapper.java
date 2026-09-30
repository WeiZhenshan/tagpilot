package com.ruoyi.taglibrary.mapper;
import java.util.*;
import org.apache.ibatis.annotations.*;
public interface TsInsightMapper {
 @Select("select library_id from tl_tag_library where library_id=#{library} for update")
 Long lockLibrary(@Param("library")Long library);
 @Select("select skill_id,version,pack_hash,status,definition_json,evaluation_json,create_by,review_by,publish_time from ts_insight_skill where library_id=#{library} order by skill_id,create_time desc")
 List<Map<String,Object>> list(@Param("library")Long library);
 @Select("select * from ts_insight_skill where library_id=#{library} and skill_id=#{id} and version=#{version} for update")
 Map<String,Object> version(@Param("library")Long library,@Param("id")String id,@Param("version")String version);
 @Insert("insert into ts_insight_skill(library_id,skill_id,version,pack_hash,definition_json,create_by) values(#{library},#{id},#{version},#{hash},#{definition},#{user})")
 int insert(@Param("library")Long library,@Param("id")String id,@Param("version")String version,@Param("hash")String hash,@Param("definition")String definition,@Param("user")String user);
 @Update("update ts_insight_skill set status='REVIEWED',evaluation_json=#{gate},review_by=#{user},review_time=now() where library_id=#{library} and skill_id=#{id} and version=#{version} and status='DRAFT'")
 int review(@Param("library")Long library,@Param("id")String id,@Param("version")String version,@Param("gate")String gate,@Param("user")String user);
 @Update("update ts_insight_skill set status='RETIRED' where library_id=#{library} and skill_id=#{id} and status='PUBLISHED'")
 int retire(@Param("library")Long library,@Param("id")String id);
 @Update("update ts_insight_skill set status='PUBLISHED',publish_by=#{user},publish_time=now() where library_id=#{library} and skill_id=#{id} and version=#{version} and status in ('REVIEWED','RETIRED')")
 int publish(@Param("library")Long library,@Param("id")String id,@Param("version")String version,@Param("user")String user);
 @Insert("insert into ts_insight_run(run_id,library_id,thread_id,owner_id,revision,plan_hash,status,payload_cipher,elapsed_ms) values(#{id},#{library},#{thread},#{owner},#{revision},#{hash},#{status},#{payload},#{elapsed})")
 int run(@Param("id")String id,@Param("library")Long library,@Param("thread")String thread,@Param("owner")Long owner,@Param("revision")Long revision,@Param("hash")String hash,@Param("status")String status,@Param("payload")String payload,@Param("elapsed")long elapsed);
 @Select("select * from ts_insight_run where run_id=#{id} and owner_id=#{owner}")
 Map<String,Object> ownedRun(@Param("id")String id,@Param("owner")Long owner);
 @Select("select r.run_id,r.thread_id,r.revision,r.status,r.elapsed_ms,r.create_time,f.rating,f.category,f.comment_text from ts_insight_run r left join ts_insight_feedback f on f.run_id=r.run_id and f.owner_id=r.owner_id where r.library_id=#{library} and r.owner_id=#{owner} order by r.create_time desc limit 100")
 List<Map<String,Object>> audit(@Param("library")Long library,@Param("owner")Long owner);
 @Insert("insert into ts_insight_feedback(run_id,owner_id,rating,category,comment_text) values(#{id},#{owner},#{rating},#{category},#{comment}) on duplicate key update rating=values(rating),category=values(category),comment_text=values(comment_text)")
 int feedback(@Param("id")String id,@Param("owner")Long owner,@Param("rating")int rating,@Param("category")String category,@Param("comment")String comment);
}
