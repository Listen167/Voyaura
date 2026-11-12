from __future__ import annotations

import argparse
import logging
import sys

from app.errors import AppError
from app.image_jobs import process_image_job
from app.integrations.image_queue import get_image_queue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("voyaura.image-worker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process Voyaura image generation jobs")
    parser.add_argument("--once", action="store_true", help="Process one queued job and exit")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    queue = get_image_queue()
    logger.info("image_worker_started queue=%s", queue.queue_key)
    while True:
        try:
            job_id = queue.dequeue(timeout_seconds=2 if args.once else 5)
        except AppError as exc:
            logger.error("image_queue_error code=%s message=%s", exc.code, exc.message)
            return 1
        if job_id is None:
            if args.once:
                logger.info("image_worker_idle no_job=true")
                return 0
            continue
        result = process_image_job(job_id)
        logger.info("image_job_finished job_id=%s result=%s", job_id, result)
        if args.once:
            return 0 if result in {"succeeded", "missing"} else 1


if __name__ == "__main__":
    sys.exit(main())
