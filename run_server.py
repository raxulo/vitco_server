"""
Quickyee - single-file server entry point.

This is the script PyInstaller freezes (see quickyee.spec). Unlike the dev
command `uvicorn app.main:app --reload`, it runs uvicorn in-process with a
single worker and no reloader, which is what a frozen executable needs.

HOST / PORT are read from .env (next to the executable); defaults 0.0.0.0:8600.

If the server is already running on that port, starting a second copy does not
crash with a traceback: it prints a clear message and exits.

Python 3.13+
"""

from __future__ import annotations

import multiprocessing
import socket
import sys


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on host:port (server already up)."""
    # 0.0.0.0 means "all interfaces"; probe it on the loopback address
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            return sock.connect_ex((probe_host, port)) == 0
    except OSError:
        return False


def _pause_if_double_clicked() -> None:
    """Keep a double-clicked Windows window open so the message is readable."""
    if (
        sys.platform.startswith("win")
        and getattr(sys, "frozen", False)
        and sys.stdin is not None
        and sys.stdin.isatty()
    ):
        try:
            input("Press Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass


def main() -> None:
    import uvicorn

    from app.config.settings import settings
    from app.main import app

    host = getattr(settings, "HOST", "0.0.0.0")
    port = int(getattr(settings, "PORT", 8600))

    # Already running? Don't start a second copy.
    if _port_in_use(host, port):
        print(
            f"Quickyee is already running on port {port}. "
            f"A second copy was not started.\n"
            f"Stop the running one first (Ctrl+C in its window, or close it) "
            f"to start again."
        )
        _pause_if_double_clicked()
        raise SystemExit(1)

    print(f"Quickyee server starting on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        uvicorn.run(app, host=host, port=port, workers=1)
    except OSError as exc:
        # Backstop: the port was taken in the moment between the check and bind
        print(
            f"Could not start Quickyee on port {port}: {exc}\n"
            f"It is most likely already running."
        )
        _pause_if_double_clicked()
        raise SystemExit(1)


if __name__ == "__main__":
    # Required so a frozen build does not re-launch itself when any library
    # starts a helper process.
    multiprocessing.freeze_support()
    main()
