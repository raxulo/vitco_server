"""
Create .env from .env.example on first setup (used by setup.bat / setup.sh).

- An existing .env is never touched.
- SECRET_KEY gets a fresh random value.

Python 3.13+
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
TEMPLATE = ROOT / ".env.example"


def main() -> int:
    if ENV_FILE.exists():
        print(".env already exists - left unchanged.")
        return 0
    if not TEMPLATE.exists():
        print("[ERROR] .env.example not found.", file=sys.stderr)
        return 1

    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if line.startswith("SECRET_KEY="):
            line = f"SECRET_KEY={secrets.token_urlsafe(48)}"
        lines.append(line)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(".env created with a random SECRET_KEY.")
    print("Set ADMIN_NAME / ADMIN_EMAIL / ADMIN_PASSWORD in .env before the first start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
