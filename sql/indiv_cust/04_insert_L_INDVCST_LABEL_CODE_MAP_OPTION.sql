-- ============================================================================
-- L_INDVCST_LABEL_CODE_MAP  码值初始化 —— 选项型字段（第 1 批）
-- 目标库    : indiv_cust  （先执行 02_create_L_INDVCST_LABEL_CODE_MAP.sql）
-- 覆盖范围  : 本批 42 个选项型字段，共 195 条码值
-- 编码规范  : 分类型用短字母码（M/F、NORMAL/FROZEN）；有序分档用前导零数字码（01/02/…），
--             与既有码表 tag_code 注释「码值（字符串，保留前导零）」一致
-- 码值来源  : 复用既有系统码值 3 个字段（GENDER / CUR_CUST_LEVEL / HIST_MAX_CUST_LEVEL 等）；
--             其余按银行零售客户经营业务语义设计，逐段标注依据，标 ★推定 的为推断值
-- 机构类字段: 开户/管户一级・二级・三级机构 共 6 个字段的码值见 05_..._BRANCH.sql（真实联行号）
-- 幂等性    : ON DUPLICATE KEY UPDATE，可重复执行（需 MySQL 8.0.19+，当前实例 8.0.46）
-- 本文件仅生成，未在数据库中执行。
-- ============================================================================

INSERT INTO `indiv_cust`.`L_INDVCST_LABEL_CODE_MAP`
  (`tag_name_en`, `tag_code`, `tag_name_cn`, `code_definition`, `code_sort`, `last_update_time`)
VALUES
  -- 性别（复用既有系统码值）
  ('GENDER', 'M', '性别', '男', 1, '2026-09-15 00:00:00'),
  ('GENDER', 'F', '性别', '女', 2, '2026-09-15 00:00:00'),
  -- 证件类型（★推定：按人民银行联网核查证件类型口径设计）
  ('ID_TYPE', 'ID_CARD', '证件类型', '身份证', 1, '2026-09-15 00:00:00'),
  ('ID_TYPE', 'PASSPORT', '证件类型', '护照', 2, '2026-09-15 00:00:00'),
  ('ID_TYPE', 'HK_MO_TW', '证件类型', '港澳台居民居住证', 3, '2026-09-15 00:00:00'),
  ('ID_TYPE', 'FOREIGNER', '证件类型', '外国人永久居留证', 4, '2026-09-15 00:00:00'),
  ('ID_TYPE', 'MILITARY', '证件类型', '军官证', 5, '2026-09-15 00:00:00'),
  ('ID_TYPE', 'OTHER', '证件类型', '其他', 6, '2026-09-15 00:00:00'),
  -- 行外资产(万元)(KYC)（★推定：行外资产分档，与私银/运营/万元口径统一）
  ('OUTSIDE_ASSET_WAN_KYC', '01', '行外资产(万元)(KYC)', '50万以下', 1, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_WAN_KYC', '02', '行外资产(万元)(KYC)', '50万(含)-100万', 2, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_WAN_KYC', '03', '行外资产(万元)(KYC)', '100万(含)-300万', 3, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_WAN_KYC', '04', '行外资产(万元)(KYC)', '300万(含)-600万', 4, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_WAN_KYC', '05', '行外资产(万元)(KYC)', '600万(含)-1000万', 5, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_WAN_KYC', '06', '行外资产(万元)(KYC)', '1000万及以上', 6, '2026-09-15 00:00:00'),
  -- 行外资产（运营KYC）（★推定：同上，三口径统一便于横向对比）
  ('OUTSIDE_ASSET_OPS_KYC', '01', '行外资产（运营KYC）', '50万以下', 1, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_OPS_KYC', '02', '行外资产（运营KYC）', '50万(含)-100万', 2, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_OPS_KYC', '03', '行外资产（运营KYC）', '100万(含)-300万', 3, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_OPS_KYC', '04', '行外资产（运营KYC）', '300万(含)-600万', 4, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_OPS_KYC', '05', '行外资产（运营KYC）', '600万(含)-1000万', 5, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_OPS_KYC', '06', '行外资产（运营KYC）', '1000万及以上', 6, '2026-09-15 00:00:00'),
  -- 行外资产（私银KYC）（★推定：同上）
  ('OUTSIDE_ASSET_PB_KYC', '01', '行外资产（私银KYC）', '50万以下', 1, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_PB_KYC', '02', '行外资产（私银KYC）', '50万(含)-100万', 2, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_PB_KYC', '03', '行外资产（私银KYC）', '100万(含)-300万', 3, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_PB_KYC', '04', '行外资产（私银KYC）', '300万(含)-600万', 4, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_PB_KYC', '05', '行外资产（私银KYC）', '600万(含)-1000万', 5, '2026-09-15 00:00:00'),
  ('OUTSIDE_ASSET_PB_KYC', '06', '行外资产（私银KYC）', '1000万及以上', 6, '2026-09-15 00:00:00'),
  -- 家庭年收入（私银KYC）（★推定：家庭年收入分档）
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '01', '家庭年收入（私银KYC）', '20万以下', 1, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '02', '家庭年收入（私银KYC）', '20万(含)-50万', 2, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '03', '家庭年收入（私银KYC）', '50万(含)-100万', 3, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '04', '家庭年收入（私银KYC）', '100万(含)-300万', 4, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '05', '家庭年收入（私银KYC）', '300万(含)-500万', 5, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_ANNUAL_INCOME_PB_KYC', '06', '家庭年收入（私银KYC）', '500万及以上', 6, '2026-09-15 00:00:00'),
  -- 当前APP设备类型（★推定：APP 设备类型）
  ('CUR_APP_DEVICE_TYPE', 'IOS', '当前APP设备类型', '苹果 iOS', 1, '2026-09-15 00:00:00'),
  ('CUR_APP_DEVICE_TYPE', 'ANDROID', '当前APP设备类型', '安卓 Android', 2, '2026-09-15 00:00:00'),
  ('CUR_APP_DEVICE_TYPE', 'HARMONY', '当前APP设备类型', '鸿蒙 HarmonyOS', 3, '2026-09-15 00:00:00'),
  ('CUR_APP_DEVICE_TYPE', 'OTHER', '当前APP设备类型', '其他', 4, '2026-09-15 00:00:00'),
  -- 最高学历（★推定：国民教育序列学历）
  ('HIGHEST_EDUCATION', '01', '最高学历', '初中及以下', 1, '2026-09-15 00:00:00'),
  ('HIGHEST_EDUCATION', '02', '最高学历', '高中/中专', 2, '2026-09-15 00:00:00'),
  ('HIGHEST_EDUCATION', '03', '最高学历', '大专', 3, '2026-09-15 00:00:00'),
  ('HIGHEST_EDUCATION', '04', '最高学历', '本科', 4, '2026-09-15 00:00:00'),
  ('HIGHEST_EDUCATION', '05', '最高学历', '硕士', 5, '2026-09-15 00:00:00'),
  ('HIGHEST_EDUCATION', '06', '最高学历', '博士', 6, '2026-09-15 00:00:00'),
  -- 上12个月最高客户等级（复用既有系统码值）
  ('PREV_12_MONTHS_MAX_CUST_LEVEL', 'A', '上12个月最高客户等级', 'A级客户', 1, '2026-09-15 00:00:00'),
  ('PREV_12_MONTHS_MAX_CUST_LEVEL', 'B', '上12个月最高客户等级', 'B级客户', 2, '2026-09-15 00:00:00'),
  ('PREV_12_MONTHS_MAX_CUST_LEVEL', 'C', '上12个月最高客户等级', 'C级客户', 3, '2026-09-15 00:00:00'),
  -- 当前潜力资产等级（规则预测）（★推定：潜力资产等级，沿用资产分档）
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '01', '当前潜力资产等级（规则预测）', '50万以下', 1, '2026-09-15 00:00:00'),
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '02', '当前潜力资产等级（规则预测）', '50万(含)-100万', 2, '2026-09-15 00:00:00'),
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '03', '当前潜力资产等级（规则预测）', '100万(含)-300万', 3, '2026-09-15 00:00:00'),
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '04', '当前潜力资产等级（规则预测）', '300万(含)-600万', 4, '2026-09-15 00:00:00'),
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '05', '当前潜力资产等级（规则预测）', '600万(含)-1000万', 5, '2026-09-15 00:00:00'),
  ('CUR_ASSET_POTENTIAL_LEVEL_RULE_PREDICTION', '06', '当前潜力资产等级（规则预测）', '1000万及以上', 6, '2026-09-15 00:00:00'),
  -- 历史最高客户等级（复用既有系统码值）
  ('HIST_MAX_CUST_LEVEL', 'A', '历史最高客户等级', 'A级客户', 1, '2026-09-15 00:00:00'),
  ('HIST_MAX_CUST_LEVEL', 'B', '历史最高客户等级', 'B级客户', 2, '2026-09-15 00:00:00'),
  ('HIST_MAX_CUST_LEVEL', 'C', '历史最高客户等级', 'C级客户', 3, '2026-09-15 00:00:00'),
  -- 当前客户潜力等级（财富价值潜力模型）（★推定：潜力模型 5 档）
  ('CUR_CUST_POTENTIAL_LEVEL_WEALTH_VALUE_POTENTIAL_MODEL', '01', '当前客户潜力等级（财富价值潜力模型）', '极低', 1, '2026-09-15 00:00:00'),
  ('CUR_CUST_POTENTIAL_LEVEL_WEALTH_VALUE_POTENTIAL_MODEL', '02', '当前客户潜力等级（财富价值潜力模型）', '较低', 2, '2026-09-15 00:00:00'),
  ('CUR_CUST_POTENTIAL_LEVEL_WEALTH_VALUE_POTENTIAL_MODEL', '03', '当前客户潜力等级（财富价值潜力模型）', '中等', 3, '2026-09-15 00:00:00'),
  ('CUR_CUST_POTENTIAL_LEVEL_WEALTH_VALUE_POTENTIAL_MODEL', '04', '当前客户潜力等级（财富价值潜力模型）', '较高', 4, '2026-09-15 00:00:00'),
  ('CUR_CUST_POTENTIAL_LEVEL_WEALTH_VALUE_POTENTIAL_MODEL', '05', '当前客户潜力等级（财富价值潜力模型）', '极高', 5, '2026-09-15 00:00:00'),
  -- 当前私银客户类型（★推定：私银客群分层）
  ('CUR_PB_CUST_TYPE', 'PB_STD', '当前私银客户类型', '私银标准客户', 1, '2026-09-15 00:00:00'),
  ('CUR_PB_CUST_TYPE', 'PB_ULTRA', '当前私银客户类型', '私银超高净值客户', 2, '2026-09-15 00:00:00'),
  ('CUR_PB_CUST_TYPE', 'PB_FAMILY', '当前私银客户类型', '私银家族客户', 3, '2026-09-15 00:00:00'),
  -- 当前客户等级（复用既有系统码值）
  ('CUR_CUST_LEVEL', 'A', '当前客户等级', 'A级客户', 1, '2026-09-15 00:00:00'),
  ('CUR_CUST_LEVEL', 'B', '当前客户等级', 'B级客户', 2, '2026-09-15 00:00:00'),
  ('CUR_CUST_LEVEL', 'C', '当前客户等级', 'C级客户', 3, '2026-09-15 00:00:00'),
  -- 上月末私银主账户生客熟客忠诚客分类（★推定：生客/熟客/忠诚客三分）
  ('LAST_MONTH_END_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'NEW', '上月末私银主账户生客熟客忠诚客分类', '生客', 1, '2026-09-15 00:00:00'),
  ('LAST_MONTH_END_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'REPEAT', '上月末私银主账户生客熟客忠诚客分类', '熟客', 2, '2026-09-15 00:00:00'),
  ('LAST_MONTH_END_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'LOYAL', '上月末私银主账户生客熟客忠诚客分类', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 当前财富生客熟客忠诚客分类（★推定：同上）
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'NEW', '当前财富生客熟客忠诚客分类', '生客', 1, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'REPEAT', '当前财富生客熟客忠诚客分类', '熟客', 2, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'LOYAL', '当前财富生客熟客忠诚客分类', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 当前尊享会员等级（★推定：尊享会员 7 级）
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '01', '当前尊享会员等级', 'V1', 1, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '02', '当前尊享会员等级', 'V2', 2, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '03', '当前尊享会员等级', 'V3', 3, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '04', '当前尊享会员等级', 'V4', 4, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '05', '当前尊享会员等级', 'V5', 5, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '06', '当前尊享会员等级', 'V6', 6, '2026-09-15 00:00:00'),
  ('CUR_EXCLUSIVE_MEMBER_LEVEL', '07', '当前尊享会员等级', 'V7', 7, '2026-09-15 00:00:00'),
  -- 上年末财富生客熟客忠诚客分类（★推定：同上）
  ('LAST_YEAR_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'NEW', '上年末财富生客熟客忠诚客分类', '生客', 1, '2026-09-15 00:00:00'),
  ('LAST_YEAR_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'REPEAT', '上年末财富生客熟客忠诚客分类', '熟客', 2, '2026-09-15 00:00:00'),
  ('LAST_YEAR_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'LOYAL', '上年末财富生客熟客忠诚客分类', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 上月末财富生客熟客忠诚客分类（★推定：同上）
  ('LAST_MONTH_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'NEW', '上月末财富生客熟客忠诚客分类', '生客', 1, '2026-09-15 00:00:00'),
  ('LAST_MONTH_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'REPEAT', '上月末财富生客熟客忠诚客分类', '熟客', 2, '2026-09-15 00:00:00'),
  ('LAST_MONTH_END_WEALTH_NEW_REPEAT_LOYAL_CLASS', 'LOYAL', '上月末财富生客熟客忠诚客分类', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 当前私银主账户生客熟客忠诚客分类（★推定：同上）
  ('CUR_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'NEW', '当前私银主账户生客熟客忠诚客分类', '生客', 1, '2026-09-15 00:00:00'),
  ('CUR_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'REPEAT', '当前私银主账户生客熟客忠诚客分类', '熟客', 2, '2026-09-15 00:00:00'),
  ('CUR_PB_MAIN_ACCT_NEW_REPEAT_LOYAL_CLASS', 'LOYAL', '当前私银主账户生客熟客忠诚客分类', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 当前财富生客熟客忠诚客分类（2026年）（★推定：同上（2026 口径））
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS_Y2026', 'NEW', '当前财富生客熟客忠诚客分类（2026年）', '生客', 1, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS_Y2026', 'REPEAT', '当前财富生客熟客忠诚客分类（2026年）', '熟客', 2, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NEW_REPEAT_LOYAL_CLASS_Y2026', 'LOYAL', '当前财富生客熟客忠诚客分类（2026年）', '忠诚客', 3, '2026-09-15 00:00:00'),
  -- 本年最高财富收益产品大类（★推定：财富收益产品大类）
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'FUND', '本年最高财富收益产品大类', '基金', 1, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'WMP', '本年最高财富收益产品大类', '理财', 2, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'INSURANCE', '本年最高财富收益产品大类', '保险', 3, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'DEPOSIT', '本年最高财富收益产品大类', '存款', 4, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'GOLD', '本年最高财富收益产品大类', '贵金属', 5, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'TRUST', '本年最高财富收益产品大类', '信托', 6, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'BOND', '本年最高财富收益产品大类', '债券', 7, '2026-09-15 00:00:00'),
  ('CUR_YEAR_MAX_WEALTH_INCOME_PRODUCT_CATEGORY', 'OTHER', '本年最高财富收益产品大类', '其他', 8, '2026-09-15 00:00:00'),
  -- 当前税前平均月收入等级（★推定：税前月收入分档）
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '01', '当前税前平均月收入等级', '5千以下', 1, '2026-09-15 00:00:00'),
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '02', '当前税前平均月收入等级', '5千(含)-1万', 2, '2026-09-15 00:00:00'),
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '03', '当前税前平均月收入等级', '1万(含)-2万', 3, '2026-09-15 00:00:00'),
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '04', '当前税前平均月收入等级', '2万(含)-5万', 4, '2026-09-15 00:00:00'),
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '05', '当前税前平均月收入等级', '5万(含)-10万', 5, '2026-09-15 00:00:00'),
  ('CUR_PRE_TAX_AVG_MONTHLY_INCOME_LEVEL', '06', '当前税前平均月收入等级', '10万及以上', 6, '2026-09-15 00:00:00'),
  -- 当前基金定投状态（★推定：基金定投状态）
  ('CUR_FUND_SIP_STATUS', 'NONE', '当前基金定投状态', '未定投', 1, '2026-09-15 00:00:00'),
  ('CUR_FUND_SIP_STATUS', 'ACTIVE', '当前基金定投状态', '定投中', 2, '2026-09-15 00:00:00'),
  ('CUR_FUND_SIP_STATUS', 'SUSPENDED', '当前基金定投状态', '已暂停', 3, '2026-09-15 00:00:00'),
  ('CUR_FUND_SIP_STATUS', 'TERMINATED', '当前基金定投状态', '已终止', 4, '2026-09-15 00:00:00'),
  -- 当前权益值账户类型（★推定：权益值账户归属类型）
  ('CUR_BENEFIT_VALUE_ACCT_TYPE', 'PERSONAL', '当前权益值账户类型', '个人账户', 1, '2026-09-15 00:00:00'),
  ('CUR_BENEFIT_VALUE_ACCT_TYPE', 'FAMILY', '当前权益值账户类型', '家庭账户', 2, '2026-09-15 00:00:00'),
  ('CUR_BENEFIT_VALUE_ACCT_TYPE', 'MERCHANT', '当前权益值账户类型', '商户账户', 3, '2026-09-15 00:00:00'),
  -- 当前生意通授信状态（★推定：授信状态）
  ('CUR_BUSINESS_LINK_CREDIT_STATUS', 'NORMAL', '当前生意通授信状态', '正常', 1, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_STATUS', 'FROZEN', '当前生意通授信状态', '冻结', 2, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_STATUS', 'CLOSED', '当前生意通授信状态', '已关闭', 3, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_STATUS', 'EXPIRED', '当前生意通授信状态', '已到期', 4, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_STATUS', 'NONE', '当前生意通授信状态', '无授信', 5, '2026-09-15 00:00:00'),
  -- 当前工薪贷类授信状态（★推定：授信状态）
  ('CUR_PAY_LOAN_TYPE_CREDIT_STATUS', 'NORMAL', '当前工薪贷类授信状态', '正常', 1, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_TYPE_CREDIT_STATUS', 'FROZEN', '当前工薪贷类授信状态', '冻结', 2, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_TYPE_CREDIT_STATUS', 'CLOSED', '当前工薪贷类授信状态', '已关闭', 3, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_TYPE_CREDIT_STATUS', 'EXPIRED', '当前工薪贷类授信状态', '已到期', 4, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_TYPE_CREDIT_STATUS', 'NONE', '当前工薪贷类授信状态', '无授信', 5, '2026-09-15 00:00:00'),
  -- 当前速易贷额度冻结状态（★推定：额度冻结状态）
  ('CUR_FAST_LOAN_CREDIT_LINE_FREEZE_STATUS', 'NORMAL', '当前速易贷额度冻结状态', '正常', 1, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_LINE_FREEZE_STATUS', 'FROZEN', '当前速易贷额度冻结状态', '已冻结', 2, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_LINE_FREEZE_STATUS', 'RELEASED', '当前速易贷额度冻结状态', '已解冻', 3, '2026-09-15 00:00:00'),
  -- 当前速易贷授信状态（★推定：授信状态）
  ('CUR_FAST_LOAN_CREDIT_STATUS', 'NORMAL', '当前速易贷授信状态', '正常', 1, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_STATUS', 'FROZEN', '当前速易贷授信状态', '冻结', 2, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_STATUS', 'CLOSED', '当前速易贷授信状态', '已关闭', 3, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_STATUS', 'EXPIRED', '当前速易贷授信状态', '已到期', 4, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_CREDIT_STATUS', 'NONE', '当前速易贷授信状态', '无授信', 5, '2026-09-15 00:00:00'),
  -- 当前生意通额度冻结状态（★推定：额度冻结状态）
  ('CUR_BUSINESS_LINK_CREDIT_LINE_FREEZE_STATUS', 'NORMAL', '当前生意通额度冻结状态', '正常', 1, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_LINE_FREEZE_STATUS', 'FROZEN', '当前生意通额度冻结状态', '已冻结', 2, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_CREDIT_LINE_FREEZE_STATUS', 'RELEASED', '当前生意通额度冻结状态', '已解冻', 3, '2026-09-15 00:00:00'),
  -- 当前客户升金重点跟进员工HR条线（★推定：员工归属条线）
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'PERSONAL', '当前客户升金重点跟进员工HR条线', '个金条线', 1, '2026-09-15 00:00:00'),
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'WEALTH', '当前客户升金重点跟进员工HR条线', '财富条线', 2, '2026-09-15 00:00:00'),
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'LOAN', '当前客户升金重点跟进员工HR条线', '信贷条线', 3, '2026-09-15 00:00:00'),
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'OPS', '当前客户升金重点跟进员工HR条线', '运营条线', 4, '2026-09-15 00:00:00'),
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'CORPORATE', '当前客户升金重点跟进员工HR条线', '对公条线', 5, '2026-09-15 00:00:00'),
  ('CUR_CUST_UPGRADE_TO_GOLD_KEY_FOLLOW_UP_EMPLOYEE_HR_LINE', 'OTHER', '当前客户升金重点跟进员工HR条线', '其他', 6, '2026-09-15 00:00:00'),
  -- 当前理财风评等级（★推定：理财风险承受能力等级 C1-C5）
  ('CUR_WMP_RISK_ASSESSMENT_LEVEL', 'C1', '当前理财风评等级', 'C1 谨慎型', 1, '2026-09-15 00:00:00'),
  ('CUR_WMP_RISK_ASSESSMENT_LEVEL', 'C2', '当前理财风评等级', 'C2 稳健型', 2, '2026-09-15 00:00:00'),
  ('CUR_WMP_RISK_ASSESSMENT_LEVEL', 'C3', '当前理财风评等级', 'C3 平衡型', 3, '2026-09-15 00:00:00'),
  ('CUR_WMP_RISK_ASSESSMENT_LEVEL', 'C4', '当前理财风评等级', 'C4 成长型', 4, '2026-09-15 00:00:00'),
  ('CUR_WMP_RISK_ASSESSMENT_LEVEL', 'C5', '当前理财风评等级', 'C5 进取型', 5, '2026-09-15 00:00:00'),
  -- 当前财富非保险风评等级（★推定：同上）
  ('CUR_WEALTH_NON_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C1', '当前财富非保险风评等级', 'C1 谨慎型', 1, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NON_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C2', '当前财富非保险风评等级', 'C2 稳健型', 2, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NON_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C3', '当前财富非保险风评等级', 'C3 平衡型', 3, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NON_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C4', '当前财富非保险风评等级', 'C4 成长型', 4, '2026-09-15 00:00:00'),
  ('CUR_WEALTH_NON_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C5', '当前财富非保险风评等级', 'C5 进取型', 5, '2026-09-15 00:00:00'),
  -- 当前生意通A卡评级（★推定：内部卡评级 A-E）
  ('CUR_BUSINESS_LINK_A_CARD_RATING', 'A', '当前生意通A卡评级', 'A 优质', 1, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_A_CARD_RATING', 'B', '当前生意通A卡评级', 'B 良好', 2, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_A_CARD_RATING', 'C', '当前生意通A卡评级', 'C 一般', 3, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_A_CARD_RATING', 'D', '当前生意通A卡评级', 'D 关注', 4, '2026-09-15 00:00:00'),
  ('CUR_BUSINESS_LINK_A_CARD_RATING', 'E', '当前生意通A卡评级', 'E 劣变', 5, '2026-09-15 00:00:00'),
  -- 当前工薪贷A卡评级（★推定：同上）
  ('CUR_PAY_LOAN_A_CARD_RATING', 'A', '当前工薪贷A卡评级', 'A 优质', 1, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_A_CARD_RATING', 'B', '当前工薪贷A卡评级', 'B 良好', 2, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_A_CARD_RATING', 'C', '当前工薪贷A卡评级', 'C 一般', 3, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_A_CARD_RATING', 'D', '当前工薪贷A卡评级', 'D 关注', 4, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_A_CARD_RATING', 'E', '当前工薪贷A卡评级', 'E 劣变', 5, '2026-09-15 00:00:00'),
  -- 当前工薪贷B卡评级（★推定：同上）
  ('CUR_PAY_LOAN_B_CARD_RATING', 'A', '当前工薪贷B卡评级', 'A 优质', 1, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_B_CARD_RATING', 'B', '当前工薪贷B卡评级', 'B 良好', 2, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_B_CARD_RATING', 'C', '当前工薪贷B卡评级', 'C 一般', 3, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_B_CARD_RATING', 'D', '当前工薪贷B卡评级', 'D 关注', 4, '2026-09-15 00:00:00'),
  ('CUR_PAY_LOAN_B_CARD_RATING', 'E', '当前工薪贷B卡评级', 'E 劣变', 5, '2026-09-15 00:00:00'),
  -- 投资经验（理财风评）（★推定：投资经验年限分档）
  ('INVESTMENT_EXPERIENCE_WMP_RISK_ASSESSMENT', '01', '投资经验（理财风评）', '无经验(1年以下)', 1, '2026-09-15 00:00:00'),
  ('INVESTMENT_EXPERIENCE_WMP_RISK_ASSESSMENT', '02', '投资经验（理财风评）', '1-3年', 2, '2026-09-15 00:00:00'),
  ('INVESTMENT_EXPERIENCE_WMP_RISK_ASSESSMENT', '03', '投资经验（理财风评）', '3-5年', 3, '2026-09-15 00:00:00'),
  ('INVESTMENT_EXPERIENCE_WMP_RISK_ASSESSMENT', '04', '投资经验（理财风评）', '5-10年', 4, '2026-09-15 00:00:00'),
  ('INVESTMENT_EXPERIENCE_WMP_RISK_ASSESSMENT', '05', '投资经验（理财风评）', '10年以上', 5, '2026-09-15 00:00:00'),
  -- 当前速易贷B卡评级（★推定：同上）
  ('CUR_FAST_LOAN_B_CARD_RATING', 'A', '当前速易贷B卡评级', 'A 优质', 1, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_B_CARD_RATING', 'B', '当前速易贷B卡评级', 'B 良好', 2, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_B_CARD_RATING', 'C', '当前速易贷B卡评级', 'C 一般', 3, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_B_CARD_RATING', 'D', '当前速易贷B卡评级', 'D 关注', 4, '2026-09-15 00:00:00'),
  ('CUR_FAST_LOAN_B_CARD_RATING', 'E', '当前速易贷B卡评级', 'E 劣变', 5, '2026-09-15 00:00:00'),
  -- 当前基金风评等级（★推定：基金风险承受能力等级 C1-C5）
  ('CUR_FUND_RISK_ASSESSMENT_LEVEL', 'C1', '当前基金风评等级', 'C1 谨慎型', 1, '2026-09-15 00:00:00'),
  ('CUR_FUND_RISK_ASSESSMENT_LEVEL', 'C2', '当前基金风评等级', 'C2 稳健型', 2, '2026-09-15 00:00:00'),
  ('CUR_FUND_RISK_ASSESSMENT_LEVEL', 'C3', '当前基金风评等级', 'C3 平衡型', 3, '2026-09-15 00:00:00'),
  ('CUR_FUND_RISK_ASSESSMENT_LEVEL', 'C4', '当前基金风评等级', 'C4 成长型', 4, '2026-09-15 00:00:00'),
  ('CUR_FUND_RISK_ASSESSMENT_LEVEL', 'C5', '当前基金风评等级', 'C5 进取型', 5, '2026-09-15 00:00:00'),
  -- 家庭总资产（理财风评）（★推定：家庭总资产分档）
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '01', '家庭总资产（理财风评）', '50万以下', 1, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '02', '家庭总资产（理财风评）', '50万(含)-100万', 2, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '03', '家庭总资产（理财风评）', '100万(含)-300万', 3, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '04', '家庭总资产（理财风评）', '300万(含)-600万', 4, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '05', '家庭总资产（理财风评）', '600万(含)-1000万', 5, '2026-09-15 00:00:00'),
  ('HOUSEHOLD_TOTAL_ASSET_WMP_RISK_ASSESSMENT', '06', '家庭总资产（理财风评）', '1000万及以上', 6, '2026-09-15 00:00:00'),
  -- 当前保险风评等级（★推定：保险风险承受能力等级 C1-C5）
  ('CUR_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C1', '当前保险风评等级', 'C1 谨慎型', 1, '2026-09-15 00:00:00'),
  ('CUR_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C2', '当前保险风评等级', 'C2 稳健型', 2, '2026-09-15 00:00:00'),
  ('CUR_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C3', '当前保险风评等级', 'C3 平衡型', 3, '2026-09-15 00:00:00'),
  ('CUR_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C4', '当前保险风评等级', 'C4 成长型', 4, '2026-09-15 00:00:00'),
  ('CUR_INSURANCE_RISK_ASSESSMENT_LEVEL', 'C5', '当前保险风评等级', 'C5 进取型', 5, '2026-09-15 00:00:00'),
  -- 最新征信工作情况（★推定：征信报告工作情况口径）
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'EMPLOYED', '最新征信工作情况', '在职', 1, '2026-09-15 00:00:00'),
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'SELF_EMPLOYED', '最新征信工作情况', '自营/个体', 2, '2026-09-15 00:00:00'),
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'RETIRED', '最新征信工作情况', '退休', 3, '2026-09-15 00:00:00'),
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'UNEMPLOYED', '最新征信工作情况', '无业', 4, '2026-09-15 00:00:00'),
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'STUDENT', '最新征信工作情况', '学生', 5, '2026-09-15 00:00:00'),
  ('LATEST_CIR_EMPLOYMENT_STATUS', 'OTHER', '最新征信工作情况', '其他', 6, '2026-09-15 00:00:00')
AS src
ON DUPLICATE KEY UPDATE
  `tag_name_cn`      = src.`tag_name_cn`,
  `code_definition`  = src.`code_definition`,
  `code_sort`        = src.`code_sort`,
  `last_update_time` = src.`last_update_time`;

-- ----------------------------------------------------------------------------
-- 机构类字段（开户/管户一级・二级・三级机构 共 6 个）不在此文件：
--   其码值为真实机构标识（联行号 CNAPS），已单独生成于
--   05_insert_L_INDVCST_LABEL_CODE_MAP_BRANCH.sql（共 1270 条）
-- ----------------------------------------------------------------------------
