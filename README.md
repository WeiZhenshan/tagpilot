<p align="center">
    <img alt="logo" src="https://oscimg.oschina.net/oscnet/up-d3d0a9303e11d522a06cd263f3079027715.png">
</p>
<h1 align="center" style="margin: 30px 0 30px; font-weight: bold;">TagPilot 标签管理系统</h1>
<h4 align="center">基于 RuoYi-Vue 的数据中台与标签客群一体化管理平台</h4>
<p align="center">
    <a href="https://github.com/WeiZhenshan/tagpilot"><img src="https://img.shields.io/badge/TagPilot-v1.0-brightgreen.svg"></a>
    <a href="https://github.com/WeiZhenshan/tagpilot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mashape/apistatus.svg"></a>
</p>

## 项目简介

**TagPilot** 是在 [RuoYi-Vue](https://gitee.com/y_project/RuoYi-Vue)（Spring Boot 2.5.15 / Java 8）基础上深度定制的标签客群管理系统，涵盖**数据源管理（DataBroker）、标签库（TagLibrary）、客群圈选（ObjectGroup）**三大核心模块，提供从数据源接入、元数据管理、标签生产到客群筛选的一站式解决方案。

### 架构总览

```
┌─────────────────────────────────────────────────┐
│                  客群圈选 (ObjectGroup)           │
│       规则引擎 · SQL 生成 · 码值解析 · 导入导出      │
├─────────────────────────────────────────────────┤
│                  标签库 (TagLibrary)              │
│     标签目录 · 标签管理 · 维度管理 · 映射同步 · 元数据审核 │
├─────────────────────────────────────────────────┤
│               数据源管理 (DataBroker)              │
│   数据源管理 · 数据集版本管理 · 维表管理 · 元数据采集    │
├─────────────────────────────────────────────────┤
│              RuoYi-Vue 基础平台                    │
│     RBAC 权限 · JWT 认证 · Redis 缓存 · MyBatis    │
└─────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. 数据源管理 (DataBroker) — `ruoyi-databroker`

数据源与元数据管理层，为上层标签和客群提供统一的数据底座。

| 功能 | 说明 |
| :--- | :--- |
| **数据源管理** | 注册 JDBC 数据源（支持连接测试、加密存储），树形目录组织 |
| **数据集管理** | 定义 SQL 数据集，支持**多版本管理（草稿/发布/下线/复制）**，自动采集元数据（表/字段/类型/注释） |
| **在线版本解析** | 统一解析数据集当前在线版本，默认版本优先，自动回退最大版本号在线版本 |
| **维表管理** | 登记码值维度表、标准字段预检、物理码值预览 |
| **元数据同步** | JDBC 直连采集表结构元数据，记录变更日志 |

### 2. 标签库 (TagLibrary) — `ruoyi-taglibrary`

标签全生命周期管理模块。

| 功能 | 说明 |
| :--- | :--- |
| **目录管理** | 多级树形标签目录，支持拖拽移动排序 |
| **标签管理** | 标签 CRUD、从数据集版本中选取输出字段生成标签、标签状态管理 |
| **维度管理** | 标签维度关联、码值映射配置、维度候选值维护 |
| **批量映射同步** | 标签与维度的批量映射关系管理，同步信息区展示、三状态分列，支持跨页勾选、撤回、未保存保护 |
| **元数据审核** | 变更类型记录、来源快照、完整性校验、**双阶段互斥**、旁路封堵、撤回接口 |
| **对账同步** | 标签与维度的同步对账机制，来源缺失恢复、结构变更待确认、同步统计与行锁 |

### 3. 客群圈选 (ObjectGroup) — `ruoyi-objectgroup`

可视化规则引擎驱动的客群筛选与导出模块。

| 功能 | 说明 |
| :--- | :--- |
| **规则编辑器** | 可视化拖拽式条件组合，支持标签拖入定位、码值缓存防竞态、树过滤可拖标签、失效编码拦截 |
| **SQL 生成引擎** | 基于标签定义和维度关系自动生成筛选 SQL，支持预览中文副本 |
| **码值解析** | 在线版本解析贯穿，维度表码值查询与缓存 |
| **客群管理** | 客群定义 CRUD、规则校验、结果预览 |
| **导入导出** | 客群名单导入导出 |

---

## 技术栈

**后端**

| 技术 | 版本 |
| :--- | :--- |
| Java | 8 |
| Spring Boot | 2.5.15 |
| Spring Security | 5.x |
| MyBatis | 3.x |
| MySQL | 8.x |
| Redis | (Token/缓存) |
| Maven | 3.x |

**前端**

| 技术 | 版本 |
| :--- | :--- |
| Vue | 2.x |
| Element UI | 2.x |
| Vue CLI | 4.x |
| Axios | — |

---

## 快速开始

### 环境要求

- JDK 8（推荐 Amazon Corretto 8）
- Maven 3.6+
- MySQL 8.0+
- Redis
- Node.js 16+（前端构建）

### 数据库初始化

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS `ry` DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci;

-- 导入基础表结构与种子数据
source sql/ry_20260417.sql;

-- 导入 Quartz 定时任务表
source sql/quartz.sql;
```

### 后端启动

```bash
# 构建
mvn clean package -DskipTests

# 启动（Spring Boot）
java -jar ruoyi-admin/target/ruoyi-admin.jar

# 或使用脚本
./ry.sh start
```

配置文件：`ruoyi-admin/src/main/resources/application-druid.yml`（数据库连接）、`application.yml`（Redis、Token 等）。

### 前端启动

```bash
cd ruoyi-ui
npm install
npm run dev       # 开发模式，端口 80，代理 /dev-api → localhost:8080
npm run build:prod # 生产构建
```

### 一键启停 (`dev.sh`)

项目提供 `dev.sh` 脚本参照 `ry.sh` 风格统一管理前后端进程：

```bash
./dev.sh start       # 启动前后端（jar 缺失或源码有更新时自动增量编译）
./dev.sh stop        # 停止前后端
./dev.sh restart     # 重启
./dev.sh status      # 查看进程状态
./dev.sh build       # 强制重新编译后端（mvn clean package -DskipTests）
```

脚本特性：
- 自动检测 Redis（6379）和 MySQL（3306）是否就绪，未启动时中止并提示
- 自动切换到本机 JDK 1.8（系统默认 JDK 17 时自动降级）
- 数据源加密密钥自动管理：首次运行时随机生成并持久化到 `.databroker-crypto-secret`，避免每次重启换钥导致存量密文不可解
- 支持自定义前端端口：`PORT=8081 ./dev.sh start`
- 支持自定义加密密钥：`DATABROKER_CRYPTO_SECRET=xxx ./dev.sh start`

---

## 项目结构

```
ruoyi-admin          # 应用入口，Controller 层
ruoyi-framework      # 安全框架、JWT、AOP、配置
ruoyi-system         # RBAC 基础业务（用户/角色/菜单/部门）
ruoyi-common         # 公共工具与基类
ruoyi-databroker     # 数据源管理模块
ruoyi-taglibrary     # 标签库模块
ruoyi-objectgroup    # 客群圈选模块
ruoyi-quartz         # 定时任务
ruoyi-generator      # 代码生成器
ruoyi-ui             # Vue 2 前端项目
```

---

## 许可证

本项目基于 RuoYi-Vue，遵循 MIT 协议。