"""Create an isolated, empty SQLite profile and a private local access token.

Run with the API virtual environment's Python. This never copies personal data,
starts cloud services, overwrites an existing profile, or prints the secret.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"


def read_profile() -> dict[str, str]:
    path = LOCAL / "api.env"
    if not path.exists():
        raise SystemExit("Local profile missing. Run scripts/local_setup.py first.")
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8018)
    parser.add_argument("--web-port", type=int, default=5188)
    args = parser.parse_args()
    if not all(1024 <= p <= 65535 for p in [args.api_port, args.web_port]):
        parser.error("Ports must be between 1024 and 65535.")
    if args.api_port == args.web_port:
        parser.error("API and web ports must be different.")
    LOCAL.mkdir(exist_ok=True)
    profile_path = LOCAL / "api.env"
    if not profile_path.exists():
        token = secrets.token_urlsafe(32)
        profile = {
            "VOYAURA_ENVIRONMENT": "local",
            "VOYAURA_DATABASE_URL": "sqlite:///" + (LOCAL / "voyaura.db").as_posix(),
            "VOYAURA_AUTH_USERNAME": "AuroraRovella",
            "VOYAURA_AUTH_TOKEN": token,
            "VOYAURA_CORS_ORIGINS": f"http://127.0.0.1:{args.web_port}",
            "VOYAURA_AMAP_WEB_KEY": "",
            "VOYAURA_AMAP_WEB_PRIVATE_KEY": "",
            "VOYAURA_IMAGE_PROVIDER": "disabled",
            "VOYAURA_AGENT_LLM_ENABLED": "false",
            "VOYAURA_AGENT_LLM_API_KEY": "",
            "VOYAURA_DEEPSEEK_API_KEY": "",
            "VOYAURA_LOCAL_API_PORT": str(args.api_port),
            "VOYAURA_LOCAL_WEB_PORT": str(args.web_port),
        }
        # Exclusive creation prevents accidental replacement of existing secrets.
        with profile_path.open("x", encoding="utf-8") as file:
            file.write("# Private local profile. Never commit this file.\n")
            file.write(
                "\n".join(f"{key}={value}" for key, value in profile.items()) + "\n"
            )
        with (LOCAL / "access-token.txt").open("x", encoding="utf-8") as file:
            file.write(token + "\n")
        try:
            profile_path.chmod(0o600)
            (LOCAL / "access-token.txt").chmod(0o600)
        except OSError:
            pass  # Windows uses the containing user's profile ACL.
    profile = read_profile()
    if len(profile.get("VOYAURA_AUTH_TOKEN", "")) < 32:
        raise SystemExit(
            "Local token is missing or too short; profile was left unchanged."
        )
    env = {**os.environ, **profile}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT / "api",
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.seed"], cwd=ROOT / "api", env=env, check=True
    )
    print("Local empty database migrated and seeded; no travel history was invented.")
    print("Private access token is saved at:", LOCAL / "access-token.txt")
    print("API:", "http://127.0.0.1:" + profile["VOYAURA_LOCAL_API_PORT"])
    print("Web:", "http://127.0.0.1:" + profile["VOYAURA_LOCAL_WEB_PORT"])


if __name__ == "__main__":
    main()
