-- ----------------------------
-- 客户标签宽表
-- 说明：配合 /Users/wzs/ZCodeProject/标签宽表模拟数据生成/ind_tag_data.csv 导入使用
-- 导入命令见文末“数据导入 - LOAD DATA”章节
-- ----------------------------
drop table if exists ind_tag_data;
create table ind_tag_data (
  cust_id                        varchar(20)     not null                   comment '客户ID',
  gender                         char(1)         default null               comment '性别（F女 M男）',
  age                            tinyint         default null               comment '年龄',
  age_group                      varchar(10)     default null               comment '年龄段（18-24/25-29/.../60+）',
  education                      varchar(20)     default null               comment '学历',
  marriage_status                varchar(10)     default null               comment '婚姻状况',
  occupation_type                varchar(30)     default null               comment '职业类型',
  annual_income_k                decimal(8,1)    default null               comment '年收入（千元）',
  annual_income_range            varchar(20)     default null               comment '年收入区间',
  city_tier                      tinyint         default null               comment '城市等级（1/2/3/4线）',
  region                         varchar(10)     default null               comment '所在区域（华东/华北/...）',
  branch_code                    varchar(20)     default null               comment '所属支行代码',
  cust_segment                   varchar(20)     default null               comment '客户分层（大众/富裕/高净值/私银）',
  is_new_cust                    tinyint(1)      default 0                  comment '是否新客（0否 1是）',
  is_active_cust                 tinyint(1)      default 0                  comment '是否活跃客户（0否 1是）',
  is_salary_cust                 tinyint(1)      default 0                  comment '是否代发工资客户（0否 1是）',
  is_young_elite                 tinyint(1)      default 0                  comment '是否青年精英（0否 1是）',
  is_retiree                     tinyint(1)      default 0                  comment '是否退休人群（0否 1是）',
  is_owner_entrepreneur          tinyint(1)      default 0                  comment '是否企业主/个体经营者（0否 1是）',
  is_white_collar                tinyint(1)      default 0                  comment '是否白领（0否 1是）',
  is_student                     tinyint(1)      default 0                  comment '是否学生（0否 1是）',
  is_housewife                   tinyint(1)      default 0                  comment '是否家庭主妇/夫（0否 1是）',
  life_stage                     varchar(30)     default null               comment '人生阶段',
  consumption_preference         varchar(30)     default null               comment '消费偏好',
  aum_balance                    decimal(16,2)   default 0                  comment 'AUM管理资产余额（元）',
  aum_level                      varchar(20)     default null               comment 'AUM等级',
  avg_daily_deposit              decimal(16,2)   default 0                  comment '日均存款（元）',
  contribution_score             int(5)          default 0                  comment '贡献度评分（0-100）',
  contribution_level             varchar(10)     default null               comment '贡献度等级',
  clv_score                      int(5)          default 0                  comment '客户生命周期价值CLV评分（0-100）',
  clv_level                      varchar(10)     default null               comment 'CLV等级',
  cross_sell_index               int(5)          default 0                  comment '交叉销售指数（0-100）',
  loyalty_years                  decimal(5,1)    default 0                  comment '忠诚度年数',
  loyalty_level                  varchar(10)     default null               comment '忠诚度等级',
  has_deposit                    tinyint(1)      default 0                  comment '是否持有存款（0否 1是）',
  has_wealth                     tinyint(1)      default 0                  comment '是否持有理财（0否 1是）',
  has_fund                       tinyint(1)      default 0                  comment '是否持有基金（0否 1是）',
  has_insurance                  tinyint(1)      default 0                  comment '是否持有保险（0否 1是）',
  has_credit_card                tinyint(1)      default 0                  comment '是否持有信用卡（0否 1是）',
  has_loan                       tinyint(1)      default 0                  comment '是否持有贷款（0否 1是）',
  has_forex                      tinyint(1)      default 0                  comment '是否持有外汇（0否 1是）',
  has_precious_metal             tinyint(1)      default 0                  comment '是否持有贵金属（0否 1是）',
  has_trust                      tinyint(1)      default 0                  comment '是否持有信托（0否 1是）',
  total_products_count           int(3)          default 0                  comment '持有产品总数',
  last_transaction_date          date            default null               comment '最近交易日期',
  transaction_frequency_monthly  int(5)          default 0                  comment '月交易频次',
  transaction_amt_monthly        decimal(16,2)   default 0                  comment '月交易金额（元）',
  channel_preference             varchar(20)     default null               comment '渠道偏好（线上/线下/全渠道）',
  online_login_freq_monthly      int(5)          default 0                  comment '月网银登录次数',
  counter_visit_freq_quarterly   int(5)          default 0                  comment '季度柜面访问次数',
  is_mobile_banking_user         tinyint(1)      default 0                  comment '是否手机银行用户（0否 1是）',
  is_online_banking_user         tinyint(1)      default 0                  comment '是否网银用户（0否 1是）',
  is_wechat_banking_user         tinyint(1)      default 0                  comment '是否微信银行用户（0否 1是）',
  auto_invest_flag               tinyint(1)      default 0                  comment '是否开通自动投资（0否 1是）',
  auto_pay_flag                  tinyint(1)      default 0                  comment '是否开通自动还款（0否 1是）',
  primary_transaction_type       varchar(20)     default null               comment '主要交易类型',
  risk_rating                    varchar(5)      default null               comment '风险评级（R1-R5）',
  risk_tolerance                 varchar(10)     default null               comment '风险承受能力',
  kyc_status                     varchar(10)     default null               comment 'KYC实名状态（完整/基本/未完成）',
  is_pep                         tinyint(1)      default 0                  comment '是否政治公众人物PEP（0否 1是）',
  overdue_count_12m              int(3)          default 0                  comment '近12个月逾期次数',
  overdue_amount_max             decimal(16,2)   default 0                  comment '最大逾期金额（元）',
  credit_score                   int(5)          default 0                  comment '信用评分',
  blacklist_flag                 tinyint(1)      default 0                  comment '是否黑名单（0否 1是）',
  fraud_alert_flag               tinyint(1)      default 0                  comment '是否有欺诈预警（0否 1是）',
  suspicious_transaction_flag    tinyint(1)      default 0                  comment '是否有可疑交易（0否 1是）',
  aml_risk_level                 varchar(10)     default null               comment '反洗钱风险等级（低/中/高）',
  primary key (cust_id)
) engine=innodb default charset=utf8mb4 comment = '客户标签宽表';

-- ----------------------------
-- 数据导入 - LOAD DATA（推荐，2万行约1秒）
-- 注意：
--   1) secure_file_priv 限制时，请把 CSV 放到 MySQL 允许的目录，或改用方式二/三
--   2) CSV 是 UTF-8（带 BOM），IGNORE 1 LINES 跳过表头，BOM 不会进入数据行
--   3) CSV 字段分隔符为逗号，无文本限定符；若数据中出现逗号请改用工具导入
-- ----------------------------
-- load data local infile '/Users/wzs/ZCodeProject/标签宽表模拟数据生成/ind_tag_data.csv'
-- into table ind_tag_data
-- character set utf8mb4
-- fields terminated by ',' optionally enclosed by '"'
-- lines terminated by '\n'
-- ignore 1 lines;
