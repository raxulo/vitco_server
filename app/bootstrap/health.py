"""
RealTimeTransfer
================

Bootstrap Module: Health Monitoring

Exposes readiness and liveness endpoints for diagnostics.

Python 3.13+
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def register_health_endpoints(app: FastAPI) -> None:
    """
    Exposes /healthz endpoint.
    """
    @app.get("/healthz", tags=["Infrastructure"])
    async def health_check():
        """
        Operational database status and metrics diagnostics.
        """
        state = app.state.application
        db_health = {"connected": False, "message": "Database is not initialized"}
        
        database = state.container.database
        if database:
            try:
                db_health = await database.health()
            except Exception as e:
                db_health = {"connected": False, "message": str(e)}

        is_healthy = db_health.get("connected", False)
        status_code = 200 if is_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "unhealthy",
                "uptime_seconds": round(state.uptime, 2),
                "app_status": state.status,
                "database": db_health,
                "metadata": state.metadata
            }
        )
