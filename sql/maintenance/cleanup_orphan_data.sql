-- ============================================================================
-- 标签系统孤儿数据一次性清理脚本（对应《标签系统数据链路评估与优化方案》P0-6）
--
-- 背景：早期标签库删除不级联清理关联数据，导致以下存量孤儿：
--   1. tl_tag_library_dimension 指向已删除/不存在标签库的残留关系（阻塞维表删除）
--   2. tl_tag_code_value 归属库已删除/不存在（孤儿码值）
--   3. tl_object_group 关联库已删除但仍 del_flag='0'（孤儿对象群，运行时必然报错）
--   4. tl_object_group_import group_id IS NULL 且长期未保存的导入批次（上传即永久残留）
--
-- 使用要求：
--   * 仅在测试库执行并核对数量后再上测试生产库
--   * 每段均先提供"受影响行数预估"，确认无误后放开对应 DELETE
--   * 本脚本是历史数据修复，后续此类清理已由代码级联逻辑承接，勿重复定时执行
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 维表关系残留：relation 指向的标签库不存在或已逻辑删除
--    （删除保护只认"未删除库"，此类残留会永久阻塞维表删除）
-- ----------------------------------------------------------------------------
-- select count(*) from tl_tag_library_dimension r
-- left join tl_tag_library l on l.library_id = r.library_id
-- where l.library_id is null or l.del_flag <> '0';

-- delete r from tl_tag_library_dimension r
-- left join tl_tag_library l on l.library_id = r.library_id
-- where l.library_id is null or l.del_flag <> '0';

-- ----------------------------------------------------------------------------
-- 2. 孤儿码值：码值归属的标签库不存在或已逻辑删除
-- ----------------------------------------------------------------------------
-- select count(*) from tl_tag_code_value v
-- left join tl_tag_library l on l.library_id = v.library_id
-- where l.library_id is null or l.del_flag <> '0';

-- delete v from tl_tag_code_value v
-- left join tl_tag_library l on l.library_id = v.library_id
-- where l.library_id is null or l.del_flag <> '0';

-- ----------------------------------------------------------------------------
-- 3. 孤儿对象群：仍为存在态（del_flag='0'）但关联库已删除/不存在，
--    运行时会报"关联标签库的数据集不存在或未上线"。逻辑删除以留审计痕迹。
--    若需物理删除，改执行：delete from tl_object_group where ...（同条件）
-- ----------------------------------------------------------------------------
-- select count(*) from tl_object_group g
-- left join tl_tag_library l on l.library_id = g.library_id
-- where g.del_flag = '0' and (l.library_id is null or l.del_flag <> '0');

-- update tl_object_group g
-- left join tl_tag_library l on l.library_id = g.library_id
-- set g.del_flag = '2'
-- where g.del_flag = '0' and (l.library_id is null or l.del_flag <> '0');

-- ----------------------------------------------------------------------------
-- 4. 未保存的导入批次残留：group_id IS NULL 且创建超过 N 天（默认 1 天），
--    视为已放弃的上传。短于 N 天的不动，避免误删"上传后尚未保存"的在途批次。
--    时间窗可按需调整：INTERVAL 1 DAY
-- ----------------------------------------------------------------------------
-- select count(*) from tl_object_group_import
-- where group_id is null and create_time < date_sub(sysdate(), interval 1 day);

-- delete from tl_object_group_import
-- where group_id is null and create_time < date_sub(sysdate(), interval 1 day);
