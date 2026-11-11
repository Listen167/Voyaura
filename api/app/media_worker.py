from __future__ import annotations

import argparse
import logging
import sys
import time

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.errors import AppError
from app.integrations.media_queue import get_media_queue
from app.media_cleanup import cleanup_expired_media_uploads
from app.media_jobs import process_media_asset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("voyaura.media-worker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process Voyaura private media jobs")
    parser.add_argument("--once", action="store_true", help="Process one queued job and exit")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    queue = get_media_queue()
    logger.info("worker_started queue=%s", queue.queue_key)
    last_cleanup = 0.0
    while True:
        if not args.once and time.monotonic() - last_cleanup >= settings.media_cleanup_interval_seconds:
            try:
                cleanup = cleanup_expired_media_uploads()
                logger.info(
                    "cleanup_finished scanned=%s deleted=%s skipped=%s failures=%s",
                    cleanup.scanned,
                    cleanup.deleted,
                    cleanup.skipped,
                    len(cleanup.failures),
                )
            except (AppError, SQLAlchemyError) as exc:
                logger.error("cleanup_error type=%s message=%s", type(exc).__name__, exc)
            last_cleanup = time.monotonic()
        try:
            asset_id = queue.dequeue(timeout_seconds=2 if args.once else 5)
        except AppError as exc:
            logger.error("queue_error code=%s message=%s", exc.code, exc.message)
            return 1
        if asset_id is None:
            if args.once:
                logger.info("worker_idle no_job=true")
                return 0
            continue
        result = process_media_asset(asset_id)
        logger.info("job_finished asset_id=%s result=%s", asset_id, result)
        if args.once:
            return 0 if result in {"ready", "missing"} else 1


if __name__ == "__main__":
    sys.exit(main())
