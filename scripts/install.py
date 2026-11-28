"""Install locked Voyaura dependencies and initialize a local demo."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
WEB = ROOT / "web"
VENV = API / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(label: str, command: list[str], cwd: Path) -> None:
    print(label, flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies-only", action="store_true", help="Skip the local SQLite demo.")
    parser.add_argument("--api-port", type=int, default=8018)
    parser.add_argument("--web-port", type=int, default=5188)
    args = parser.parse_args()

    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        parser.error("Use Python 3.11, 3.12 or 3.13. Python 3.12 is recommended.")
    if not all(1024 <= port <= 65535 for port in (args.api_port, args.web_port)):
        parser.error("API and web ports must be in the range 1024–65535.")
    if args.api_port == args.web_port:
        parser.error("API and web ports must be different.")

    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        parser.error("Install Node.js 24 LTS and npm, then rerun this command.")
    node_major = int(subprocess.check_output([node, "--version"], text=True).strip().lstrip("v").split(".")[0])
    if node_major < 24:
        parser.error("Use Node.js 24 LTS for the frontend toolchain.")

    uv = shutil.which("uv")
    if not PYTHON.exists():
        create_env = [uv, "venv", "--python", sys.executable, str(VENV)] if uv else [
            sys.executable, "-m", "venv", str(VENV),
        ]
        run("Creating API virtual environment", create_env, ROOT)
    elif not (VENV / "pyvenv.cfg").exists():
        parser.error("api/.venv is not a virtual environment.")

    locked = ["--require-hashes", "-r", "requirements-dev.lock"]
    if uv:
        run("Installing locked Python dependencies", [
            uv, "pip", "install", "--python", str(PYTHON), *locked,
        ], API)
    else:
        run("Checking virtual environment pip", [str(PYTHON), "-m", "ensurepip"], API)
        run("Installing locked Python dependencies", [
            str(PYTHON), "-m", "pip", "install", *locked,
        ], API)
    run("Checking API imports", [str(PYTHON), "-c", "import app.main"], API)
    run("Installing locked frontend dependencies", [npm, "ci"], WEB)

    if not args.dependencies_only:
        run("Initializing and migrating the local SQLite demo", [
            str(PYTHON), "scripts/local_setup.py", "--api-port", str(args.api_port),
            "--web-port", str(args.web_port),
        ], ROOT)
    print("Installation complete. See README.md for launch commands.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, OSError) as exc:
        sys.exit(f"Install failed. Review the command output above. {exc}")
