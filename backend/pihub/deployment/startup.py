"""
Deployment Automation & Startup Recovery Service

Handles:
- systemd integration
- Docker recovery coordination
- startup validation
- deployment diagnostics
- failed service restart handling
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


class StartupValidator:
    """Validate deployment readiness at startup"""

    def __init__(self, checks_dir: Path | None = None) -> None:
        self.checks_dir = checks_dir or Path("/storage/startup_checks")
        self.checks_dir.mkdir(parents=True, exist_ok=True)
        self.last_check_time = 0
        self.check_results: dict[str, dict[str, Any]] = {}

    def check_docker_available(self) -> dict[str, Any]:
        """Check if Docker is available"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5,
            )
            return {
                "check": "docker_available",
                "status": "ok" if result.returncode == 0 else "failed",
                "timestamp": int(time.time()),
            }
        except Exception as e:
            return {
                "check": "docker_available",
                "status": "failed",
                "error": str(e),
                "timestamp": int(time.time()),
            }

    def check_docker_daemon(self) -> dict[str, Any]:
        """Check if Docker daemon is running"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "docker"],
                capture_output=True,
                timeout=5,
            )
            return {
                "check": "docker_daemon",
                "status": "ok" if result.returncode == 0 else "failed",
                "timestamp": int(time.time()),
            }
        except Exception as e:
            return {
                "check": "docker_daemon",
                "status": "failed",
                "error": str(e),
                "timestamp": int(time.time()),
            }

    def check_pihub_database(self) -> dict[str, Any]:
        """Check if PiHub database is accessible"""
        import sqlite3

        try:
            db_path = Path("/storage/pihub.sqlite3")
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("select 1 from classroom limit 1")
                conn.close()
                return {
                    "check": "pihub_database",
                    "status": "ok",
                    "timestamp": int(time.time()),
                }
            else:
                return {
                    "check": "pihub_database",
                    "status": "warning",
                    "detail": "database_not_found",
                    "timestamp": int(time.time()),
                }
        except Exception as e:
            return {
                "check": "pihub_database",
                "status": "failed",
                "error": str(e),
                "timestamp": int(time.time()),
            }

    def check_pihub_storage(self) -> dict[str, Any]:
        """Check if PiHub storage directories exist"""
        dirs_to_check = [
            Path("/storage"),
            Path("/packs"),
            Path("/cache"),
            Path("/logs"),
        ]

        all_exist = all(d.exists() for d in dirs_to_check)
        return {
            "check": "pihub_storage",
            "status": "ok" if all_exist else "warning",
            "directories": {str(d): d.exists() for d in dirs_to_check},
            "timestamp": int(time.time()),
        }

    def run_startup_checks(self) -> dict[str, Any]:
        """Run all startup validation checks"""
        checks = [
            self.check_docker_available,
            self.check_docker_daemon,
            self.check_pihub_database,
            self.check_pihub_storage,
        ]

        results = {}
        for check_fn in checks:
            result = check_fn()
            results[result["check"]] = result

        self.check_results = results
        self.last_check_time = int(time.time())

        return {
            "startup_ready": all(r["status"] in ("ok", "warning") for r in results.values()),
            "checks": results,
            "timestamp": int(time.time()),
        }


class DockerRecovery:
    """Docker service recovery coordination"""

    def __init__(self) -> None:
        self.recovery_history: list[dict[str, Any]] = []

    def check_container_status(self, container_name: str) -> dict[str, Any]:
        """Check if container is running"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.State}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = result.stdout.strip()
            return {
                "container": container_name,
                "running": state == "running",
                "state": state,
                "timestamp": int(time.time()),
            }
        except Exception as e:
            return {
                "container": container_name,
                "running": False,
                "error": str(e),
                "timestamp": int(time.time()),
            }

    def restart_container(self, container_name: str) -> dict[str, Any]:
        """Restart a failed container"""
        try:
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                timeout=30,
            )
            success = result.returncode == 0

            record = {
                "action": "restart",
                "container": container_name,
                "success": success,
                "timestamp": int(time.time()),
            }
            self.recovery_history.append(record)

            return record
        except Exception as e:
            record = {
                "action": "restart",
                "container": container_name,
                "success": False,
                "error": str(e),
                "timestamp": int(time.time()),
            }
            self.recovery_history.append(record)
            return record

    def ensure_container_running(self, container_name: str) -> bool:
        """Ensure container is running, restart if needed"""
        status = self.check_container_status(container_name)
        if not status["running"]:
            result = self.restart_container(container_name)
            return result["success"]
        return True

    def recovery_status(self) -> dict[str, Any]:
        """Get recovery history and status"""
        successful = sum(1 for r in self.recovery_history if r.get("success"))
        failed = len(self.recovery_history) - successful

        return {
            "total_recovery_attempts": len(self.recovery_history),
            "successful": successful,
            "failed": failed,
            "recent": self.recovery_history[-10:] if self.recovery_history else [],
        }


class DeploymentAutomation:
    """Coordinate deployment automation and recovery"""

    def __init__(self) -> None:
        self.validator = StartupValidator()
        self.docker_recovery = DockerRecovery()
        self.containers = ["qdrant", "content-pipeline", "gateway", "inference-service", "pihub", "nginx"]

    def validate_deployment(self) -> dict[str, Any]:
        """Run full deployment validation"""
        return self.validator.run_startup_checks()

    def ensure_all_containers_running(self) -> dict[str, Any]:
        """Ensure all required containers are running"""
        results = {}
        for container in self.containers:
            results[container] = self.docker_recovery.ensure_container_running(container)

        return {
            "all_running": all(results.values()),
            "containers": results,
            "recovery_status": self.docker_recovery.recovery_status(),
        }

    def get_deployment_status(self) -> dict[str, Any]:
        """Get overall deployment status"""
        validation = self.validate_deployment()
        container_status = {c: self.docker_recovery.check_container_status(c) for c in self.containers}
        recovery = self.docker_recovery.recovery_status()

        return {
            "validation": validation,
            "containers": container_status,
            "recovery": recovery,
            "timestamp": int(time.time()),
        }
