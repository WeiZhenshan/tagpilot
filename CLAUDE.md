# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Backend (Spring Boot 2.5 + Java 8)

```bash
# Build all modules
mvn clean package -DskipTests

# Run tests
mvn test

# Run a single test class
mvn test -pl ruoyi-system -Dtest=ClassName

# Start the app (packaged jar)
java -jar ruoyi-admin/target/ruoyi-admin.jar

# Start via shell script (dev)
./ry.sh start    # stop|restart|status
```

The admin module is the entry point (`ruoyi-admin`). It depends on all other modules and contains controllers, resources, and `RuoYiApplication.java`.

### Frontend (Vue 2 + Element UI)

```bash
cd ruoyi-ui
npm install
npm run dev           # dev server
npm run build:prod    # production build
npm run build:stage   # staging build
```

## Module Architecture

The project is a 9-module Maven multi-module project (`pom.xml` at root):

| Module | Purpose |
|---|---|
| `ruoyi-admin` | Entry point. Spring Boot startup, HTTP controllers, YAML config, i18n resources, MyBatis config. |
| `ruoyi-framework` | Cross-cutting infrastructure: Security config, JWT filter, AOP aspects (logging, data-scope, rate-limiting, data-source switching), Druid/Redis/MyBatis/thread-pool config, repeat-submit interceptor, `TokenService`, `PermissionService`. |
| `ruoyi-system` | Core business logic: domain entities, MyBatis mappers, service layer for users, roles, menus, depts, posts, config, dicts, notices. |
| `ruoyi-common` | Shared library: domain base classes, enums, annotations, utils (String/Date/Excel/Security/Servlet/IP/uuid/http), XSS filter, exception types, constants. |
| `ruoyi-quartz` | Scheduled-task subsystem: Quartz job management UI, task execution, CRUD for job definitions. |
| `ruoyi-generator` | Code generator: Velocity-based code generation from DB table metadata. Reads `information_schema` and produces controller/service/mapper/domain/Vue templates. |
| `ruoyi-databroker` | DataBroker — data source & dataset management, metadata collection, dimension tables. Prefix `dp_`. Routes `/databroker/**`. |
| `ruoyi-taglibrary` | TagLibrary — label directory/tag/dimension management, metadata audit, batch mapping sync. Prefix `tl_`. Routes `/taglibrary/**`. |
| `ruoyi-objectgroup` | ObjectGroup — visual rule engine, SQL generation for customer segment selection, import/export. Routes `/objectgroup/**`. |

Python backends (not Maven modules): `tagpilot-semantic` is the semantic engine + vector index on `:8091`; `tagpilot-agent` is the LangGraph orchestration layer on `:8092` and calls semantic `/retrieve`. `tagpilot-assistant` is the React Assistant UI workbench on `:5174` (`/agent-ui/`), loaded from the Vue `/agent` route.

**Dependency direction**: `admin` -> `framework` -> `system` -> `common`; `admin` also directly depends on `quartz`, `generator`, `databroker`, `taglibrary` and `objectgroup`. Among the business modules, `databroker` depends on `framework`; `objectgroup` depends on `common` + `framework` + `databroker`; `taglibrary` depends on `common` + `framework` + `databroker` + `objectgroup`.

## Key Architecture Patterns

### Authentication & Authorization
- **Stateless JWT**: No server-side sessions. `JwtAuthenticationTokenFilter` extracts the token from the `Authorization` header on every request, hydrates `LoginUser` from Redis, and sets it into `SecurityContextHolder`.
- **Token lifecycle**: `TokenService.createToken()` generates a UUID stored in Redis under `login_tokens:<uuid>`. The JWT payload contains only the UUID and username. Redis is the source of truth for `LoginUser`. Token auto-refreshes if within 20 min of expiry.
- **Permission model**: `PermissionService` (bean name `"ss"`) exposes `@PreAuthorize("@ss.hasPermi('system:user:list')")` — a custom SpEL method usable in `@PreAuthorize` annotations. Permissions are loaded per-user at login and cached in the `LoginUser` object in Redis. Admin user (`userId == 1`) has all permissions.
- **Anonymous access**: The `@Anonymous` annotation on a controller method bypasses authentication, collected at startup by `PermitAllUrlProperties`.
- **RBAC + data scope**: Roles assign menu permissions. The `@DataScope` annotation + `DataScopeAspect` filters queries by dept hierarchy (dept, dept-and-children, self, custom).

### Multi-DataSource
- Read/write splitting via `DynamicDataSourceContextHolder` (ThreadLocal). The `@DataSource` annotation + `DataSourceAspect` switch between `MASTER` and `SLAVE` before a service method executes.

### Request/Response
- **Unified response**: All controllers return `AjaxResult` (code, msg, data) or `TableDataInfo` (paginated). The `web/core` package contains base controller and global exception handler.
- **Repeat-submit guard**: `@RepeatSubmit` annotation + `RepeatSubmitInterceptor`. Subclass implements `isRepeatSubmit()` to define the rule (e.g., compare request params within an interval).
- **XSS filtering**: Configurable in `application.yml` (`xss.enabled`, `xss.urlPatterns`). Exclusions via `xss.excludes`.
- **Rate limiting**: `@RateLimiter` annotation + `RateLimiterAspect` backed by Redis counters.

### MyBatis
- XML mappers live in each module's `src/main/resources/mapper/<module>/` (e.g. `ruoyi-system/.../mapper/system/`, `ruoyi-databroker/.../mapper/databroker/`), aggregated at startup by `mybatis.mapperLocations: classpath*:mapper/**/*Mapper.xml`. Aliases declared in `mybatis.typeAliasesPackage: com.ruoyi.**.domain`. PageHelper configured for MySQL dialect. Custom `MyBatisConfig` enables map-underscore-to-camel-case by default.

### Frontend (ruoyi-ui)
- Vue 2 + Vuex + Vue Router 3 + Element UI + Axios.
- `src/api/` — request modules organized by feature.
- `src/views/` — page components mirroring the backend controller structure.
- `src/store/modules/permission.js` — dynamic route loading from the backend menu tree.
- `src/permission.js` — router guard that checks login state and fetches user info/menus.
- `src/utils/request.js` — Axios interceptor: attaches token header, handles 401 redirect.

## Configuration

- **Active profile**: `spring.profiles.active: druid` — DB config lives in `application-druid.yml`.
- **Redis required**: Token storage, cache, rate-limiting all depend on Redis.
- **DB init**: Run `sql/init/ry_init.sql` once on MySQL 8.0+ (creates the `ry` + `indiv_cust` databases); later incremental changes go in `sql/migration/` and are applied by `bin/db-migrate.sh`. Full script index in `sql/README.md`.
- `ruoyi.profile` sets the file-upload root path (OS-specific).
- `token.expireTime` units are **minutes** (default 30).
- `user.password.maxRetryCount` / `lockTime` control account lockout (default 5 attempts / 10 min).

## Internal Conventions
- `ruoyi-common` is the only allowed cross-cutting dependency (no circular references between business modules).
- Domain entities extend `BaseEntity` (createBy, createTime, updateBy, updateTime, remark, params map).
- Tree entities (dept, menu) extend `TreeEntity` (parentId, parentName, orderNum, ancestors, children).
- Enum values are stored as strings in the DB, not ordinal integers.
- Controller-level `@PreAuthorize` checks are the primary authorization mechanism; service-level methods use the `@DataScope` aspect for row-level filtering.
