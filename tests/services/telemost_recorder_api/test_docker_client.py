"""Tests for the Docker SDK wrapper used to spawn recorder containers."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.docker_client import (
    docker_ping,
    list_orphan_containers,
    monitor_container,
    spawn_recorder_container,
    stop_container,
)


def test_spawn_passes_meeting_id_label_and_volume():
    captured: dict = {}

    def fake_run(image, **kwargs):
        captured["image"] = image
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.id = "container_abc"
        return m

    fake_client = MagicMock()
    fake_client.containers.run = fake_run

    meeting_id = uuid4()
    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ):
        cid = spawn_recorder_container(
            meeting_id=meeting_id,
            meeting_url="https://telemost.yandex.ru/j/abc",
            data_dir="/app/data/telemost",
        )

    assert cid == "container_abc"
    assert captured["image"] == "telemost_recorder:latest"
    assert captured["kwargs"]["labels"]["telemost.meeting_id"] == str(meeting_id)
    assert captured["kwargs"]["detach"] is True
    cmd = captured["kwargs"]["command"]
    assert "join" in cmd
    assert "https://telemost.yandex.ru/j/abc" in cmd
    assert "--meeting-id" in cmd
    assert str(meeting_id) in cmd
    assert "--output-dir" in cmd
    assert any("/app/data/telemost" in v for v in captured["kwargs"]["volumes"])


@pytest.mark.asyncio
async def test_monitor_returns_exit_code():
    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"ok\n"

    fake_client = MagicMock()
    fake_client.containers.get.return_value = container

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ):
        result = await monitor_container("container_abc", timeout_seconds=300)

    assert result["exit_code"] == 0
    assert "ok" in result["logs"]
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_monitor_handles_timeout():
    """When wait raises (timeout/error), monitor returns exit_code=-1 and timed_out=True."""
    container = MagicMock()
    container.wait.side_effect = Exception("read timeout")
    container.logs.return_value = b"partial logs\n"

    fake_client = MagicMock()
    fake_client.containers.get.return_value = container

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ):
        result = await monitor_container("container_xyz", timeout_seconds=1)

    assert result["exit_code"] == -1
    assert result["timed_out"] is True


def test_spawn_mounts_storage_state_when_path_exists(tmp_path):
    """When TELEMOST_STORAGE_STATE_PATH points to an existing file, the recorder
    container gets a read-only mount + the env var pointing at the in-container
    path, so Playwright loads it as authenticated context."""
    storage_state_file = tmp_path / "storage_state.json"
    storage_state_file.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    captured: dict = {}

    def fake_run(image, **kwargs):
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.id = "container_with_state"
        return m

    fake_client = MagicMock()
    fake_client.containers.run = fake_run

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ), patch(
        "services.telemost_recorder_api.docker_client.TELEMOST_STORAGE_STATE_PATH",
        str(storage_state_file),
    ):
        spawn_recorder_container(
            meeting_id=uuid4(),
            meeting_url="https://telemost.yandex.ru/j/abc",
            data_dir="/app/data/telemost",
        )

    volumes = captured["kwargs"]["volumes"]
    assert str(storage_state_file) in volumes, "storage_state file must be bind-mounted"
    bind_info = volumes[str(storage_state_file)]
    assert bind_info["mode"] == "ro", "storage_state must be read-only"
    assert bind_info["bind"] == "/app/data/telemost_storage_state.json"
    env = captured["kwargs"]["environment"]
    assert env["TELEMOST_STORAGE_STATE_PATH"] == "/app/data/telemost_storage_state.json"


def test_spawn_falls_back_to_guest_when_storage_state_missing(tmp_path, caplog):
    """Configured path that doesn't exist must log a warning and fall back to
    guest mode (no mount, no env). A half-rotated cookie must not silently kill
    all recordings."""
    missing_file = tmp_path / "does_not_exist.json"
    captured: dict = {}

    def fake_run(image, **kwargs):
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.id = "container_guest"
        return m

    fake_client = MagicMock()
    fake_client.containers.run = fake_run

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ), patch(
        "services.telemost_recorder_api.docker_client.TELEMOST_STORAGE_STATE_PATH",
        str(missing_file),
    ), caplog.at_level("WARNING"):
        spawn_recorder_container(
            meeting_id=uuid4(),
            meeting_url="https://telemost.yandex.ru/j/abc",
            data_dir="/app/data/telemost",
        )

    volumes = captured["kwargs"]["volumes"]
    assert str(missing_file) not in volumes
    env = captured["kwargs"]["environment"]
    assert "TELEMOST_STORAGE_STATE_PATH" not in env
    assert any("falling back to guest mode" in r.message for r in caplog.records)


def test_spawn_guest_mode_when_storage_state_unset():
    """No env var set = pure guest mode (legacy behaviour preserved)."""
    captured: dict = {}

    def fake_run(image, **kwargs):
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.id = "container_guest"
        return m

    fake_client = MagicMock()
    fake_client.containers.run = fake_run

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ), patch(
        "services.telemost_recorder_api.docker_client.TELEMOST_STORAGE_STATE_PATH",
        "",
    ):
        spawn_recorder_container(
            meeting_id=uuid4(),
            meeting_url="https://telemost.yandex.ru/j/abc",
            data_dir="/app/data/telemost",
        )

    env = captured["kwargs"]["environment"]
    assert "TELEMOST_STORAGE_STATE_PATH" not in env


def test_list_orphan_containers():
    c1 = MagicMock()
    c1.id = "container_1"
    c1.labels = {"telemost.meeting_id": "abc"}
    c2 = MagicMock()
    c2.id = "container_2"
    c2.labels = {"telemost.meeting_id": "xyz"}
    fake_client = MagicMock()
    fake_client.containers.list.return_value = [c1, c2]

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ):
        orphans = list_orphan_containers()

    assert {o["meeting_id"] for o in orphans} == {"abc", "xyz"}
    assert {o["container_id"] for o in orphans} == {"container_1", "container_2"}


def test_stop_container_swallows_not_found():
    """If the container is already gone, stop_container must not raise."""
    from docker.errors import NotFound

    fake_client = MagicMock()
    fake_client.containers.get.side_effect = NotFound("not found")

    with patch(
        "services.telemost_recorder_api.docker_client._get_client",
        return_value=fake_client,
    ):
        stop_container("missing_container")  # must not raise


@pytest.mark.asyncio
async def test_docker_ping_returns_true_when_reachable():
    """When docker.from_env().ping() returns True, docker_ping must return True."""
    fake_client = MagicMock()
    fake_client.ping.return_value = True

    with patch(
        "services.telemost_recorder_api.docker_client.docker.from_env",
        return_value=fake_client,
    ):
        result = await docker_ping()

    assert result is True


@pytest.mark.asyncio
async def test_docker_ping_returns_false_on_exception():
    """When docker.from_env() raises (sock missing/timeout), docker_ping returns False."""
    from docker.errors import DockerException

    with patch(
        "services.telemost_recorder_api.docker_client.docker.from_env",
        side_effect=DockerException("docker.sock not reachable"),
    ):
        result = await docker_ping()

    assert result is False


@pytest.mark.asyncio
async def test_docker_ping_returns_false_on_timeout(monkeypatch):
    """When docker.ping() hangs longer than 5s, docker_ping returns False
    without waiting forever."""
    fake_client = MagicMock()
    # Simulate hang — synchronous sleep inside the thread executor.
    fake_client.ping.side_effect = lambda: time.sleep(10)
    monkeypatch.setattr(
        "services.telemost_recorder_api.docker_client.docker.from_env",
        lambda: fake_client,
    )
    # Bound the test itself so a regression doesn't hang CI for 10s.
    result = await asyncio.wait_for(docker_ping(), timeout=7)
    assert result is False
