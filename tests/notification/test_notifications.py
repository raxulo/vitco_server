"""
Shared push notifications (REQ-76, REQ-77, DECISION-033).

The module every feature uses: device tokens through the real API, `NotificationService` writing the
outbox, the worker against a fake sender, and the FCM HTTP v1 sender against a fake Google.
Nothing here knows about tickets or any other feature.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import delete, update

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.notification.application.handler import DeviceHandler
from app.modules.notification.application.sender import (
    DisabledSender,
    FcmSender,
    SendResult,
    build_sender,
    load_credentials,
)
from app.modules.notification.application.service import NotificationService
from app.modules.notification.application.worker import MAX_ATTEMPTS, PushWorker, backoff
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.domain.exceptions import NotificationValidationException
from app.modules.notification.infrastructure.models import NotificationOutboxModel
from app.modules.notification.infrastructure.repository import NotificationRepository

BASE = "/api/v1/notifications"


def fcm_token() -> str:
    return "fcm-" + uuid4().hex + ":APA91b" + uuid4().hex


@pytest.fixture
async def notify(api, user_factory):
    """The app's own notification parts, with the service switched on (no Firebase credential in tests)."""
    from app.main import app

    container = app.state.application.container
    repository = container.resolve(NotificationRepository)
    # The test database is shared: start every test with an empty outbox so the worker only sees this test's rows
    async with container.database.transaction() as session:
        await session.execute(delete(NotificationOutboxModel))
    return SimpleNamespace(
        database=container.database,
        repository=repository,
        service=NotificationService(repository, enabled=True),
        devices=container.resolve(DeviceHandler),
        user=await user_factory(Role.FARMER),
        user_factory=user_factory,
    )


async def _queue(notify, *, devices=1, **overrides):
    tokens = [fcm_token() for _ in range(devices)]
    message = dict(
        user_id=notify.user, source="payments", type="PAYMENT_RECEIVED",
        title="Payment received", body="₹ 2,450 for 1-15 Nov", reference_id="pay-1", data={"amount": "2450"},
    )
    message.update(overrides)
    async with notify.database.transaction():
        for token in tokens:
            await notify.repository.upsert_token(user_id=notify.user, fcm_token=token, platform="android", app_version=None)
        await notify.service.notify(**message)
    return tokens


async def _rows(notify):
    return await notify.devices.outbox_for(notify.user)


# =========================================================
# DEVICE TOKENS (REQ-76)
# =========================================================

@pytest.mark.parametrize("role", [Role.FARMER, Role.VLCC, Role.MCC, Role.ADMIN, Role.SUPER_ADMIN])
async def test_any_signed_in_app_user_registers_and_removes_devices(api, user_factory, token_for, role):
    from app.main import app

    repository = app.state.application.container.resolve(NotificationRepository)
    database = app.state.application.container.database
    user_id = await user_factory(role)
    headers = token_for(user_id, role)
    token = fcm_token()
    first = await api.post(f"{BASE}/devices", headers=headers, json={"fcm_token": token, "platform": "android", "app_version": "2.4.1"})
    assert first.status_code == 200 and first.json()["data"]["platform"] == "android"
    await api.post(f"{BASE}/devices", headers=headers, json={"fcm_token": fcm_token(), "platform": "ios"})
    again = await api.post(f"{BASE}/devices", headers=headers, json={"fcm_token": token, "platform": "android", "app_version": "2.5.0"})
    assert again.json()["data"]["app_version"] == "2.5.0"
    async with database.transaction():
        assert len(await repository.active_tokens(user_id)) == 2       # two phones; the repeat did not add one

    removed = await api.delete(f"{BASE}/devices/{token}", headers=headers)
    assert removed.status_code == 200 and removed.json()["data"]["removed"] is True
    assert (await api.delete(f"{BASE}/devices/{token}", headers=headers)).json()["data"]["removed"] is False


async def test_a_token_moves_to_whoever_registers_it_last(api, user_factory, token_for):
    from app.main import app

    repository = app.state.application.container.resolve(NotificationRepository)
    database = app.state.application.container.database
    first, second = await user_factory(Role.FARMER), await user_factory(Role.VLCC)
    token = fcm_token()
    await api.post(f"{BASE}/devices", headers=token_for(first, Role.FARMER), json={"fcm_token": token, "platform": "android"})
    await api.post(f"{BASE}/devices", headers=token_for(second, Role.VLCC), json={"fcm_token": token, "platform": "android"})
    async with database.transaction():
        assert await repository.active_tokens(first) == []
        assert [t.fcm_token for t in await repository.active_tokens(second)] == [token]
    # The first user cannot remove what is now someone else's phone
    gone = await api.delete(f"{BASE}/devices/{token}", headers=token_for(first, Role.FARMER))
    assert gone.json()["data"]["removed"] is False


async def test_device_input_is_checked_and_sign_in_is_required(api, user_factory, token_for):
    farmer = token_for(await user_factory(Role.FARMER), Role.FARMER)
    assert (await api.post(f"{BASE}/devices", headers=farmer, json={"fcm_token": fcm_token(), "platform": "windows"})).status_code == 422
    assert (await api.post(f"{BASE}/devices", headers=farmer, json={"fcm_token": "short", "platform": "android"})).status_code == 422
    assert (await api.post(f"{BASE}/devices", json={"fcm_token": fcm_token(), "platform": "android"})).status_code == 401
    # Support staff use the portal only (Phase 25 isolation), so they cannot reach the app API
    staff = token_for(await user_factory(Role.SUPPORT), Role.SUPPORT)
    assert (await api.post(f"{BASE}/devices", headers=staff, json={"fcm_token": fcm_token(), "platform": "android"})).status_code == 403


# =========================================================
# SERVICE: the outbox any module writes to
# =========================================================

async def test_notify_writes_a_short_row_with_source_type_and_reference(notify):
    await _queue(notify, body="x" * 500, title="t" * 300)
    (row,) = await _rows(notify)
    assert (row.source, row.type, row.reference_id) == ("payments", "PAYMENT_RECEIVED", "pay-1")
    assert len(row.title) == 120 and len(row.body) == 180 and row.body.endswith("…")
    assert row.status is NotificationStatus.PENDING and row.skip_if_online is False
    assert row.payload == {"amount": "2450", "source": "payments", "type": "PAYMENT_RECEIVED", "reference_id": "pay-1"}


async def test_notify_checks_the_source_and_type(notify):
    for bad in ({"source": "Payments!"}, {"source": ""}, {"type": " "}):
        with pytest.raises(NotificationValidationException):
            async with notify.database.transaction():
                await notify.service.notify(**{
                    "user_id": notify.user, "source": "payments", "type": "X", "title": "t", "body": "b", **bad,
                })


async def test_notify_many_sends_once_per_user(notify):
    other = await notify.user_factory(Role.FARMER)
    async with notify.database.transaction():
        count = await notify.service.notify_many(
            [notify.user, other, notify.user], source="collections", type="RATE_CHANGED", title="New rates", body="From tomorrow",
        )
    assert count == 2


async def test_nothing_is_written_while_push_is_disabled(notify):
    disabled = NotificationService(notify.repository, enabled=False)
    async with notify.database.transaction():
        assert await disabled.notify(user_id=notify.user, source="payments", type="X", title="t", body="b") is None
    assert await _rows(notify) == []


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="SQLite: the app's pysqlite setup lets a released savepoint commit (pre-existing, see STATE concerns); "
           "verified on PostgreSQL",
)
async def test_the_row_rolls_back_with_the_change_that_asked_for_it(notify):
    with pytest.raises(RuntimeError):
        async with notify.database.transaction():
            async with notify.database.transaction():          # the module's own handler transaction
                await notify.service.notify(user_id=notify.user, source="payments", type="X", title="t", body="b")
            raise RuntimeError("the request failed afterwards")
    assert await _rows(notify) == []


# =========================================================
# WORKER (fake sender)
# =========================================================

class FakeSender:
    enabled = True

    def __init__(self, *results: SendResult) -> None:
        self.results = list(results)
        self.sent: list[tuple[str, str, str, dict]] = []

    async def send(self, token, *, title, body, data):
        self.sent.append((token, title, body, data))
        return self.results.pop(0) if self.results else SendResult(ok=True)

    async def close(self):
        return None


def _worker(notify, sender, *online) -> PushWorker:
    worker = PushWorker(database=notify.database, repository=notify.repository, sender=sender)

    async def presence(user_id):
        return user_id in online

    worker.add_presence(presence)
    return worker


async def _drain(worker: PushWorker) -> None:
    while await worker.run_once():
        pass


async def _due_now(notify):
    async with notify.database.transaction() as session:
        await session.execute(update(NotificationOutboxModel).values(next_attempt_at=now_naive_ist() - timedelta(seconds=1)))


async def test_the_worker_sends_to_every_device_with_the_routing_data(notify):
    tokens = await _queue(notify, devices=2)
    sender = FakeSender()
    await _drain(_worker(notify, sender))
    assert sorted(t for t, *_ in sender.sent) == sorted(tokens)
    title, body, data = sender.sent[0][1:]
    assert title == "Payment received" and body == "₹ 2,450 for 1-15 Nov"
    assert data == {"amount": "2450", "source": "payments", "type": "PAYMENT_RECEIVED", "reference_id": "pay-1"}
    (row,) = await _rows(notify)
    assert row.status is NotificationStatus.SENT and row.sent_at is not None and row.attempts == 1


async def test_online_users_are_skipped_only_when_the_module_asked_for_it(notify):
    await _queue(notify)                                     # e.g. a payment: always sent
    await _queue(notify, devices=0, type="CHAT", skip_if_online=True)
    sender = FakeSender()
    await _drain(_worker(notify, sender, notify.user))
    statuses = {row.type: (row.status, row.last_error) for row in await _rows(notify)}
    assert statuses["PAYMENT_RECEIVED"] == (NotificationStatus.SENT, None)
    assert statuses["CHAT"] == (NotificationStatus.SKIPPED, "user online")


async def test_a_failing_presence_check_counts_as_offline(notify):
    await _queue(notify, skip_if_online=True)
    worker = PushWorker(database=notify.database, repository=notify.repository, sender=FakeSender())

    async def broken(_user_id):
        raise RuntimeError("redis gone")

    worker.add_presence(broken)
    await _drain(worker)
    assert (await _rows(notify))[0].status is NotificationStatus.SENT


async def test_a_temporary_failure_is_retried_later_then_sent(notify):
    await _queue(notify)
    worker = _worker(notify, FakeSender(SendResult(ok=False, retryable=True, error="http 503")))
    await _drain(worker)
    (row,) = await _rows(notify)
    assert row.status is NotificationStatus.PENDING and row.attempts == 1 and row.last_error == "http 503"
    assert row.next_attempt_at > now_naive_ist() and await worker.run_once() == 0
    await _due_now(notify)
    await _drain(worker)
    (row,) = await _rows(notify)
    assert row.status is NotificationStatus.SENT and row.attempts == 2


async def test_it_gives_up_after_five_attempts(notify):
    await _queue(notify)
    worker = _worker(notify, FakeSender(*[SendResult(ok=False, retryable=True, error="timeout")] * MAX_ATTEMPTS))
    for _ in range(MAX_ATTEMPTS):
        await _due_now(notify)
        await _drain(worker)
    (row,) = await _rows(notify)
    assert row.status is NotificationStatus.FAILED and row.attempts == MAX_ATTEMPTS
    assert backoff(1) == timedelta(seconds=30) and backoff(20) == timedelta(minutes=30)


async def test_dead_tokens_are_switched_off(notify):
    dead, alive = await _queue(notify, devices=2)
    sender = FakeSender()

    async def send(token, *, title, body, data):
        sender.sent.append((token, title, body, data))
        return SendResult(ok=False, unregistered=True, error="UNREGISTERED") if token == dead else SendResult(ok=True)

    sender.send = send
    await _drain(_worker(notify, sender))
    async with notify.database.transaction():
        assert [t.fcm_token for t in await notify.repository.active_tokens(notify.user)] == [alive]
    assert (await _rows(notify))[0].status is NotificationStatus.SENT


async def test_no_device_or_only_dead_ones_means_skipped(notify):
    await _queue(notify, devices=0)
    await _queue(notify, devices=1, type="SECOND")
    await _drain(_worker(notify, FakeSender(SendResult(ok=False, unregistered=True, error="UNREGISTERED"))))
    # The first was handled when the second's device already existed; both end skipped without a live device
    assert {row.last_error for row in await _rows(notify)} <= {"no device", "no live device"}
    assert all(row.status is NotificationStatus.SKIPPED for row in await _rows(notify))


async def test_disabled_mode_marks_rows_and_the_worker_does_not_start(notify):
    await _queue(notify)
    worker = _worker(notify, DisabledSender())
    await worker.start()
    assert worker._task is None                               # no credential: no background loop
    await _drain(worker)
    assert (await _rows(notify))[0].status is NotificationStatus.SKIPPED


async def test_rows_left_half_sent_by_a_crash_are_released(notify):
    await _queue(notify)
    async with notify.database.transaction():
        assert len(await notify.repository.claim_due(now=now_naive_ist(), limit=10)) == 1
        assert await notify.repository.claim_due(now=now_naive_ist(), limit=10) == []     # SENDING: not taken twice
        assert await notify.repository.release_stuck(before=now_naive_ist() + timedelta(minutes=1)) == 1
    assert (await _rows(notify))[0].status is NotificationStatus.PENDING


async def test_finished_rows_are_purged_after_their_time(notify):
    await _queue(notify)
    await _drain(_worker(notify, FakeSender()))
    async with notify.database.transaction():
        assert await notify.repository.purge_finished(before=now_naive_ist() - timedelta(days=1)) == 0
        assert await notify.repository.purge_finished(before=now_naive_ist() + timedelta(seconds=5)) >= 1
    assert await _rows(notify) == []


# =========================================================
# FCM HTTP v1 SENDER (fake Google)
# =========================================================

def _credentials():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    return {
        "type": "service_account", "project_id": "quickyee-test", "private_key_id": "k1", "private_key": pem,
        "client_email": "push@quickyee-test.iam.gserviceaccount.com", "token_uri": "https://oauth2.googleapis.com/token",
    }, key.public_key()


def _google(sends: list[httpx.Response], log: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        log.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": f"ya29.{len(log)}", "expires_in": 3600})
        return sends.pop(0)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fcm_sender_signs_a_jwt_and_sends_the_v1_message():
    from jose import jwt

    credentials, public_key = _credentials()
    log: list[httpx.Request] = []
    sender = FcmSender(credentials, client=_google([httpx.Response(200, json={"name": "projects/x/messages/1"})] * 2, log))
    result = await sender.send("device-token", title="Payment received", body="Hello", data={"reference_id": "abc"})
    assert result.ok

    token_request, send_request = log
    form = dict(item.split("=", 1) for item in token_request.content.decode().split("&"))
    claims = jwt.decode(
        form["assertion"],
        public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
        algorithms=["RS256"], audience="https://oauth2.googleapis.com/token",
    )
    assert claims["iss"] == credentials["client_email"] and "firebase.messaging" in claims["scope"]
    assert str(send_request.url) == "https://fcm.googleapis.com/v1/projects/quickyee-test/messages:send"
    assert send_request.headers["authorization"] == "Bearer ya29.1"
    message = json.loads(send_request.content)["message"]
    assert message["token"] == "device-token" and message["notification"] == {"title": "Payment received", "body": "Hello"}
    assert message["data"] == {"reference_id": "abc"}

    await sender.send("device-token", title="t", body="b", data={})
    assert [r.url.host for r in log].count("oauth2.googleapis.com") == 1        # access token reused
    await sender.close()


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(404, json={"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}), "unregistered"),
        (httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}}), "unregistered"),
        (httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}), "retryable"),
        (httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}), "retryable"),
        (httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}}), "failed"),
    ],
    ids=["unregistered", "invalid-token", "unavailable", "quota", "forbidden"],
)
async def test_fcm_errors_are_sorted_into_dead_retry_or_failed(response, expected):
    credentials, _ = _credentials()
    result = await FcmSender(credentials, client=_google([response], [])).send("t", title="t", body="b", data={})
    kind = "unregistered" if result.unregistered else "retryable" if result.retryable else "failed"
    assert not result.ok and kind == expected


async def test_an_expired_access_token_is_renewed_once():
    credentials, _ = _credentials()
    log: list[httpx.Request] = []
    sender = FcmSender(credentials, client=_google([httpx.Response(401), httpx.Response(200, json={})], log))
    assert (await sender.send("t", title="t", body="b", data={})).ok
    assert [r.url.host for r in log].count("oauth2.googleapis.com") == 2


async def test_a_network_error_is_retryable():
    credentials, _ = _credentials()

    def broken(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "x", "expires_in": 3600})
        raise httpx.ConnectError("down")

    result = await FcmSender(credentials, client=httpx.AsyncClient(transport=httpx.MockTransport(broken))).send(
        "t", title="t", body="b", data={},
    )
    assert result.retryable and "ConnectError" in result.error


def test_credentials_come_from_env_or_file_and_bad_ones_disable_push(tmp_path):
    credentials, _ = _credentials()
    assert isinstance(build_sender(), DisabledSender)
    assert isinstance(build_sender(json_text=json.dumps(credentials)), FcmSender)
    path = tmp_path / "firebase.json"
    path.write_text(json.dumps(credentials), encoding="utf-8")
    assert load_credentials(file_path=str(path))["project_id"] == "quickyee-test"
    assert isinstance(build_sender(file_path=str(path)), FcmSender)
    assert isinstance(build_sender(file_path=str(tmp_path / "missing.json")), DisabledSender)
    assert isinstance(build_sender(json_text="{not json"), DisabledSender)
    assert isinstance(build_sender(json_text=json.dumps({"project_id": "x"})), DisabledSender)


# =========================================================
# FCM TOKEN SENT WITH THE APP LOGIN
# =========================================================

async def _login_user(database, role: Role) -> tuple[str, str]:
    """A user with a real password; returns (mobile, password)."""
    from app.modules.administration.infrastructure.models import UserModel
    from app.modules.auth.infrastructure.password import PasswordService

    user_id = uuid4()
    mobile = "9" + str(user_id.int)[-9:]
    async with database.transaction() as session:
        session.add(UserModel(
            id=user_id, name="App User", email=f"{user_id.hex}@quickyee-tests.com", mobile=mobile,
            password_hash=PasswordService().hash("Passw0rd!x"), role=role,
        ))
    return mobile, "Passw0rd!x"


async def test_login_with_an_fcm_token_registers_the_phone(api, notify):
    mobile, password = await _login_user(notify.database, Role.FARMER)
    token = fcm_token()
    response = await api.post("/api/v1/auth/login", json={
        "mobile": mobile, "password": password, "fcm_token": token, "platform": "android", "app_version": "2.4.1",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["push_registered"] is True
    user_id = body["user_id"]
    async with notify.database.transaction():
        devices = await notify.repository.active_tokens(UUID(user_id))
    assert [(d.fcm_token, d.platform, d.app_version) for d in devices] == [(token, "android", "2.4.1")]

    # Logging in again on the same phone does not add a second device
    await api.post("/api/v1/auth/login", json={"mobile": mobile, "password": password, "fcm_token": token, "platform": "android"})
    async with notify.database.transaction():
        assert len(await notify.repository.active_tokens(UUID(user_id))) == 1


async def test_login_without_or_with_a_bad_token_still_logs_in(api, notify):
    mobile, password = await _login_user(notify.database, Role.VLCC)
    plain = await api.post("/api/v1/auth/login", json={"mobile": mobile, "password": password})
    assert plain.status_code == 200 and plain.json()["push_registered"] is False

    bad = await api.post("/api/v1/auth/login", json={"mobile": mobile, "password": password, "fcm_token": "short", "platform": "android"})
    assert bad.status_code == 200 and bad.json()["push_registered"] is False
    wrong_platform = await api.post("/api/v1/auth/login", json={
        "mobile": mobile, "password": password, "fcm_token": fcm_token(), "platform": "windows",
    })
    assert wrong_platform.status_code == 200 and wrong_platform.json()["push_registered"] is False


async def test_a_failed_login_registers_nothing(api, notify):
    mobile, _password = await _login_user(notify.database, Role.FARMER)
    token = fcm_token()
    response = await api.post("/api/v1/auth/login", json={"mobile": mobile, "password": "wrong", "fcm_token": token, "platform": "android"})
    assert response.status_code >= 400
    async with notify.database.transaction() as session:
        from sqlalchemy import func, select
        from app.modules.notification.infrastructure.models import NotificationDeviceTokenModel
        assert await session.scalar(
            select(func.count()).select_from(NotificationDeviceTokenModel).where(NotificationDeviceTokenModel.fcm_token == token)
        ) == 0
