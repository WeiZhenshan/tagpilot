package com.ruoyi.taglibrary.service;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/** 分析口径只读当前不可变发布快照；语义登记台的未发布修改不能改变单位或码值。 */
@Service
public class TsPublishedAnalysisCatalog {
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsSnapshotArtifactStore artifacts;
    @Autowired private ObjectMapper json;
    public Map<Long,JsonNode> tags(Long library,Set<Long> requested) {
        Map<Long,JsonNode> out=new LinkedHashMap<>();if(requested.isEmpty())return out;
        TsCatalogSnapshot snapshot=catalog.activeSnapshot(library);
        if(snapshot==null)throw new ServiceException("没有已发布的分析口径",409);
        Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(library,snapshot.getSnapshotId()));
        if(!eligible.containsAll(requested))throw new ServiceException("分析指标已下线或无权限",403);
        Map<Long,ObjectNode> codes=new HashMap<>();
        try {
            for(String line:Files.readAllLines(artifacts.verifiedPath(snapshot),StandardCharsets.UTF_8)) {
                if(line.trim().isEmpty())continue;JsonNode node=json.readTree(line);long tid=node.path("tag_id").asLong();
                if(!requested.contains(tid))continue;
                if("tag".equals(node.path("kind").asText()))out.put(tid,node);
                if("code_value".equals(node.path("kind").asText()))codes.computeIfAbsent(tid,k->json.createObjectNode()).put(node.path("code").asText(),node.path("label").asText());
            }
        }catch(ServiceException e){throw e;}catch(Exception e){throw new ServiceException("无法读取发布分析口径",409);}
        if(!out.keySet().containsAll(requested))throw new ServiceException("发布快照缺少分析指标",409);
        for(Map.Entry<Long,JsonNode> entry:out.entrySet())((ObjectNode)entry.getValue()).set("_code_labels",codes.getOrDefault(entry.getKey(),json.createObjectNode()));
        return out;
    }
}
