package com.ruoyi.taglibrary.service;

import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** P3 控制面：白名单字段、修改前内容校验和单事务落库；不接受 SQL。 */
@Service
public class TsSemanticChangeSetService {
    @Autowired private JdbcTemplate jdbc;
    @Autowired private ObjectMapper json;
    private static final Map<String,List<String>> FIELDS = new LinkedHashMap<>();
    static {
        FIELDS.put("ts_tag_semantic", Arrays.asList("tag_id","concept_id","family_key","caliber_struct","definition_long","semantic_type","unit","unit_scale","allowed_operators","semantic_version","source_ref"));
        FIELDS.put("ts_concept", Arrays.asList("concept_id","library_id","concept_code","concept_name","domain_dir_id","tag_object","definition","parent_id","status","source","source_ref"));
        FIELDS.put("ts_alias", Arrays.asList("target_type","target_id","alias_text","alias_norm","alias_type","weight","source","source_ref"));
        FIELDS.put("ts_tag_example", Arrays.asList("tag_id","example_type","utterance","expected_condition","source","source_ref"));
        FIELDS.put("ts_concept_tag_relation", Arrays.asList("library_id","concept_id","tag_id","relation_note","source_ref","version"));
        FIELDS.put("ts_business_term", Arrays.asList("term_id","term","term_norm","term_type","options","default_policy","applicable_semantic_types","tag_object","source_ref"));
    }
    private static final Map<String,List<String>> KEYS = new LinkedHashMap<>();
    static {
        KEYS.put("ts_tag_semantic", Arrays.asList("tag_id"));
        KEYS.put("ts_concept", Arrays.asList("concept_id"));
        KEYS.put("ts_alias", Arrays.asList("target_type","target_id","alias_norm"));
        KEYS.put("ts_tag_example", Arrays.asList("tag_id","example_type","utterance"));
        KEYS.put("ts_concept_tag_relation", Arrays.asList("library_id","concept_id","tag_id"));
        KEYS.put("ts_business_term", Arrays.asList("term_id"));
    }
    private Object normalized(String key,Object value) {
        if(value==null)return null;
        if(Arrays.asList("caliber_struct","allowed_operators","expected_condition","options").contains(key) && value instanceof String) {
            try{return json.readValue((String)value,Object.class);}catch(Exception e){throw new ServiceException("语义 JSON 格式错误");}
        }
        return value;
    }
    private String hash(Map<String,Object> row) {
        Map<String,Object> clean=new TreeMap<>();
        for(Map.Entry<String,Object> entry:row.entrySet())clean.put(entry.getKey(),normalized(entry.getKey(),entry.getValue()));
        return TsSnapshotCanonicalizer.sha256(TsSnapshotCanonicalizer.dumps(clean));
    }
    public List<Map<String,Object>> relations(Long library) {
        return jdbc.queryForList("select relation_id,library_id,concept_id,tag_id,relation_note,source_ref,review_status,version from ts_concept_tag_relation where library_id=? and review_status='REVIEWED' order by relation_id",library);
    }
    @Transactional(readOnly=true, isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Map<String,Object> validate(Map<String,Object> pack) { return inspect(pack,false); }

    @SuppressWarnings("unchecked")
    private Map<String,Object> inspect(Map<String,Object> pack,boolean lock) {
        if(!"semantic-changeset.v1".equals(pack.get("schema_version")))fail("变更包版本错误");
        if(!String.valueOf(pack.get("change_id")).matches("[A-Za-z0-9_-]{1,96}"))fail("变更包 ID 非法");
        Long library=Long.valueOf(String.valueOf(pack.get("library_id")));
        List<Map<String,Object>> snapshots=jdbc.queryForList("select snapshot_id,content_hash from ts_catalog_snapshot where library_id=? and status='ACTIVE'"+(lock?" for update":""),library);
        if(snapshots.size()!=1 || !Objects.equals(snapshots.get(0).get("snapshot_id"),pack.get("baseline_snapshot")) || !Objects.equals(snapshots.get(0).get("content_hash"),pack.get("baseline_hash")))fail("变更包基线已变化");
        for(String field:Arrays.asList("source_refs","source_case_ids","review_records"))if(!(pack.get(field) instanceof List) || ((List<?>)pack.get(field)).isEmpty())fail("缺少来源、开发案例或复核记录");
        List<Map<String,Object>> changes=(List<Map<String,Object>>)pack.get("changes");
        if(changes==null || changes.isEmpty() || changes.size()>500)fail("变更数量非法");
        Set<String> identities=new HashSet<>();
        Set<Long> newConcepts=new HashSet<>();
        for(Map<String,Object> c:changes)if("ts_concept".equals(c.get("table")))newConcepts.add(Long.valueOf(String.valueOf(((Map<?,?>)c.get("after")).get("concept_id"))));
        for(Map<String,Object> c:changes) {
            String table=String.valueOf(c.get("table"));
            Map<String,Object> key=(Map<String,Object>)c.get("key"),after=(Map<String,Object>)c.get("after");
            if(!FIELDS.containsKey(table) || key==null || after==null || !key.keySet().equals(new HashSet<>(KEYS.get(table))) || !FIELDS.get(table).containsAll(after.keySet()))fail("变更字段不在许可范围");
            if(!Objects.equals(new HashMap<>(key),subset(after,KEYS.get(table))))fail("变更不能修改标识");
            if(after.get("source_ref")==null || String.valueOf(after.get("source_ref")).trim().isEmpty())fail("变更必须逐条提供来源");
            if(!identities.add(table+TsSnapshotCanonicalizer.dumps(key)))fail("变更目标重复");
            String where=where(table);Object[] args=KEYS.get(table).stream().map(key::get).toArray();
            List<Map<String,Object>> rows=jdbc.queryForList("select "+String.join(",",FIELDS.get(table))+" from "+table+" where "+where+(lock?" for update":""),args);
            String before=rows.isEmpty()?null:hash(rows.get(0));
            if(rows.size()>1 || !Objects.equals(before,c.get("before_hash")))fail("修改前 hash 不一致，拒绝覆盖并发修改");
            if(table.equals("ts_tag_semantic") && rows.isEmpty())fail("只能更新已存在的标签语义");
            if(after.containsKey("library_id") && !library.equals(Long.valueOf(String.valueOf(after.get("library_id")))))fail("变更跨标签库");
            Long tid=null;
            if(after.containsKey("tag_id"))tid=Long.valueOf(String.valueOf(after.get("tag_id")));
            if(table.equals("ts_alias")) {
                if(!"TAG".equals(after.get("target_type")))fail("首期变更包只开放标签别名");
                tid=Long.valueOf(String.valueOf(after.get("target_id")));
                if(!Arrays.asList("FORMAL","COLLOQUIAL","ABBR","HISTORICAL","NEGATIVE").contains(after.get("alias_type")))fail("别名类型错误");
            }
            if(tid!=null && jdbc.queryForObject("select count(*) from tl_tag where tag_id=? and library_id=? and del_flag='0' and is_object_key='0'",Integer.class,tid,library)!=1)fail("标签不属于目标库或是对象键");
            if(after.containsKey("concept_id") && !table.equals("ts_concept")) {
                Long cid=Long.valueOf(String.valueOf(after.get("concept_id")));
                if(!newConcepts.contains(cid) && jdbc.queryForObject("select count(*) from ts_concept where concept_id=? and library_id=? and status='0' and review_status='REVIEWED'",Integer.class,cid,library)!=1)fail("候选关联或主概念引用非法");
            }
            c.put("validated_before_hash",before);
            c.put("before",rows.isEmpty()?null:rows.get(0));
        }
        return TsSnapshotAssembler.map("valid",true,"change_id",pack.get("change_id"),"changes",changes.size(),"writes",0);
    }
    private Map<String,Object> subset(Map<String,Object> row,List<String> keys) {Map<String,Object> result=new LinkedHashMap<>();for(String k:keys)result.put(k,row.get(k));return result;}
    private String where(String table) {List<String> out=new ArrayList<>();for(String key:KEYS.get(table))out.add(key+"=?");return String.join(" and ",out);}
    private void fail(String message){throw new ServiceException(message);}

    @Transactional
    @SuppressWarnings("unchecked")
    public Map<String,Object> apply(Map<String,Object> pack) throws Exception {
        if(!"REVIEWED".equals(pack.get("status")))fail("只允许应用已复核变更包");
        String packageHash=TsSnapshotCanonicalizer.sha256(TsSnapshotCanonicalizer.dumps(pack));
        List<Map<String,Object>> previous=jdbc.queryForList("select package_hash from ts_semantic_changeset where change_id=?",pack.get("change_id"));
        if(!previous.isEmpty()) {
            if(!packageHash.equals(previous.get(0).get("package_hash")))fail("已应用 ID 的内容不一致");
            return TsSnapshotAssembler.map("applied",false,"idempotent",true,"change_id",pack.get("change_id"));
        }
        inspect(pack,true);
        for(Map<String,Object> c:(List<Map<String,Object>>)pack.get("changes")) {
            String table=String.valueOf(c.get("table"));Map<String,Object> after=(Map<String,Object>)c.get("after"),key=(Map<String,Object>)c.get("key");
            List<String> fields=new ArrayList<>(after.keySet());List<Object> args=new ArrayList<>();
            for(String field:fields){Object value=after.get(field);args.add(value instanceof Map || value instanceof List?json.writeValueAsString(value):value);}
            if(c.get("before_hash")==null) {
                List<String> placeholders=new ArrayList<>(Collections.nCopies(fields.size(),"?"));
                jdbc.update("insert into "+table+" ("+String.join(",",fields)+",review_status) values ("+String.join(",",placeholders)+",'REVIEWED')",args.toArray());
            } else {
                List<String> setters=new ArrayList<>();for(String field:fields)setters.add(field+"=?");
                for(String field:KEYS.get(table))args.add(key.get(field));
                jdbc.update("update "+table+" set "+String.join(",",setters)+",review_status='REVIEWED' where "+where(table),args.toArray());
            }
        }
        // 保存输入与修改前后值；应用不发布、不激活，复用既有 Java 流程。
        jdbc.update("insert into ts_semantic_changeset(change_id,library_id,baseline_snapshot,package_hash,package_json,applied_by,applied_at) values(?,?,?,?,?,?,now())",
                    pack.get("change_id"),pack.get("library_id"),pack.get("baseline_snapshot"),packageHash,json.writeValueAsString(pack),SecurityUtils.getUsername());
        return TsSnapshotAssembler.map("applied",true,"change_id",pack.get("change_id"),"changes",((List<?>)pack.get("changes")).size());
    }
}
