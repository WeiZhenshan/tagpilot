package com.ruoyi.taglibrary.service;

import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.mapper.TsAgentSkillMapper;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/** SKILL.md 是技能协议；展示名、分类、发布版本仅用于平台登记。 */
@Service
@SuppressWarnings("unchecked")
public class TsAgentSkillService {
    @Autowired private TsAgentSkillMapper mapper;
    @Autowired private ObjectMapper json;
    private Map<String,Object> decode(Object value) {
        try { return json.readValue(String.valueOf(value),Map.class); }
        catch(Exception e) { throw new ServiceException("技能内容无法读取"); }
    }
    private String encode(Object value) {
        try { return json.writeValueAsString(value); }
        catch(Exception e) { throw new ServiceException("技能格式错误"); }
    }
    private String text(Map<String,Object> body,String key,int max,boolean required) {
        Object raw=body.get(key);String value=raw instanceof String?((String)raw).trim():"";
        if(value.length()>max || required && value.isEmpty())throw new ServiceException(key+" 内容缺失或过长");
        return value;
    }
    public Map<String,Object> validate(Map<String,Object> body,boolean publish) {
        String name=text(body,"name",64,true);
        if(!name.matches("[a-z0-9]+(?:-[a-z0-9]+)*"))throw new ServiceException("技能名称只能包含小写字母、数字和单个连接符");
        if(name.contains("anthropic") || name.contains("claude") || Arrays.asList("synced","clear","compact","init","login","logout","config","settings","help","cost","context","exit","quit","model","permissions","add-dir","resume","rewind","mcp","plugin","plugins","agents","skills","memory","status","theme","doctor","feedback","bug","terminal-setup","hooks","output-style","plan").contains(name))throw new ServiceException("技能名称与平台保留词或内置命令冲突，请使用业务名称");
        Map<String,Object> out=map("name",name,"display_name",text(body,"display_name",100,true),"description",text(body,"description",1024,publish),
            "instructions",text(body,"instructions",60000,publish),"argument_hint",text(body,"argument_hint",200,false),
            "version",text(body,"version",24,true),"category",text(body,"category",24,true),
            "user_invocable",!Boolean.FALSE.equals(body.get("user_invocable")),"disable_model_invocation",Boolean.TRUE.equals(body.get("disable_model_invocation")));
        if(String.valueOf(out.get("description")).matches("(?s).*<[^>]+>.*"))throw new ServiceException("用途描述不能包含XML标签");
        if(!String.valueOf(out.get("version")).matches("\\d+\\.\\d+\\.\\d+"))throw new ServiceException("版本号须为三段数字");
        if(!Arrays.asList("fact","diagnosis","decision","chart","general").contains(out.get("category")))throw new ServiceException("技能分类非法");
        List<String> tools=new ArrayList<>();
        if(!(body.get("allowed_tools") instanceof List))throw new ServiceException("请登记允许的工具");
        for(Object tool:(List<?>)body.get("allowed_tools")) {
            if(!Arrays.asList("Read","Skill").contains(tool)||tools.contains(tool))throw new ServiceException("当前运行仅支持 Read 和 Skill 工具");
            tools.add(String.valueOf(tool));
        }
        if(publish && Boolean.FALSE.equals(out.get("user_invocable")) && Boolean.TRUE.equals(out.get("disable_model_invocation")))throw new ServiceException("至少开启一种技能调用方式");
        out.put("allowed_tools",tools);
        List<Map<String,Object>> resources=new ArrayList<>();Set<String> paths=new HashSet<>();int size=0;
        if(!(body.get("resources") instanceof List)||((List<?>)body.get("resources")).size()>30)throw new ServiceException("资源列表最多30项");
        for(Object raw:(List<?>)body.get("resources")) {
            if(!(raw instanceof Map))throw new ServiceException("资源格式错误");Map<String,Object> r=(Map<String,Object>)raw;
            String path=text(r,"path",200,true),content=text(r,"content",60000,true);
            if(!path.matches("(?:references|scripts|assets)/[A-Za-z0-9_./-]+") || path.contains("..") || path.contains("//") || path.endsWith("/") || !paths.add(path))throw new ServiceException("资源路径须位于 references、scripts 或 assets 下，且不能重复或越界");
            size+=content.length();resources.add(map("path",path,"content",content));
        }
        if(size>200000)throw new ServiceException("资源内容总计不能超过20万字");out.put("resources",resources);
        // 不支持命令预处理，避免发布内容在权限回调前执行 shell。
        if(markdown(out).matches("(?s).*![`]([^`]+)[`].*"))throw new ServiceException("当前不支持内嵌命令预处理，请改为文字指令");
        out.put("skill_md",markdown(out));return out;
    }
    public String markdown(Map<String,Object> body) {
        StringBuilder s=new StringBuilder("---\n");
        for(String key:Arrays.asList("name","description","argument_hint"))s.append(key.replace('_','-')).append(": ").append(encode(body.get(key))).append('\n');
        s.append("user-invocable: ").append(body.get("user_invocable")).append("\ndisable-model-invocation: ").append(body.get("disable_model_invocation"));
        s.append("\nallowed-tools: ").append(encode(body.get("allowed_tools"))).append("\n---\n\n").append(body.get("instructions")).append('\n');return s.toString();
    }
    public List<Map<String,Object>> list(boolean runtime) {
        List<Map<String,Object>> out=new ArrayList<>();
        for(Map<String,Object> row:mapper.list()) {
            if(runtime) { if(row.get("published_json")!=null) { Map<String,Object> p=decode(row.get("published_json"));p.remove("instructions");p.remove("resources");p.remove("skill_md");out.add(p); } }
            else { Map<String,Object> d=decode(row.get("draft_json"));d.putAll(map("row_version",row.get("row_version"),"update_time",row.get("update_time"),"published",row.get("published_json")==null?null:decode(row.get("published_json"))));out.add(d); }
        }return out;
    }
    public List<Map<String,Object>> published() {
        List<Map<String,Object>> out=new ArrayList<>();for(Map<String,Object> row:mapper.list())if(row.get("published_json")!=null)out.add(decode(row.get("published_json")));
        if(out.size()>60 || encode(out).length()>1000000)throw new ServiceException("发布技能总量超过单次运行加载上限");return out;
    }
    private long revision(Map<String,Object> body) { try{return Long.parseLong(String.valueOf(body.get("row_version")));}catch(Exception e){throw new ServiceException("缺少技能版本，请刷新");} }
    @Transactional public void save(Map<String,Object> body) {
        Map<String,Object> draft=validate(body,false);String name=String.valueOf(draft.get("name"));Map<String,Object> row=mapper.lock(name);
        if(row==null) { if(revision(body)!=0)throw new ServiceException("技能已变化，请刷新",409);
            try{mapper.insert(name,encode(draft),SecurityUtils.getUsername());}catch(org.springframework.dao.DuplicateKeyException e){throw new ServiceException("技能名称已存在，请刷新",409);} }
        else if(mapper.save(name,encode(draft),revision(body),SecurityUtils.getUsername())!=1)throw new ServiceException("技能已被其他页面修改，请刷新",409);
    }
    @Transactional public void publish(String name,Map<String,Object> body) {
        Map<String,Object> row=mapper.lock(name);if(row==null)throw new ServiceException("技能不存在",404);
        Map<String,Object> draft=validate(decode(row.get("draft_json")),true);
        if(row.get("published_json")!=null) { Map<String,Object> previous=decode(row.get("published_json"));if(previous.get("version").equals(draft.get("version")))throw new ServiceException("编辑发布内容后须使用新版本号"); }
        if(mapper.publish(name,encode(draft),revision(body),SecurityUtils.getUsername())!=1)throw new ServiceException("技能已变化，请刷新",409);
    }
    @Transactional public void retire(String name,Map<String,Object> body) {
        if(mapper.retire(name,revision(body),SecurityUtils.getUsername())!=1)throw new ServiceException("技能已变化，请刷新",409);
    }
}
