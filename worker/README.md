# Voyaura Worker

This service will own asynchronous media work:

- photo normalization and thumbnails;
- vlog metadata and cover extraction;
- style generation through provider adapters;
- optional ComfyUI workflows;
- Xiaoxi co-photo composition;
- poster and publish-pack rendering.

No image provider is selected in the scaffold. The worker contract will keep
cloud editing models and ComfyUI interchangeable.

## Current media worker

The first worker slice is implemented with a Redis list and runs separately
from FastAPI. It scans private uploads, creates photo thumbnails, extracts Vlog
covers and metadata, and only then marks an asset as ready.

From the project root, keep it visible in a fourth VS Code terminal:

```powershell
.\worker\run.ps1
```

Process at most one queued job during diagnostics:

```powershell
.\worker\run.ps1 --once
```

Verify Defender/ClamAV, Redis, FFmpeg/ffprobe and MinIO without creating any
travel records. Temporary MinIO objects and the isolated Redis queue are
removed before the command exits:

```powershell
cd api
.\.venv\Scripts\python.exe scripts\media_pipeline_smoke.py
```

Local Windows development uses Windows Defender. Linux deployments can set
`VOYAURA_MEDIA_SCANNER_PROVIDER=clamav` and configure the ClamAV host and port.

The long-running worker checks once per hour for expired uploads that never
left `pending`. It removes their MinIO objects and database rows so they no
longer reserve quota. Run the same bounded cleanup manually from `api/`:

```powershell
.\.venv\Scripts\python.exe -m app.media_cleanup --limit 100
```

The cleanup never removes `processing`, `ready`, or `failed` assets. Failed
tasks remain visible in the city archive so the user can retry recoverable
worker errors or explicitly delete the asset.

