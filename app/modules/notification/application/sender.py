"""
Push senders (REQ-77, DECISION-033), shared by every module

`FcmSender` talks to the Firebase Cloud Messaging HTTP v1 API. It signs a short-lived JWT with the
service account's private key, exchanges it for an OAuth access token (cached until shortly before
it expires) and posts one message per device token. No Google SDK is needed.

The credential comes from `FIREBASE_CREDENTIALS_FILE` (a path) or `FIREBASE_CREDENTIALS_JSON` (the JSON
itself), never from the repository. Without either, `build_sender` returns `DisabledSender`, which
sends nothing and only logs, so the rest of the app is unaffected.

Tokens and message text are never logged.

Python 3.13+
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"


@dataclass(slots=True, frozen=True)
class SendResult:
    ok: bool
    unregistered: bool = False      # the token is dead: stop using it
    retryable: bool = False         # try again later (network, quota, server)
    error: str = ""


class PushSender(Protocol):

    @property
    def enabled(self) -> bool: ...

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> SendResult: ...

    async def close(self) -> None: ...


class DisabledSender:
    """Used when no Firebase credential is configured: logs, never sends."""

    enabled = False

    def __init__(self, reason: str = "no Firebase credentials") -> None:
        self.reason = reason

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> SendResult:
        return SendResult(ok=False, error=f"push disabled: {self.reason}")

    async def close(self) -> None:
        return None


class FcmSender:

    enabled = True

    def __init__(self, credentials: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> None:
        for key in ("project_id", "client_email", "private_key"):
            if not credentials.get(key):
                raise ValueError(f"Firebase credential has no {key}")
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=10)
        self._access_token: str | None = None
        self._expires_at = 0.0

    @property
    def project_id(self) -> str:
        return str(self._credentials["project_id"])

    async def _token(self, *, force: bool = False) -> str:
        if not force and self._access_token and time.time() < self._expires_at - 300:
            return self._access_token
        from jose import jwt

        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self._credentials["client_email"],
                "scope": SCOPE,
                "aud": self._credentials.get("token_uri") or TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            self._credentials["private_key"],
            algorithm="RS256",
            headers={"kid": self._credentials.get("private_key_id", "")} if self._credentials.get("private_key_id") else None,
        )
        response = await self._client.post(
            self._credentials.get("token_uri") or TOKEN_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        response.raise_for_status()
        body = response.json()
        self._access_token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 3600))
        return self._access_token

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> SendResult:
        message = {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": {key: str(value) for key, value in data.items()},
                "android": {"priority": "high"},
                "apns": {"payload": {"aps": {"sound": "default"}}},
            }
        }
        try:
            for attempt in (1, 2):
                access = await self._token(force=attempt == 2)
                response = await self._client.post(
                    SEND_URL.format(project=self.project_id), json=message,
                    headers={"Authorization": f"Bearer {access}"},
                )
                if response.status_code == 401 and attempt == 1:
                    continue                          # token revoked or expired early: get a new one once
                return self._result(response)
        except httpx.HTTPError as exc:
            return SendResult(ok=False, retryable=True, error=f"network: {type(exc).__name__}")
        return SendResult(ok=False, retryable=True, error="unauthorized")

    @staticmethod
    def _result(response: httpx.Response) -> SendResult:
        if response.status_code == 200:
            return SendResult(ok=True)
        code = ""
        try:
            error = response.json().get("error", {})
            code = error.get("status", "")
            for detail in error.get("details", []) or []:
                code = detail.get("errorCode") or code
        except ValueError:
            pass
        if response.status_code == 404 or code in {"UNREGISTERED", "SENDER_ID_MISMATCH"}:
            return SendResult(ok=False, unregistered=True, error=code or "unregistered")
        if response.status_code == 400 and code == "INVALID_ARGUMENT":
            return SendResult(ok=False, unregistered=True, error="invalid token")
        if response.status_code == 429 or response.status_code >= 500:
            return SendResult(ok=False, retryable=True, error=code or f"http {response.status_code}")
        return SendResult(ok=False, error=code or f"http {response.status_code}")

    async def close(self) -> None:
        await self._client.aclose()


def load_credentials(file_path: str = "", json_text: str = "") -> dict[str, Any] | None:
    """The service-account JSON from an environment value or a file, or None when neither is set."""
    if json_text and json_text.strip():
        return json.loads(json_text)
    if file_path and file_path.strip():
        return json.loads(Path(file_path.strip()).read_text(encoding="utf-8"))
    return None


def build_sender(file_path: str = "", json_text: str = "") -> PushSender:
    try:
        credentials = load_credentials(file_path, json_text)
    except Exception as exc:
        logger.error("Firebase credential could not be read (%s); push notifications are disabled.", type(exc).__name__)
        return DisabledSender("credential could not be read")
    if credentials is None:
        logger.info("No Firebase credential configured; push notifications are disabled.")
        return DisabledSender()
    try:
        return FcmSender(credentials)
    except ValueError as exc:
        logger.error("Firebase credential is incomplete (%s); push notifications are disabled.", exc)
        return DisabledSender("credential incomplete")
