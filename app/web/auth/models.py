"""
Auth Web ViewModels

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field


__all__ = (
    "LoginViewModel",
)

@dataclass(
    slots=True,
    frozen=True,
    kw_only=True,
)
class LoginViewModel:
    title: str
    error: str | None = None
    email: str = ""