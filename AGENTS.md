# AGENTS.md

Workspace guidance for ZCode agents working in `/Users/wzs/dev/RuoYi-Vue`.

For in-depth architecture (auth/JWT flow, data-scope, multi-datasource, MyBatis, frontend structure) read **`CLAUDE.md`** first — this file complements it and avoids duplicating that detail.

## What this repo is

RuoYi-Vue v3.9.2 — a Chinese-origin Java + Vue admin/RBAC rapid-development platform (若依管理系统). Spring Boot 2.5.15 + Java 8 backend, Vue 2 + Element UI frontend, stateless JWT auth, Redis-backed, MyBatis + MySQL.

- Primary language of comments/UI/commits is **Chinese**; match that when editing existing code.
- Official docs: http://doc.ruoyi.vip · Demo: http://vue.ruoyi.vip (admin/admin123).

## Module layout

6-module Maven multi-module (`pom.xml` at root). Dependency direction: `admin → framework → system → common`; `admin` also pulls `quartz` + `generator`.

| Module | Role |
|---|---|
| `ruoyi-admin` | Entry point: `RuoYiApplication`, HTTP controllers (`web/controller/{system,monitor,common,tool}`), YAML config, i18n, MyBatis XML mappers under `resources/mapper/`. |
| `ruoyi-framework` | Cross-cutting infra: Spring Security config, JWT filter, aspects (logging/data-scope/rate-limiter/datasource), Druid/Redis/MyBatis/thread-pool config, `TokenService`, `PermissionService` (bean `ss`). |
| `ruoyi-system` | Core business: domain entities, mappers, services for users/roles/menus/depts/posts/config/dicts/notices. |
| `ruoyi-common` | Shared lib only — base classes, enums, annotations, utils, XSS filter, exceptions, constants. No business logic. |
| `ruoyi-quartz` | Scheduled-task subsystem. |
| `ruoyi-generator` | Velocity-based codegen from DB metadata → controller/service/mapper/domain/Vue. |
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
- **Branch ≠ README claim.** `README.md` advertises `master` = Spring Boot 4.x, but this checkout (branch `dev`) is **Spring Boot 2.5.15 / Java 8**. Always trust `pom.xml` (`java.version`, `spring-boot.version`) over the README when the toolchain matters.
- **Redis is mandatory.** Token storage, caching, rate-limiting, and login-session hydration all fail without a running Redis.
- **DB init order:** `sql/ry_20260417.sql` first, then `sql/quartz.sql`, against the `ry` MySQL database.
- **No frontend lint/format tooling.** No ESLint, Prettier, or `.editorconfig` is configured — there is no `npm run lint`. Match the surrounding file's style by hand.
- **No CI.** `.github/` contains only `FUNDING.yml`. Nothing runs on push; verification is your responsibility.
- **Token expiry units are minutes** (`token.expireTime`, default 30), not seconds/ms.
- **`user.password.maxRetryCount` / `lockTime`** control account lockout (defaults 5 / 10 min).

## Conventions that matter for edits

- Controllers return `AjaxResult` (single) or `TableDataInfo` (paginated). Don't return raw entities/maps.
- Authorization is via `@PreAuthorize("@ss.hasPermi('module:resource:action')")` on controllers; admin (`userId == 1`) bypasses. Row-level filtering uses `@DataScope` on service methods.
- `@Anonymous` marks endpoints that skip auth; `@RepeatSubmit` guards duplicate submits; `@DataSource` switches master/slave; `@RateLimiter` throttles.
- Enum values are persisted as **strings**, never ordinals.
- MyBatis type-alias package is `com.ruoyi.**.domain`; mappers are XML in `ruoyi-admin/src/main/resources/mapper/`. Underscore→camelCase mapping is on by default.
- Frontend: `src/api/` = request modules per feature, `src/views/` = pages mirroring controllers, `src/store/modules/permission.js` = dynamic routes from backend menu tree, `src/utils/request.js` = Axios interceptor (attaches token, handles 401).

## Docs to read before touching sensitive areas

- `CLAUDE.md` — full architecture (auth, datasource, aspects, frontend).
- `doc/若依环境使用手册.docx` — environment setup manual (Chinese).
- `sql/ry_20260417.sql` — canonical schema/seed reference for entity fields.
