package com.ruoyi.taglibrary.service;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;
import com.ruoyi.common.exception.ServiceException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class TsSemanticChangeSetServiceTest {
    @Test void staleBaselineRejectsWithoutWriting() {
        JdbcTemplate jdbc=mock(JdbcTemplate.class);TsSemanticChangeSetService service=new TsSemanticChangeSetService();
        ReflectionTestUtils.setField(service,"jdbc",jdbc);
        Map<String,Object> pack=TsSnapshotAssembler.map("schema_version","semantic-changeset.v1","change_id","p3-test","library_id",107,"baseline_snapshot","old","baseline_hash","hash");
        when(jdbc.queryForList(anyString(),eq(107L))).thenReturn(Collections.singletonList(TsSnapshotAssembler.map("snapshot_id","new","content_hash","hash")));
        assertThrows(ServiceException.class,()->service.validate(pack));
        verify(jdbc,never()).update(anyString(),any(Object[].class));
    }
    @Test void reviewedPackageRequiredBeforeAnyDatabaseOperation() {
        JdbcTemplate jdbc=mock(JdbcTemplate.class);TsSemanticChangeSetService service=new TsSemanticChangeSetService();
        ReflectionTestUtils.setField(service,"jdbc",jdbc);
        assertThrows(ServiceException.class,()->service.apply(TsSnapshotAssembler.map("status","DRAFT")));
        verifyNoInteractions(jdbc);
    }
}
