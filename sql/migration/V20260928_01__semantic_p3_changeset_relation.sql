-- P3：候选关联不改变主概念与 family_key；变更包与审计保留历史，向前幂等。
create table if not exists ts_concept_tag_relation (
    relation_id bigint not null auto_increment,
    library_id bigint not null,
    concept_id bigint not null,
    tag_id bigint not null,
    relation_note varchar(1000) not null,
    source_ref varchar(500) not null,
    review_status varchar(16) not null default 'DRAFT',
    version int not null default 1,
    primary key (relation_id),
    unique key uk_ts_ctr (library_id, concept_id, tag_id)
) engine=innodb comment='概念到候选标签的关联，非等价关系';

create table if not exists ts_semantic_changeset (
    change_id varchar(96) not null,
    library_id bigint not null,
    baseline_snapshot varchar(64) not null,
    package_hash char(64) not null,
    package_json json not null,
    applied_by varchar(64) not null,
    applied_at datetime not null,
    primary key (change_id)
) engine=innodb comment='受控语义变更包及修改前后证据';
