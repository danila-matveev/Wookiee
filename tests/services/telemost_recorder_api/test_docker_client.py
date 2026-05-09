"""Tests for the Docker SDK wrapper used to spawn recorder containers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.docker_client import (
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
