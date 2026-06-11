#!/usr/bin/env python3
"""Utility helpers for orchestration scripts.

These helpers call running services by using Docker to run curl inside
the service container network namespace. This avoids requiring host
ports to be published.
"""
from __future__ import annotations

import json
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _run_docker_curl(container: str, url: str, method: str = "GET", json_body: Optional[Dict] = None) -> Dict[str, Any]:
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        f"container:{container}",
        "curlimages/curl:8.4.0",
        "-sS",
        "-X",
        method,
        url,
        "-H",
        "Content-Type: application/json",
    ]

    if json_body is not None:
        payload = json.dumps(json_body, ensure_ascii=False)
        cmd.extend(["-d", payload])

    logger.debug("Running: %s", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        logger.error("Command failed: %s", proc.stderr.strip())
        raise RuntimeError(f"Docker curl failed: {proc.stderr.strip()}")

    try:
        return json.loads(proc.stdout)
    except Exception:
        # Return raw text under 'raw' if not JSON
        return {"raw": proc.stdout}


def copy_to_container(src: Path, container: str, dest: str) -> None:
    """Copy a host file or directory into a container path using docker cp."""
    src = Path(src)
    # Ensure parent directory exists inside the container
    parent = str(Path(dest).parent)
    mkdir_cmd = ["docker", "exec", container, "mkdir", "-p", parent]
    logger.debug("Ensuring container dir: %s", " ".join(shlex.quote(c) for c in mkdir_cmd))
    proc_mkdir = subprocess.run(mkdir_cmd, capture_output=True, text=True)
    if proc_mkdir.returncode != 0:
        logger.error("docker exec mkdir failed: %s", proc_mkdir.stderr.strip())
        raise RuntimeError(f"docker exec mkdir failed: {proc_mkdir.stderr.strip()}")

    cmd = ["docker", "cp", str(src), f"{container}:{dest}"]
    logger.debug("Copying to container: %s", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("docker cp failed: %s", proc.stderr.strip())
        raise RuntimeError(f"docker cp failed: {proc.stderr.strip()}")


def ingest_directory_via_content_pipeline(container: str, directory: str) -> Dict[str, Any]:
    """Call content-pipeline's /ingest/directory endpoint inside its container network."""
    url = "http://localhost:8001/ingest/directory"
    payload = {"directory": directory, "recursive": True, "source": "orchestrator"}
    return _run_docker_curl(container, url, method="POST", json_body=payload)


def generate_pack_via_pack_service(container: str, pack_type: str, grade: Optional[int] = None, subject: Optional[str] = None, chapter: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    url = "http://localhost:8030/packs/generate"
    body: Dict[str, Any] = {"pack_type": pack_type}
    if grade is not None:
        body["grade"] = grade
    if subject is not None:
        body["subject"] = subject
    if chapter is not None:
        body["chapter"] = chapter
    if language is not None:
        body["language"] = language
    return _run_docker_curl(container, url, method="POST", json_body=body)


def validate_pack_via_pack_service(container: str, pack_id: str) -> Dict[str, Any]:
    url = f"http://localhost:8030/packs/{pack_id}/validate"
    return _run_docker_curl(container, url, method="POST", json_body={})


def list_packs_via_pack_service(container: str) -> Dict[str, Any]:
    url = "http://localhost:8030/packs/list"
    return _run_docker_curl(container, url, method="GET")
