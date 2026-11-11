# Voyaura

Voyaura is a map-first travel companion for planning journeys, lighting up
visited cities, preserving photos and vlogs, and turning memories into visual
stories with Xiaoxi.

## Projects

- `web/`: Vue 3 responsive PWA for mobile and desktop.
- `api/`: FastAPI service and PostgreSQL data model.
- `worker/`: reserved for image, video, and ComfyUI jobs.
- `infra/`: local PostgreSQL, Redis, and MinIO services.
- `docx/`: product, architecture, integration, database, and delivery docs.

## Quick Start

1. Copy `.env.example` to `.env`; optionally copy `web/.env.example` to `web/.env.local` for AMap credentials.
2. Start Docker Desktop, then run `docker compose --env-file .env -f infra/compose.yml up -d`.
3. From `api/`, create `.venv` and run `python -m pip install -e ".[dev]"` with that environment.
4. From `api/`, run `python -m alembic -c alembic.ini upgrade head`, then `python -m app.seed`.
5. From `api/`, start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`.
6. From `web/`, run `npm install`, then `npm run dev -- --host 127.0.0.1 --port 5174`.

Local services:

- Web: `http://127.0.0.1:5174`
- API docs: `http://127.0.0.1:8001/docs`
- PostgreSQL/Navicat: `127.0.0.1:5433`
- Redis: `127.0.0.1:6379`
- MinIO API: `http://127.0.0.1:9000`
- MinIO console: `http://127.0.0.1:9001`

The Redis image comes from Amazon ECR's official Docker Library mirror. The
MinIO image comes from Chainguard and is pinned by digest. These project-level
sources avoid depending on a machine-wide Docker Hub mirror. If startup fails,
run `docker compose --env-file .env -f infra/compose.yml ps` and inspect the
failing service with `docker compose --env-file .env -f infra/compose.yml logs SERVICE`.

The default seed creates `AuroraRovella` as the first tester without inventing
any travel history. Authentication will be added in a later milestone.

