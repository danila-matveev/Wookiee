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


async def docker_ping() -> bool:
    """Best-effort docker daemon liveness check. Returns False on any error.

    Run in a thread because docker-py is sync. Timeout 5s so a stalled
    socket doesn't block the /health endpoint or startup probe.

    Intentionally constructs a fresh client (not the cached one) so a
    previously bad cached connection doesn't poison the answer — and so
    the test suite can patch `docker.from_env` directly.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(lambda: bool(docker.from_env().ping())),
            timeout=5.0,
        )
    except Exception as e:  # noqa: BLE001
        # No exc_info=True — /health polls every ~10s, full stacktrace
        # would spam ~360 entries/hour. Short message is enough to diagnose.
        logger.warning("Docker ping failed: %s", e)
        return False


# Env vars proxied from API container into spawned recorder container.
# Recorder needs Yandex SpeechKit creds + bot display name; everything else
# (DB, Telegram bot token) is API-only.
_RECORDER_ENV_KEYS = (
    "SPEECHKIT_API_KEY",
    "YANDEX_FOLDER_ID",
    "Bitrix_rest_api",  # recorder's speakers.py reads this exact name
    "OPENROUTER_API_KEY",  # recorder uses for LLM speaker resolution
    "TELEMOST_BOT_NAME",
)


def spawn_recorder_container(
    *,
    meeting_id: UUID,
    meeting_url: str,
    data_dir: str,
    headless: bool = False,
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
    """Wait for container to exit (with timeout). Returns dict with keys:
    - exit_code: int (0=success, !=0=container reported failure, -1=other error)
    - logs: str (last 200 lines)
    - timed_out: bool (True iff wait timeout fired and container is likely still running)
    """
    client = _get_client()

    def _wait() -> dict:
        try:
            c = client.containers.get(container_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("monitor_container: container %s not found", container_id)
            return {"exit_code": -1, "logs": str(exc), "timed_out": False}
        try:
            result = c.wait(timeout=timeout_seconds)
            logs = c.logs(tail=200).decode("utf-8", errors="replace")
            return {"exit_code": result["StatusCode"], "logs": logs, "timed_out": False}
        except Exception as exc:  # noqa: BLE001
            # docker SDK raises on read timeout; container is still running.
            # The caller is expected to call stop_container() to clean up.
            logger.warning(
                "monitor_container: wait failed for %s (likely timeout): %s",
                container_id, exc,
            )
            try:
                logs = c.logs(tail=200).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                logs = str(exc)
            return {"exit_code": -1, "logs": logs, "timed_out": True}

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
