-- Add order_num column for drag-and-drop reordering support
ALTER TABLE dp_datasource ADD COLUMN order_num INT(4) DEFAULT 0 COMMENT '显示顺序' AFTER catalog_id;
