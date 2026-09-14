# AGENTS.md

Workspace guidance for ZCode agents working in `/Users/wzs/dev/RuoYi-Vue`.

For in-depth architecture (auth/JWT flow, data-scope, multi-datasource, MyBatis, frontend structure) read **`CLAUDE.md`** first — this file complements it and avoids duplicating that detail.

## What this repo is

RuoYi-Vue v3.9.2 — a Chinese-origin Java + Vue admin/RBAC rapid-development platform (若依管理系统). Spring Boot 2.5.15 + Java 8 backend, Vue 2 + Element UI frontend, stateless JWT auth, Redis-backed, MyBatis + MySQL.

- Primary language of comments/UI/commits is **Chinese**; match that when editing existing code.
- Official docs: http://doc.ruoyi.vip · Demo: http://vue.ruoyi.vip (admin/admin123).

## Module layout

9-module Maven multi-module (`pom.xml` at root). Dependency direction: `admin → framework → system → common`; `admin` also pulls `quartz`, `generator`, `databroker`, `taglibrary` and `objectgroup`. Business modules chain as `taglibrary → objectgroup → databroker → framework`.

| Module | Role |
|---|---|
| `ruoyi-admin` | Entry point: `RuoYiApplication`, HTTP controllers (`web/controller/{system,monitor,common,tool}`), YAML config, i18n, MyBatis config. |
| `ruoyi-framework` | Cross-cutting infra: Spring Security config, JWT filter, aspects (logging/data-scope/rate-limiter/datasource), Druid/Redis/MyBatis/thread-pool config, `TokenService`, `PermissionService` (bean `ss`). |
| `ruoyi-system` | Core business: domain entities, mappers, services for users/roles/menus/depts/posts/config/dicts/notices. |
| `ruoyi-common` | Shared lib only — base classes, enums, annotations, utils, XSS filter, exceptions, constants. No business logic. |
| `ruoyi-quartz` | Scheduled-task subsystem. |
| `ruoyi-generator` | Velocity-based codegen from DB metadata → controller/service/mapper/domain/Vue. |
| `ruoyi-databroker` | DataBroker: data source / dataset / dimension management, metadata collection. Tables `dp_*`, routes `/databroker/**`, mappers in `resources/mapper/databroker/`. |
| `ruoyi-taglibrary` | TagLibrary: tag directory / tag / dimension, metadata audit, batch mapping sync. Tables `tl_*`, routes `/taglibrary/**`, mappers in `resources/mapper/taglibrary/`. |
| `ruoyi-objectgroup` | ObjectGroup: visual rule editor, SQL generation, customer-segment preview and import/export. Routes `/objectgroup/**`, mappers in `resources/mapper/objectgroup/`. |
| `ruoyi-ui` | Vue 2 frontend (separate npm project, see below). |

**Layer rule:** `ruoyi-common` is the only allowed cross-cutting dependency. Never introduce circular deps between business modules. Domain entities extend `BaseEntity` (or `TreeEntity` for dept/menu).

## Build & run

### Backend (root)
```bash
mvn clean package -DskipTests          # build all modules → ruoyi-admin/target/ruoyi-admin.jar
mvn test                               # see "Testing" gotcha below
mvn test -pl ruoyi-system -Dtest=Foo   # single test class
java -jar ruoyi-admin/target/ruoyi-admin.jar
./ry.sh start                          # start|stop|restart|status (packaged jar)
```
Windows helpers in `bin/` (`clean.bat`, `package.bat`, `run.bat`). Active profile: `druid` → DB config in `ruoyi-admin/src/main/resources/application-druid.yml`.

### Frontend (`ruoyi-ui/`)
```bash
cd ruoyi-ui
npm install
npm run dev          # dev server on port 80, proxies /dev-api → http://localhost:8080
npm run build:prod   # production build → dist/
npm run build:stage  # staging
```
The dev server proxies `VUE_APP_BASE_API` (`/dev-api`) to the backend at `localhost:8080` — **the backend must be running** for the frontend to function. `@` alias → `ruoyi-ui/src`.

## Critical gotchas

- **Tests exist only in the new feature modules.** `ruoyi-databroker`, `ruoyi-taglibrary`, `ruoyi-objectgroup` have JUnit 5 + Mockito unit tests under `src/test/` (service-layer, mocked mappers/JDBC, no Spring context); those three poms declare `spring-boot-starter-test` (test scope) and `maven-surefire-plugin` 2.22.2 (the Maven-default 2.12.4 silently skips JUnit 5 → "Tests run: 0"). All other modules still have **0** tests — a green `mvn test` only proves those three suites pass.
- **Toolchain source of truth.** This checkout is **Spring Boot 2.5.15 / Java 8** (`pom.xml` → `spring-boot.version`, `java.version`); the default branch is `main`. Always trust `pom.xml` over prose when the toolchain matters.
- **Redis is mandatory.** Token storage, caching, rate-limiting, and login-session hydration all fail without a running Redis.
- **DB init & migration:** 新服务器首次部署执行一次 `sql/init/ry_init.sql`（创建 `ry` + `indiv_cust` 两库，含结构与基础数据，需要 MySQL 8.0+）。之后的增量变更：在 `sql/migration/` 新增 `V<yyyymmdd>_<序号>__<描述>.sql`（幂等、只向前、不得含 `drop table`），由 `bin/db-migrate.sh` 执行并记录到 `schema_migration` 表；流水线 Deploy 阶段会自动执行。旧的 `sql/archive/ry_20260417.sql` + `sql/archive/quartz.sql` 初始化方式已被取代。
- **No frontend lint/format tooling.** No ESLint, Prettier, or `.editorconfig` is configured — there is no `npm run lint`. Match the surrounding file's style by hand.
- **CI:** `.github/workflows/deploy.yml` 是唯一的流水线（GitHub Actions, self-hosted runner `tagpilot-prod`）：构建后端 jar + 前端 dist → 执行增量数据库迁移（`bin/db-migrate.sh`，凭据走仓库 secrets `TAGPILOT_DB_*`）→ 发布到 `/opt/tagpilot/releases/` 并健康检查/回滚。单元测试不在流水线中运行，验证是自己的责任。
- **Token expiry units are minutes** (`token.expireTime`, default 30), not seconds/ms.
- **`user.password.maxRetryCount` / `lockTime`** control account lockout (defaults 5 / 10 min).

## Conventions that matter for edits

- Controllers return `AjaxResult` (single) or `TableDataInfo` (paginated). Don't return raw entities/maps.
- Authorization is via `@PreAuthorize("@ss.hasPermi('module:resource:action')")` on controllers; admin (`userId == 1`) bypasses. Row-level filtering uses `@DataScope` on service methods.
- `@Anonymous` marks endpoints that skip auth; `@RepeatSubmit` guards duplicate submits; `@DataSource` switches master/slave; `@RateLimiter` throttles.
- Enum values are persisted as **strings**, never ordinals.
- MyBatis type-alias package is `com.ruoyi.**.domain`; mappers are XML under each module's `src/main/resources/mapper/<module>/`, loaded via `mybatis.mapperLocations: classpath*:mapper/**/*Mapper.xml`. Underscore→camelCase mapping is on by default.
- Frontend: `src/api/` = request modules per feature, `src/views/` = pages mirroring controllers, `src/store/modules/permission.js` = dynamic routes from backend menu tree, `src/utils/request.js` = Axios interceptor (attaches token, handles 401).

## Docs to read before touching sensitive areas

- `CLAUDE.md` — full architecture (auth, datasource, aspects, frontend).
- `docs/development/若依环境使用手册.docx` — environment setup manual (Chinese).
- `sql/archive/ry_20260417.sql` — canonical schema/seed reference for entity fields（已归档；当前初始化脚本为 `sql/init/ry_init.sql`）。
- `docs/README.md` — 全项目文档导航中心；`sql/README.md` — 数据库脚本统一索引。
