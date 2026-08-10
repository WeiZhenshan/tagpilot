package com.ruoyi.databroker.service;

import java.util.List;
import java.util.Map;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.databroker.domain.DpDimensionTable;

/**
 * 维表管理 Service
 *
 * @author ruoyi
 */
public interface IDpDimensionService {

    /** 分页查询维表列表 */
    List<DpDimensionTable> selectDimensionList(DpDimensionTable query);

    /**
     * 查询维表详情
     * 返回 map：dimension（登记信息含数据源名称）、fieldChecks（六个标准列校验结果，
     * 连接失败时为 null）、checkError（连接失败原因，成功时为 null）
     */
    Map<String, Object> getDimensionDetail(Long dimensionId);

    /** 登记维表（校验唯一性、物理表与标准字段，同表已删除记录走恢复） */
    int insertDimension(DpDimensionTable dimension);

    /** 修改维表（仅允许修改维表名称和备注） */
    int updateDimension(DpDimensionTable dimension);

    /** 批量逻辑删除（被标签库关联则整个请求失败） */
    int deleteDimensionByIds(Long[] dimensionIds);

    /** 启用/停用（停用前校验标签库引用，启用前重新校验标准字段） */
    int updateStatus(Long dimensionId, String status);

    /** 可用数据连接下拉 */
    List<Map<String, Object>> listDatasourceOptions();

    /** 指定数据源下可登记的物理表下拉 */
    List<Map<String, Object>> listTableOptions(Long datasourceId);

    /** 新建弹窗标准字段预检（按物理表ID连接外部库校验六个标准列） */
    List<Map<String, Object>> checkTableFields(Long sourceTableId);

    /** 物理码值分页预览（外部 JDBC 手工分页） */
    TableDataInfo previewValues(Long dimensionId, Integer pageNum, Integer pageSize);
}
