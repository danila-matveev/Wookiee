"""Spawn, monitor, and reconcile telemost_recorder containers via Docker SDK.

Mounts host data/telemost into the spawned container so the recorder's
audio.opus + raw_segments.json artefacts land in shared volume that the
API service can read after exit.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional
from uuid import UUID

import docker
from docker.errors import NotFound

logger = logging.getLogger(__name__)

_RECORDER_IMAGE = "telemost_recorder:latest"
_NETWORK = os.getenv("TELEMOST_RECORDER_NETWORK", "n8n-docker-caddy_default")

_client: Optional[docker.DockerClient] = None


def _get_client() -> docker.DockerClient:
    """Return a process-wide Docker client (lazy init)."""
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


# Env vars proxied from API container into spawned recorder container.
# Recorder needs Yandex SpeechKit creds + bot display name; everything else
# (DB, Telegram bot token) is API-only.
_RECORDER_ENV_KEYS = (
    "SPEECHKIT_API_KEY",
    "YANDEX_FOLDER_ID",
    "BITRIX24_WEBHOOK_URL",
    "TELEMOST_BOT_NAME",
)


def spawn_recorder_container(
    *,
    meeting_id: UUID,
    meeting_url: str,
    data_dir: str,
    headless: bool = True,
    max_minutes: Optional[int] = None,
) -> str:
    """Run telemost_recorder:latest detached. Returns container id."""
    client = _get_client()
    cmd = [
        "python",
        "scripts/telemost_record.py",
        "join",
        meeting_url,
        "--meeting-id",
        str(meeting_id),
        "--output-dir",
        f"/app/data/telemost/{meeting_id}",
    ]
    if max_minutes is not None:
        cmd.extend(["--max-minutes", str(max_minutes)])

    container = client.containers.run(
        _RECORDER_IMAGE,
        command=cmd,
        detach=True,
        labels={
            "telemost.meeting_id": str(meeting_id),
            "telemost.role": "recorder",
        },
        volumes={
            data_dir: {"bind": "/app/data/telemost", "mode": "rw"},
        },
        environment={
            "TELEMOST_HEADLESS": "true" if headless else "false",
            **{k: os.environ[k] for k in _RECORDER_ENV_KEYS if k in os.environ},
        },
        network=_NETWORK,
        remove=False,
        name=f"telemost_rec_{str(meeting_id)[:8]}",
    )
    logger.info("Spawned recorder container %s for meeting %s", container.id, meeting_id)
    return container.id


async def monitor_container(container_id: str, timeout_seconds: int) -> dict:
    """Wait for container to exit (with timeout). Returns ``{exit_code, logs}``."""
    client = _get_client()

    def _wait() -> dict:
        try:
            c = client.containers.get(container_id)
            result = c.wait(timeout=timeout_seconds)
            logs = c.logs(tail=200).decode("utf-8", errors="replace")
            return {"exit_code": result["StatusCode"], "logs": logs}
        except Exception as exc:  # noqa: BLE001
            logger.exception("monitor_container failed for %s", container_id)
            return {"exit_code": -1, "logs": str(exc)}

    return await asyncio.to_thread(_wait)


def stop_container(container_id: str) -> None:
    """Stop + remove a container. Idempotent: NotFound is silently swallowed."""
    client = _get_client()
    try:
        c = client.containers.get(container_id)
        c.stop(timeout=10)
        c.remove()
    except NotFound:
        return
    except Exception:  # noqa: BLE001
        logger.exception("stop_container %s failed", container_id)


def list_orphan_containers() -> list[dict]:
    """Return all running containers labelled telemost.meeting_id."""
    client = _get_client()
    containers = client.containers.list(filters={"label": "telemost.meeting_id"})
    return [
        {
            "container_id": c.id,
            "meeting_id": c.labels.get("telemost.meeting_id"),
        }
        for c in containers
    ]
