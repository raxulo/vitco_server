from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CreateSuperAdminCommand:
    name: str
    email: str
    password: str

