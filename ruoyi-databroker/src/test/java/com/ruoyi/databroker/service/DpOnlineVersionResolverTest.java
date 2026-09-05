package com.ruoyi.databroker.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.mapper.DpDatasetFieldMapper;
import com.ruoyi.databroker.mapper.DpDatasetVersionMapper;

/**
 * 在线版本共用解析服务单元测试（纯Mockito，不起Spring上下文）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
public class DpOnlineVersionResolverTest {

    private static final Long DATASET_ID = 4L;

    @Mock
    private DpDatasetVersionMapper versionMapper;
    @Mock
    private DpDatasetFieldMapper fieldMapper;

    @InjectMocks
    private DpOnlineVersionResolver resolver;

    /** 默认版本在线：选默认版本，原因为“默认在线版本” */
    @Test
    public void 解析_默认版本在线_选默认版本() {
        when(versionMapper.selectResolvedOnlineVersion(DATASET_ID))
                .thenReturn(buildVersion(7L, 2, true));

        DpResolvedVersion version = resolver.resolve(DATASET_ID);

        assertEquals(7L, version.getVersionId());
        assertEquals(Integer.valueOf(2), version.getVersionNo());
        assertEquals(Boolean.TRUE, version.getIsDefault());
        assertEquals(DpOnlineVersionResolver.REASON_DEFAULT, version.getReason());
    }

    /** 默认版本已下线：回退版本号最大的 ONLINE 版本，原因标注回退 */
    @Test
    public void 解析_默认版本下线_回退最大版本号() {
        when(versionMapper.selectResolvedOnlineVersion(DATASET_ID))
                .thenReturn(buildVersion(11L, 4, false));

        DpResolvedVersion version = resolver.resolve(DATASET_ID);

        assertEquals(11L, version.getVersionId());
        assertEquals(Integer.valueOf(4), version.getVersionNo());
        assertEquals(Boolean.FALSE, version.getIsDefault());
        assertEquals(DpOnlineVersionResolver.REASON_FALLBACK, version.getReason());
    }

    /** 无在线版本或数据集不存在：返回 null 由调用方报错 */
    @Test
    public void 解析_无在线版本_返回null() {
        when(versionMapper.selectResolvedOnlineVersion(DATASET_ID)).thenReturn(null);

        assertNull(resolver.resolve(DATASET_ID));
    }

    /** 数据集ID为空：直接返回 null，不查库 */
    @Test
    public void 解析_数据集ID为空_返回null() {
        assertNull(resolver.resolve(null));
    }

    /** 启用字段查询：按版本ID透传组装结果 */
    @Test
    public void 字段查询_按版本透传() {
        DpResolvedField field = new DpResolvedField();
        field.setFieldId(1L);
        field.setFieldAlias("cust_no");
        field.setFieldName("cust_no");
        field.setDataType("varchar");
        field.setIsPk("1");
        field.setTableName("indiv_cust");
        field.setDatasourceId(101L);
        when(fieldMapper.selectEnabledResolvedFields(7L)).thenReturn(Collections.singletonList(field));

        List<DpResolvedField> fields = resolver.listEnabledFields(7L);

        assertEquals(1, fields.size());
        assertEquals("cust_no", fields.get(0).getFieldAlias());
        assertEquals("indiv_cust", fields.get(0).getTableName());
        assertEquals(101L, fields.get(0).getDatasourceId());
        verify(fieldMapper).selectEnabledResolvedFields(7L);
    }

    private DpResolvedVersion buildVersion(Long versionId, int versionNo, boolean isDefault) {
        DpResolvedVersion version = new DpResolvedVersion();
        version.setDatasetId(DATASET_ID);
        version.setVersionId(versionId);
        version.setVersionNo(versionNo);
        version.setVersionName("V" + versionNo);
        version.setIsDefault(isDefault);
        return version;
    }
}
