-- 洞察Skill不可变版本、运行审计和反馈。仅登记草稿，不自动绑定/复核/发布。
CREATE TABLE IF NOT EXISTS ts_insight_skill (
 library_id BIGINT NOT NULL, skill_id VARCHAR(80) NOT NULL, version VARCHAR(24) NOT NULL,
 pack_hash CHAR(64) NOT NULL, definition_json LONGTEXT NOT NULL, evaluation_json LONGTEXT,
 status VARCHAR(16) NOT NULL DEFAULT 'DRAFT', create_by VARCHAR(64) NOT NULL,
 create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, review_by VARCHAR(64), review_time DATETIME,
 publish_by VARCHAR(64), publish_time DATETIME,
 PRIMARY KEY(library_id,skill_id,version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ts_insight_run (
 run_id VARCHAR(64) NOT NULL PRIMARY KEY, library_id BIGINT NOT NULL, thread_id VARCHAR(64) NOT NULL,
 owner_id BIGINT NOT NULL, revision BIGINT NOT NULL, plan_hash CHAR(64) NOT NULL,
 status VARCHAR(24) NOT NULL, payload_cipher LONGTEXT NOT NULL, elapsed_ms BIGINT NOT NULL DEFAULT 0,
 create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX ix_insight_owner(owner_id,thread_id,create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ts_insight_feedback (
 feedback_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, run_id VARCHAR(64) NOT NULL,
 owner_id BIGINT NOT NULL, rating INT NOT NULL, category VARCHAR(24) NOT NULL,
 comment_text VARCHAR(500) NOT NULL, create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_insight_feedback(run_id,owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- 按既有标签管理目录登记，菜单迁移幂等，不为角色自动授予新权限。
INSERT INTO sys_menu (menu_name,parent_id,order_num,path,component,is_frame,is_cache,menu_type,visible,status,perms,icon,create_by,create_time)
SELECT '洞察技能',m.menu_id,9,'insight-skill','taglibrary/insight-skill/index',1,0,'C','0','0','taglibrary:insight:list','chart','admin',NOW()
FROM sys_menu m WHERE m.path='taglibrary' AND m.menu_type='M'
AND NOT EXISTS (SELECT 1 FROM sys_menu WHERE perms='taglibrary:insight:list');
INSERT INTO sys_menu (menu_name,parent_id,order_num,path,is_frame,is_cache,menu_type,visible,status,perms,icon,create_by,create_time)
SELECT p.label,m.menu_id,p.ord,'#',1,0,'F','0','0',p.permission,'#','admin',NOW()
FROM sys_menu m JOIN (
 SELECT '运行洞察' label,1 ord,'taglibrary:insight:run' permission UNION ALL
 SELECT '编辑技能',2,'taglibrary:insight:edit' UNION ALL
 SELECT '复核技能',3,'taglibrary:insight:review' UNION ALL
 SELECT '发布技能',4,'taglibrary:insight:publish'
) p WHERE m.perms='taglibrary:insight:list'
AND NOT EXISTS (SELECT 1 FROM sys_menu s WHERE s.perms=p.permission);
