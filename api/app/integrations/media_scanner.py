from __future__ import annotations

import glob
import os
import socket
import struct
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings
from app.errors import AppError


@dataclass(frozen=True)
class ScanResult:
    infected: bool
    threat_name: str | None = None


class MediaScanner:
    def scan(self, path: str) -> ScanResult:
        raise NotImplementedError


class WindowsDefenderScanner(MediaScanner):
    def __init__(self, executable: str = "") -> None:
        self.executable = executable or self._find_executable()

    @staticmethod
    def _find_executable() -> str:
        candidates = sorted(
            glob.glob(
                r"C:\ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe"
            ),
            reverse=True,
        )
        if not candidates:
            raise AppError(
                "MEDIA_SCANNER_UNAVAILABLE",
                "找不到 Windows Defender 命令行扫描器。",
                status_code=503,
                retryable=True,
            )
        return candidates[0]

    def scan(self, path: str) -> ScanResult:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "-Scan",
                    "-ScanType",
                    "3",
                    "-File",
                    path,
                    "-DisableRemediation",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AppError(
                "MEDIA_SCANNER_UNAVAILABLE",
                "Windows Defender 扫描未能完成。",
                status_code=503,
                retryable=True,
            ) from exc
        output = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode == 0 and "found no threats" in output:
            return ScanResult(infected=False)
        if result.returncode == 2 or "found threat" in output or "threat detected" in output:
            return ScanResult(infected=True, threat_name="Windows Defender detection")
        raise AppError(
            "MEDIA_SCANNER_UNAVAILABLE",
            "Windows Defender 返回了无法识别的扫描结果。",
            status_code=503,
            details={"exit_code": result.returncode},
            retryable=True,
        )


class ClamAVScanner(MediaScanner):
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def scan(self, path: str) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=10) as connection:
                connection.sendall(b"zINSTREAM\0")
                with open(path, "rb") as source:
                    while chunk := source.read(1024 * 1024):
                        connection.sendall(struct.pack("!I", len(chunk)))
                        connection.sendall(chunk)
                connection.sendall(struct.pack("!I", 0))
                response = connection.recv(4096).decode("utf-8", errors="replace").strip("\0")
        except (OSError, TimeoutError) as exc:
            raise AppError(
                "MEDIA_SCANNER_UNAVAILABLE",
                "ClamAV 扫描服务暂时不可用。",
                status_code=503,
                retryable=True,
            ) from exc
        if response.endswith("OK"):
            return ScanResult(infected=False)
        if response.endswith("FOUND"):
            threat = response.rsplit(":", 1)[-1].removesuffix("FOUND").strip()
            return ScanResult(infected=True, threat_name=threat or "ClamAV detection")
        raise AppError(
            "MEDIA_SCANNER_UNAVAILABLE",
            "ClamAV 返回了无法识别的扫描结果。",
            status_code=503,
            retryable=True,
        )


@lru_cache
def get_media_scanner() -> MediaScanner:
    provider = settings.media_scanner_provider.strip().lower()
    if provider == "windows_defender":
        if os.name != "nt":
            raise AppError(
                "MEDIA_SCANNER_UNAVAILABLE",
                "当前系统不支持 Windows Defender 扫描 Provider。",
                status_code=503,
                retryable=True,
            )
        return WindowsDefenderScanner(settings.windows_defender_path)
    if provider == "clamav":
        return ClamAVScanner(settings.clamav_host, settings.clamav_port)
    raise AppError(
        "MEDIA_SCANNER_CONFIG_ERROR",
        "媒体扫描 Provider 配置无效。",
        status_code=500,
        details={"provider": provider},
    )
