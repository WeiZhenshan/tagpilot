package com.ruoyi.taglibrary.service;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.domain.dto.*;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.common.exception.ServiceException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class TsSemanticBasisGuard {
    @Autowired private ITsBootstrapService bootstrap;
    @Autowired private TlTagMapper tags;
    @Autowired private TsTagSemanticMapper semantics;
    public void verifyTag(TsTagSemantic semantic) { source(semantic); }
    @SuppressWarnings("unchecked")
    private Map<String, Map<String, Object>> source(TsTagSemantic semantic) {
        TlTag tag = tags.selectTagById(semantic.getTagId());
        if (tag == null) throw new ServiceException("标签不存在");
        BootstrapExportRequest request = new BootstrapExportRequest(); request.setLibraryId(tag.getLibraryId()); request.setTagIds(Collections.singletonList(tag.getTagId()));
        BootstrapExportResult freeze = bootstrap.exportFreeze(request);
        Map<String, Object> authority = null; List<Map<String, Object>> codes = new ArrayList<>();
        try {
            ObjectMapper json = new ObjectMapper();
            for (String line : freeze.getJsonl().split("\\n")) {
                Map<String, Object> row = json.readValue(line, Map.class);
                if ("tag".equals(row.get("kind"))) authority = row;
                if ("code_value".equals(row.get("kind"))) codes.add(row);
            }
        } catch (Exception e) { throw new ServiceException("无法校验复核依据"); }
        if (authority == null || !freeze.getIssues().isEmpty() || !Objects.equals(semantic.getBasisHash(), TsSnapshotAssembler.basisHash(authority, codes))) throw new ServiceException("复核依据已漂移，请重新冻结初始化并核实差异");
        Map<String, Map<String, Object>> byCode = new HashMap<>(); for (Map<String, Object> code : codes) byCode.put(String.valueOf(code.get("code")), code); return byCode;
    }
    public void verifyCode(TsCodeValueSemantic row) {
        TsTagSemantic tag = semantics.selectByTagId(row.getTagId());
        if (tag == null) throw new ServiceException("标签语义尚未初始化");
        Map<String, Object> code = source(tag).get(row.getCode());
        if (code == null || !Objects.equals(row.getBasisHash(), TsSnapshotAssembler.codeBasisHash(row.getTagId(), code, tag.getBasisHash()))) throw new ServiceException("码值复核依据已漂移");
    }
}
