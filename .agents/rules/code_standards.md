# Quickyee Workspace Coding Standards

These rules are automatically loaded by Antigravity for all work in the Quickyee workspace:

1. **Clean Architecture & DDD**: All module additions must have `domain/`, `infrastructure/`, and `application/` separation.
2. **Clock Convention**: Always use `app.core.clock` (`now_naive_ist()`, `to_naive_ist()`). Never use raw `datetime.now()` for database persistence.
3. **IoC Container**: Repositories & Handlers must be registered in `app/modules/configurator.py` and accessed via `GetHandler.<name>_handler(request)` in `app/modules/dependencies.py`.
4. **Standard Response Envelopes**:
   - List APIs: `{ status, code, message, items, limit, offset, total, pages, next_page, has_more }`
   - Single item APIs: `{ status, code, message, data }`
5. **Python 3.13+ Performance**:
   - Explicit `__slots__` on classes and handlers.
   - `@dataclass(slots=True, kw_only=True)` on entities, commands, and DTOs.
   - Modern union types `T | None`.
   - `model_dump(exclude_unset=True, exclude_none=True)` on Pydantic v2 schemas.
