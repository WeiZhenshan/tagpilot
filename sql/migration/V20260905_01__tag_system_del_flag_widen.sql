-- ----------------------------------------------------------------------------
-- V20260905_01 P0-5 逻辑删除唯一键冲突修复：del_flag 列拓宽迁移
-- 来源：sql/tag_system_del_flag_migration.sql（原文幂等，可重复执行）
-- 背景：uk(source_name, del_flag) / uk(dataset_code, del_flag) / uk(library_code, del_flag)
--       / uk(library_id, field_name, del_flag) 这类"业务键 + del_flag"复合唯一键，
--       在"删除 → 重建同名 → 再删除"循环中会出现两条 (code, '2') 记录，直接违反唯一键。
-- 方案：del_flag 由 char(1) 拓宽为 varchar(64)，逻辑删除时写入记录主键 ID 而非固定 '2'，
--       查询条件 del_flag = '0' 不受影响。
-- 执行时机：在升级应用代码之前执行（本脚本幂等，可重复执行）。
-- 对应代码：DpDataSourceMapper.xml / DpDatasetMapper.xml / TlTagLibraryMapper.xml
--           / TlTagMapper.xml 中逻辑删除语句均已改为写主键 ID（concat 主键 or 主键本身）。
-- ----------------------------------------------------------------------------

alter table dp_datasource  modify column del_flag varchar(64) default '0' comment '删除标志（0存在 其他=删除时的记录ID）';
alter table dp_dataset     modify column del_flag varchar(64) default '0' comment '删除标志（0存在 其他=删除时的记录ID）';
alter table tl_tag_library modify column del_flag varchar(64) default '0' comment '删除标志（0存在 其他=删除时的记录ID）';
alter table tl_tag         modify column del_flag varchar(64) default '0' comment '删除标志（0存在 其他=删除时的记录ID）';

-- 存量已删数据修正：把历史 '2' 改写为记录主键 ID，释放业务键以便重建同名记录
update dp_datasource  set del_flag = cast(datasource_id as char) where del_flag = '2';
update dp_dataset     set del_flag = cast(dataset_id    as char) where del_flag = '2';
update tl_tag_library set del_flag = cast(library_id    as char) where del_flag = '2';
update tl_tag         set del_flag = cast(tag_id        as char) where del_flag = '2';
