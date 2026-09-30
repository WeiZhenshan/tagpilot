-- 演示对照客群：全量客户（资产结构基准）
--
-- 用途：客群资产结构透视演示的对比基准；技能运行时在「对照客群」下拉中选择它，
--       服务端会按同一批标签列对它重新编译取数，报告里出现「本客群 vs 全量客户」的差异。
-- 口径：全量客户 = 当前授权范围内的全部客户（SCOPE_ALL）；宽表 2,000 人，人数仅用于列表展示。
--
-- 何时执行：
--   * 竞赛全库快照 sql/seed/competition/tagpilot-competition-20260930.sql.gz 已含本对象群，无需再执行；
--   * 在导入其他/更新后的快照后重建，或对象群被删除后修复时执行本脚本。
-- 幂等：按「库 107 + 名称」判重，已存在则跳过；方案自动绑定执行时库内的 ACTIVE 快照与索引构建，
--       因此换快照后重建不会出现「对照客群与当前发布版本不一致」。
-- 执行（必须显式 utf8mb4，否则中文会双重编码）：
--   mysql --default-character-set=utf8mb4 -h127.0.0.1 -uroot -p ry < sql/seed/competition/demo-baseline-cohort.sql

INSERT INTO tl_object_group
    (group_name, group_desc, library_id, rule_json, group_sql, user_count, del_flag, create_by, create_time)
SELECT '全量客户（资产结构基准）',
       '资产结构分析对照基准：当前授权范围内的全部客户（演示数据，随库内 ACTIVE 发布版本自动绑定）',
       107,
       JSON_OBJECT(
         'schemaVersion', 4,
         'audiencePlan', JSON_OBJECT(
            'schema_version', 3,
            'plan_status', 'READY',
            'valid', TRUE,
            'revision', 1,
            'summary', '当前授权范围内的全部客户',
            'diagnostics', JSON_ARRAY(),
            'validation_errors', JSON_ARRAY(),
            'build_id', b.build_id,
            'snapshot_id', b.snapshot_id,
            'artifact_hash', b.artifact_hash,
            'intent_plan', JSON_OBJECT(
               'original_request', '全部客户（作为资产结构分析的对照基准）',
               'requirements', JSON_ARRAY(JSON_OBJECT(
                  'requirement_id', 'R1',
                  'source_spans', JSON_ARRAY('当前授权范围内的全部客户'),
                  'business_meaning', '当前授权范围内的全部客户',
                  'origin', 'USER')),
               'logic_tree', JSON_OBJECT('requirement_id', 'R1'),
               'assumptions', JSON_ARRAY()),
            'tree', JSON_OBJECT(
               'kind', 'SCOPE_ALL',
               'clause_id', 'R1',
               'requirement_ids', JSON_ARRAY('R1'),
               'status', 'BOUND',
               'source_span', '当前授权范围内的全部客户'))),
       NULL, 2000, '0', 'seed', NOW()
FROM (SELECT s.snapshot_id AS snapshot_id, i.build_id AS build_id, i.artifact_hash AS artifact_hash
        FROM ts_catalog_snapshot s
        JOIN ts_index_build i ON i.snapshot_id = s.snapshot_id AND i.status = 'ACTIVE'
       WHERE s.library_id = 107 AND s.status = 'ACTIVE'
       LIMIT 1) b
WHERE NOT EXISTS (SELECT 1 FROM (SELECT 1 FROM tl_object_group
       WHERE group_name = '全量客户（资产结构基准）' AND library_id = 107 AND del_flag = '0') existing);

-- 校验：应返回 1 行；snapshot_id / build_id 与库内 ACTIVE 一致，scope 为 SCOPE_ALL。
SELECT group_id, group_name, user_count,
       JSON_UNQUOTE(JSON_EXTRACT(rule_json, '$.audiencePlan.snapshot_id')) AS snapshot_id,
       JSON_UNQUOTE(JSON_EXTRACT(rule_json, '$.audiencePlan.build_id'))    AS build_id,
       JSON_UNQUOTE(JSON_EXTRACT(rule_json, '$.audiencePlan.tree.kind'))   AS scope
  FROM tl_object_group
 WHERE group_name = '全量客户（资产结构基准）' AND del_flag = '0';
