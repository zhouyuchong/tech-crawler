import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from tech_crawler.trending_paper import pipeline


LOGGER = logging.getLogger(__name__)


def project_root():
    return Path(__file__).resolve().parents[2]


def configure_logging(root_dir):
    log_dir = Path(root_dir) / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tech_crawler.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run tech crawler jobs.")
    parser.add_argument(
        "--module",
        default="trending_paper",
        choices=["trending_paper", "today_paper"],
        help="Crawler module to run. Supported: trending_paper, today_paper.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Job date in YYYY-MM-DD format. Defaults to today.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    root_dir = project_root()
    load_dotenv(root_dir / ".env")
    configure_logging(root_dir)
    args = parse_args(argv)

    if args.module not in ("trending_paper", "today_paper"):
        LOGGER.error("Unsupported module: %s", args.module)
        return 2

    try:
        if args.module == "trending_paper":
            pipeline.run_trending_paper_job(root_dir, args.date)
        elif args.module == "today_paper":
            pipeline.run_today_paper_job(root_dir, args.date)
    except Exception:
        LOGGER.exception("%s job failed.", args.module)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
