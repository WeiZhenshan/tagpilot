-- ----------------------------------------------------------------------------
-- V20260714_01 数据源表增加显示顺序列（拖拽排序支持）
-- 来源：ruoyi-databroker/src/main/resources/sql/databroker_migration_order_num.sql
-- 已改写为幂等形式（information_schema 守卫，可重复执行）
-- ----------------------------------------------------------------------------

set @has_col := (select count(*) from information_schema.columns
    where table_schema = database() and table_name = 'dp_datasource' and column_name = 'order_num');
set @ddl := if(@has_col = 0,
    'alter table dp_datasource add column order_num int(4) default 0 comment ''显示顺序'' after catalog_id',
    'select 1');
prepare stmt from @ddl; execute stmt; deallocate prepare stmt;
