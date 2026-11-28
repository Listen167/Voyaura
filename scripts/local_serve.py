"""Run one localhost-only service using the isolated local profile."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from local_setup import ROOT, read_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["api", "web"])
    args = parser.parse_args()
    profile = read_profile()
    env = {**os.environ, **profile}
    if args.service == "api":
        env["VOYAURA_DEEPSEEK_API_KEY"] = profile.get("VOYAURA_DEEPSEEK_API_KEY", "")
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            profile["VOYAURA_LOCAL_API_PORT"],
        ]
        workdir = ROOT / "api"
    else:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm is None:
            raise SystemExit("npm is not installed.")
        env["VOYAURA_DEV_API_URL"] = (
            "http://127.0.0.1:" + profile["VOYAURA_LOCAL_API_PORT"]
        )
        env["VITE_API_BASE_URL"] = "/api/v1"
        command = [
            npm,
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--strictPort",
            "--port",
            profile["VOYAURA_LOCAL_WEB_PORT"],
        ]
        workdir = ROOT / "web"
    raise SystemExit(subprocess.call(command, cwd=workdir, env=env))


if __name__ == "__main__":
    main()
