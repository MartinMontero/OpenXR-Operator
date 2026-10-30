"""Web UI tests (M6 security shape + D-14 approval cards in the browser).

Real HTTP through Flask's test client, real agent loop in a worker thread,
fake engine and fake model. Assertions check the security gates (token,
Origin, CSP), the plain-language card, and what actually reaches the engine.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from openxr_operator.agent import AgentLoop
from openxr_operator.approval import ApprovalGate
from openxr_operator.artifacts import ArtifactWriter
from openxr_operator.auditlog import AuditLog
from openxr_operator.ui.app import create_app
from openxr_operator.ui.runtime import UIRuntime
from tests.test_agent import FINISH, SET_RED, FakeBackend
from tests.test_godot_driver import FakeEngine, _capture_reply, _driver

ORIGIN = {"Origin": "http://127.0.0.1:5000"}


@pytest.fixture
def engine(tmp_path: Path):
    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(png)
    e = FakeEngine(capture=_capture_reply(png))
    yield e
    e.stop()


def _runtime(engine: FakeEngine, tmp_path: Path, actions: list[dict[str, Any]]) -> UIRuntime:
    capabilities = frozenset({"set_property"})
    driver = _driver(engine, capabilities=capabilities, capture_tier="t3")
    loop = AgentLoop(
        driver,
        FakeBackend(actions),
        ApprovalGate(),
        AuditLog(tmp_path / "runs" / "audit.jsonl"),
        ArtifactWriter(tmp_path / "runs", flow_name="ui"),
        project_root=tmp_path,
        capabilities=capabilities,
    )
    return UIRuntime(loop)


def _client(runtime: UIRuntime):  # type: ignore[no-untyped-def]
    app = create_app(runtime, ui_token="secret")
    app.config["TESTING"] = True
    return app.test_client()


def _status(client: Any) -> dict[str, Any]:
    return client.get("/status?token=secret").get_json()


def _wait_for(client: Any, predicate, timeout: float = 8.0) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    status = _status(client)
    while time.monotonic() < deadline:
        if predicate(status):
            return status
        time.sleep(0.05)  # test-side polling (the no-sleep rule is product code)
        status = _status(client)
    raise AssertionError(f"condition not met within {timeout}s: {status}")


def test_token_required(engine: FakeEngine, tmp_path: Path) -> None:
    client = _client(_runtime(engine, tmp_path, [FINISH]))
    assert client.get("/").status_code == 401
    assert client.get("/?token=wrong").status_code == 401
    ok = client.get("/?token=secret")
    assert ok.status_code == 200
    assert b"No task yet" in ok.data  # empty state


def test_post_requires_origin_allowlist(engine: FakeEngine, tmp_path: Path) -> None:
    client = _client(_runtime(engine, tmp_path, [FINISH]))
    data = {"token": "secret", "task": "x"}
    assert client.post("/task", data=data).status_code == 403  # no Origin
    bad = dict(ORIGIN, Origin="https://evil.example")
    assert client.post("/task", data=data, headers=bad).status_code == 403
    assert client.post("/task", data=data, headers=ORIGIN).status_code == 302


def test_security_headers_and_no_third_party_origins(
    engine: FakeEngine, tmp_path: Path
) -> None:
    client = _client(_runtime(engine, tmp_path, [FINISH]))
    response = client.get("/?token=secret")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "cdn" not in csp
    assert response.headers["X-Frame-Options"] == "DENY"


def test_approval_card_plain_language_and_approve_executes(
    engine: FakeEngine, tmp_path: Path
) -> None:
    client = _client(_runtime(engine, tmp_path, [SET_RED, FINISH]))
    client.post("/task", data={"token": "secret", "task": "make it red"}, headers=ORIGIN)
    status = _wait_for(client, lambda s: s["pending"])
    request_id = status["pending"][0]

    page = client.get("/?token=secret").data.decode()
    assert "Change a property in your scene" in page  # D-14 plain language
    assert "its words, not verified" in page  # rationale is an untrusted quote
    assert "StatusLabel" in page

    response = client.post(
        "/approve",
        data={"token": "secret", "id": request_id, "approved": "1"},
        headers=ORIGIN,
    )
    assert response.status_code == 302
    _wait_for(client, lambda s: s["state"] == "done")
    assert any(m.get("cmd") == "set_property" for m in engine.received)
    assert "Label is red." in client.get("/?token=secret").data.decode()


def test_reject_never_reaches_engine(engine: FakeEngine, tmp_path: Path) -> None:
    client = _client(_runtime(engine, tmp_path, [SET_RED, FINISH]))
    client.post("/task", data={"token": "secret", "task": "make it red"}, headers=ORIGIN)
    status = _wait_for(client, lambda s: s["pending"])
    client.post(
        "/approve",
        data={"token": "secret", "id": status["pending"][0], "approved": "0"},
        headers=ORIGIN,
    )
    _wait_for(client, lambda s: s["state"] == "done")
    assert not any(m.get("cmd") == "set_property" for m in engine.received)


def test_assets_vendored_with_visible_focus(engine: FakeEngine, tmp_path: Path) -> None:
    client = _client(_runtime(engine, tmp_path, [FINISH]))
    css = client.get("/static/style.css?token=secret")
    assert css.status_code == 200
    assert b"focus-visible" in css.data
