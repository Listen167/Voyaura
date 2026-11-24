"""Run real browser/HTTP acceptance against a fresh, separate local test database.

No personal profile/database is read or modified. No cloud calls. Test records are
explicitly labelled fixtures. Logs stay under ignored .local; no token is printed.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Test service exited; inspect its local log.")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Timed out starting isolated test services.")


def main() -> int:
    folder = ROOT / ".local" / ("e2e-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    api_port, web_port = free_port(), free_port()
    while web_port == api_port:
        web_port = free_port()
    token = secrets.token_urlsafe(32)
    env = {
        **os.environ,
        "VOYAURA_ENVIRONMENT": "local",
        "VOYAURA_DATABASE_URL": "sqlite:///" + (folder / "test.db").as_posix(),
        "VOYAURA_AUTH_TOKEN": token,
        "VOYAURA_AUTH_USERNAME": "AuroraRovella",
        "VOYAURA_AMAP_WEB_KEY": "",
        "VOYAURA_AMAP_WEB_PRIVATE_KEY": "",
        "VOYAURA_AGENT_LLM_ENABLED": "false",
        "VOYAURA_AGENT_LLM_API_KEY": "",
        "VOYAURA_IMAGE_PROVIDER": "disabled",
        "VITE_AMAP_KEY": "",
        "VITE_AMAP_SECURITY_CODE": "",
        "VITE_ENABLE_PLANNER_PRACTICE": "true",
        "VITE_API_BASE_URL": "/api/v1",
        "VOYAURA_DEV_API_URL": f"http://127.0.0.1:{api_port}",
        "VOYAURA_E2E_TOKEN": token,
        "VOYAURA_E2E_API_URL": f"http://127.0.0.1:{api_port}/api/v1",
        "VOYAURA_E2E_WEB_URL": f"http://127.0.0.1:{web_port}",
        "VOYAURA_CORS_ORIGINS": f"http://127.0.0.1:{web_port}",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT / "api",
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.seed"], cwd=ROOT / "api", env=env, check=True
    )
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    node = shutil.which("node")
    if npm is None or node is None:
        raise RuntimeError("Node/npm are required; run npm ci in web first.")
    processes = []
    logs = []
    try:
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                ROOT / "api",
                "api.log",
            ),
            (
                [
                    node,
                    str(ROOT / "web/node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--strictPort",
                    "--port",
                    str(web_port),
                ],
                ROOT / "web",
                "web.log",
            ),
        ]
        for command, cwd, name in commands:
            log = (folder / name).open("w", encoding="utf-8")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT
                )
            )
        wait_ready(f"http://127.0.0.1:{api_port}/health", processes[0])
        wait_ready(f"http://127.0.0.1:{web_port}/", processes[1])
        print(
            "Running isolated browser acceptance; fixtures are not real travel.",
            flush=True,
        )
        command = [npm, "run", "test:e2e"]
        if sys.argv[1:]:
            command.extend(["--", *sys.argv[1:]])
        return subprocess.call(command, cwd=ROOT / "web", env=env)
    finally:
        # Only the exact two children launched by this invocation are terminated.
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        for log in logs:
            log.close()
        print("Isolated test evidence:", folder)


if __name__ == "__main__":
    raise SystemExit(main())
