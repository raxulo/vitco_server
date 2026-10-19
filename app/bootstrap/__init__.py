"""
Enterprise Bootstrap Package.

The bootstrap package is responsible for assembling the FastAPI
application and registering all platform components.

Responsibilities
----------------
- Application creation
- Application builder
- Lifespan configuration
- Router registration
- Middleware registration
- Exception handler registration
- OpenAPI configuration
- Health endpoint registration

Business logic MUST NOT be implemented in this package.
"""

from app.bootstrap.application import create_application

__all__ = (
    "create_application",
)