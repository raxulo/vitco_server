# Quickyee Backend — Professional Code Standards & Conventions

This document defines the mandatory architectural and coding standards for the **Quickyee** codebase. All new code, refactoring, and feature implementations MUST strictly adhere to these guidelines.

---

## 1. Architectural Philosophy: Clean Architecture & DDD

The codebase follows **Domain-Driven Design (DDD)** and **Clean Architecture**. Every functional module in `app/modules/<module_name>/` MUST be separated into three distinct layers:

```
app/modules/<module>/
├── domain/                  # 1. Enterprise Business Rules (Zero framework dependencies)
│   ├── entities.py          # Pure Python dataclasses (@dataclass(slots=True))
│   ├── enums.py             # Domain IntEnum / StrEnum
│   ├── exceptions.py        # Module-specific domain exceptions
│   ├── repository.py        # Abstract repository interfaces (Protocol / ABC)
│   └── dto.py               # Domain DTOs
├── infrastructure/          # 2. Data Access & External Services
│   ├── models.py            # SQLAlchemy 2.0 Declarative Models
│   ├── repository.py        # Async SQLAlchemy implementation of domain interface
│   └── mapper.py            # Entity <-> Model <-> DTO bidirectional mappers
└── application/             # 3. Use-Cases & Orchestration (CQRS)
    ├── command.py           # CQRS Commands & Queries (@dataclass(slots=True, kw_only=True))
    ├── dto.py               # Application-level DTOs
    └── handler.py           # Use-case handlers (__slots__, database transactions)
```

### Layer Dependency Rule
- **Domain** depends on NOTHING (no FastAPI, no SQLAlchemy, no Starlette).
- **Application** depends ONLY on Domain (and DatabaseManager interface).
- **Infrastructure** depends on Domain and Database libraries.
- **Presentation (`app/api/v1/`)** depends on Application and Pydantic.

---

## 2. Date & Time Standards (`app.core.clock`)

> ⚠️ **STRICT RULE:** Never call `datetime.now()` or `datetime.utcnow()` directly for database models or business records.

Always import and use `app.core.clock`:
- **`now_naive_ist() -> datetime`**:
  Use for all database model timestamps (`created_at`, `updated_at`, `collected_at`).
  *Rationale:* SQLite and PostgreSQL naive comparisons avoid timezone string-offset bugs.
- **`to_naive_ist(dt: datetime) -> datetime`**:
  Use to sanitize any incoming user/client timestamp before processing.
- **`now_ist() -> datetime`**:
  Use only when timezone-aware IST datetime with `+05:30` offset is explicitly required.

---

## 3. Dependency Injection & IoC Container

Never instantiate repositories or handlers directly inside routers. All components must be resolved via the IoC Container:

1. **Repository Registration**:
   Register in `app/modules/configurator.py` $\rightarrow$ `ModuleConfigurator._repo_config()`:
   ```python
   repository = MyModuleRepository(_database)
   container.register(MyModuleRepository, repository)
   ```
2. **Handler Registration**:
   Register in `app/modules/configurator.py` $\rightarrow$ `ModuleConfigurator._handler_config()` via a dedicated classmethod:
   ```python
   @classmethod
   def _mymodule(cls, container: ServiceContainer):
       handler = MyModuleHandler(
           database=container.database,
           repository=container.resolve(MyModuleRepository),
       )
       container.register(MyModuleHandler, handler)
   ```
3. **Router Access Helper**:
   Add static helper in `app/modules/dependencies.py`:
   ```python
   @staticmethod
   def mymodule_handler(request: Request) -> MyModuleHandler:
       return request.app.state.application.container.resolve(MyModuleHandler)
   ```

---

## 4. REST API & Response Envelopes (`app/api/v1/`)

All REST endpoints in `app/api/v1/routers/` must follow consistent envelope structures:

### A. List / Paginated Responses
All list endpoints (`GET /`, `POST /list`) MUST return:
```python
{
    "status": True,
    "code": 200,
    "message": "Records fetched successfully",
    "items": [...],
    "limit": limit,
    "offset": offset,
    "total": total,
    "pages": pages,
    "next_page": next_page,
    "has_more": has_more
}
```
Use the standard `_compute_pagination(total, limit, offset)` helper in the router.

### B. Single Record Responses
Endpoints returning a single record (`GET /{id}`, `POST /`, `PUT /{id}`) MUST return:
```python
{
    "status": True,
    "code": 200,  # or 201 for created
    "message": "Operation completed successfully",
    "data": { ... }
}
```

### C. Serialization
Use `ORJSONResponse` or `jsonable_encoder` for high-throughput endpoints (such as `/sync` and collections).

---

## 5. SQLAlchemy 2.0 Database Models (`infrastructure/models.py`)

1. Models MUST inherit from:
   - `Base`: `app.core.database.base.Base`
   - `UUIDMixin`: Provides standard UUID primary key (`id`)
   - `AuditMixin`: Provides `created_by`, `updated_by`
   - `TimestampMixin` or `AuditMixin`: Provides `created_at`, `updated_at` (using `now_naive_ist`)
   - `SoftDeleteMixin` (when entity supports soft deletion: `is_deleted`, `deleted_at`)
2. Use modern Mapped types:
   ```python
   id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
   code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
   ```
3. All database writes MUST be executed within transactions:
   ```python
   async with self._database.transaction():
       await self._repository.create(entity)
   ```

---

## 6. Authentication & Roles (`CurrentUser`)

1. In authenticated routes, resolve the user from `request.state.user`:
   ```python
   user: CurrentUser | None = getattr(request.state, "user", None)
   if not user:
       raise HTTPException(status_code=401, detail="Unauthorized")
   ```
2. Check roles via `user.role_type` using `Role` enum (`Role.ADMIN`, `Role.MCC`, `Role.VLCC`, `Role.FARMER`).
3. For public endpoints (like `/marketplace`, `/auth/login`, media), register routes in:
   - `public_routes_startswith` in `app/middleware/authentication.py`
   - `public_routes` set in `app/bootstrap/middleware.py`

---

## 7. Python 3.13+ Code Quality & Performance

- **Slots**: Always use `__slots__ = (...)` on Handlers, Services, and `@dataclass(slots=True)` on DTOs and Entities for memory efficiency and speed.
- **Typing**: Use modern union types `T | None`, `list[T]`, `dict[K, V]` (do NOT import `Union`, `List`, `Optional` from `typing`).
- **Pydantic Validation**: Use Pydantic v2 `model_dump(exclude_unset=True, exclude_none=True)` for partial updates.
- **Docstrings & Comments**: Preserve existing docstrings, provide clear module-level docstrings with Python 3.13+ markers.
