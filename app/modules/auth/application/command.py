from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class RegisterCommand:
    email: str
    password: str