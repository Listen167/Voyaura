# Voyaura

Voyaura is a map-first travel companion for planning journeys, lighting up
visited cities, preserving photos and vlogs, and turning memories into visual
stories with Xiaoxi.

![](image\README\1794376848603.png)

## Projects

- `web/`: Vue 3 responsive PWA for mobile and desktop.
- `api/`: FastAPI service and PostgreSQL data model.
- `worker/`: Redis worker for media scanning, thumbnails, video covers, and future image jobs.
- `infra/`: local PostgreSQL, Redis, and MinIO services.
- `docx/`: product, architecture, integration, database, and delivery docs.

## Quick Start

1. Copy `.env.example` to `.env`; optionally copy `web/.env.example` to `web/.env.local` for AMap credentials.
2. Start Docker Desktop, then run `docker compose --env-file .env -f infra/compose.yml up -d`.
3. From `api/`, create `.venv` and run `python -m pip install -e ".[dev]"` with that environment.
4. From `api/`, run `python -m alembic -c alembic.ini upgrade head`, then `python -m app.seed`.
5. From `api/`, start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`.
6. From `web/`, run `npm install`, then `npm run dev -- --host 127.0.0.1 --port 5174`.
7. From the project root, start the media worker with `.\worker\run.ps1`.

Local services:

- Web: `http://127.0.0.1:5174`
- API docs: `http://127.0.0.1:8001/docs`
- PostgreSQL/Navicat: `127.0.0.1:5433`
- Redis: `127.0.0.1:6379`
- MinIO API: `http://127.0.0.1:9000`
- MinIO console: `http://127.0.0.1:9001`

Uploaded media remains hidden until the worker finishes malware scanning and
creates a WebP thumbnail or video cover. Run the isolated environment check
from `api/` with `.\.venv\Scripts\python.exe scripts\media_pipeline_smoke.py`.
The city archive lists pending and failed media tasks, retries recoverable
worker failures, and deletes one asset through preview and confirmation.
The worker also removes expired, unfinished upload intents once per hour. Run
that cleanup manually from `api/` with
`.\.venv\Scripts\python.exe -m app.media_cleanup --limit 100`.

The city archive includes a date-grouped photo/Vlog gallery. Ready photos can
open the private style dialog. Image generation is disabled by default; after
configuring a ComfyUI API-format workflow in `api/.env`, start its separate
worker from the project root with `.\worker\run-image.ps1`. See
`docx/07-comfyui-integration.md` for the node mapping and verification flow.
The Visual Studio view keeps generation history, favorite filters, signed
downloads, idempotent deletion, and a touch-friendly before/after slider in a
responsive desktop/mobile workspace. UI reference prompts for Image 2 are in
`docx/08-ui-image-prompts.md`.

The map overview includes a real-data year timeline. Selecting a year filters
the city markers and footprint totals together; years are derived only from
confirmed visit endpoints and memory dates, and ready media contributes to the
matching memory year.

The `minimal_zine_poster` preset adapts the MIT-licensed GC Minimal Zine
Poster v0.3.1 prompt system. Voyaura stores its recipe version and source
preservation level with each image job. See `THIRD_PARTY_NOTICES.md` for the
required license notice; upstream example images are not included.

Image jobs may optionally add a deterministic travel stamp containing the
memory title, city, and date. The image worker renders this after provider
generation so Chinese text remains readable. Hosts without a supported CJK
font must set `VOYAURA_IMAGE_CAPTION_FONT_PATH`.

Xiaoxi co-photos use an optional authorized transparent PNG and deterministic
composition after provider generation. Until both
`VOYAURA_XIAOXI_PHOTO_ASSET_PATH` and
`VOYAURA_XIAOXI_PHOTO_ASSET_VERSION` are configured, the UI keeps this option
disabled and the API rejects attempts to create a fake co-photo. See
`docx/09-xiaoxi-photo-assets.md`.

The Redis image comes from Amazon ECR's official Docker Library mirror. The
MinIO image comes from Chainguard and is pinned by digest. These project-level
sources avoid depending on a machine-wide Docker Hub mirror. If startup fails,
run `docker compose --env-file .env -f infra/compose.yml ps` and inspect the
failing service with `docker compose --env-file .env -f infra/compose.yml logs SERVICE`.

The default seed creates `AuroraRovella` as the first tester without inventing
any travel history. Authentication will be added in a later milestone.
