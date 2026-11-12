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

## ComfyUI image worker

Image style jobs use a separate Redis queue so slow ComfyUI workflows do not
block malware scanning and media previews. After configuring `api/.env`, run:

```powershell
.\worker\run-image.ps1
```

For a queue diagnostic that exits after one job or an empty queue:

```powershell
.\worker\run-image.ps1 --once
```

Keep the normal media worker running as well. The image worker downloads the
private source from MinIO, sends it to ComfyUI, validates the returned image,
re-encodes it to WebP without metadata, and stores the result back in MinIO.
The API exposes the completed result through short-lived preview and download
URLs. Users can favorite completed records or delete queued, succeeded, and
failed records through preview/confirm endpoints. A `running` record is locked
against deletion until this worker finishes, preventing a late result from
being written to a removed job.

Each queued image job contains a frozen style recipe and source-preservation
level. The ComfyUI adapter also records model names found in workflow inputs
(`ckpt_name`, `unet_name`, or `model_name`) so completed work remains
auditable without exposing the workflow JSON to the browser.

When a job uses `travel_stamp`, the worker adds the frozen memory title,
city, and date after provider generation. This deterministic Pillow pass keeps
Chinese text out of the generative prompt. Configure
`VOYAURA_IMAGE_CAPTION_FONT_PATH` when the host does not provide Microsoft
YaHei, SimHei, Noto Sans CJK, or PingFang.

An optional deterministic Xiaoxi pass can run before the travel stamp. It
requires an authorized RGBA PNG configured through
`VOYAURA_XIAOXI_PHOTO_ASSET_PATH` and a stable asset version. The worker
supports left/right placement, three scales, soft alpha shadow, and slight
brightness matching. It does not redraw the character with the image model.

