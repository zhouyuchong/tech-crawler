import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from tech_crawler.trending_paper import pipeline
from tech_crawler.trending_paper.db import PaperDatabase
from tech_crawler.anime_news import pipeline as anime_news_pipeline


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
        choices=["trending_paper", "today_paper", "anime_news"],
        help="Crawler module to run. Supported: trending_paper, today_paper, anime_news.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Job date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Query top N papers by hotness from the database instead of running the crawler job.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    root_dir = project_root()
    load_dotenv(root_dir / ".env")
    configure_logging(root_dir)
    args = parse_args(argv)

    if args.module not in ("trending_paper", "today_paper", "anime_news"):
        LOGGER.error("Unsupported module: %s", args.module)
        return 2

    if args.top is not None:
        if args.top <= 0:
            LOGGER.error("Invalid limit for --top: must be greater than 0.")
            return 2
        try:
            db_path = root_dir / "data" / "papers" / "tech_crawler.db"
            if not db_path.exists():
                print("Database file does not exist yet. Please run the crawler at least once first.")
                return 0

            table_name = "trending_papers" if args.module == "trending_paper" else "daily_papers"
            db = PaperDatabase(db_path)
            try:
                papers = db.get_top_papers(table_name, args.top)
                if not papers:
                    print(f"No papers found in database table: {table_name}")
                    return 0

                print(f"Top {args.top} papers by hotness in {table_name}:")
                print("-" * 80)
                for idx, paper in enumerate(papers, start=1):
                    print(f"{idx:2d}. [Hotness: {paper.hotness}] {paper.title}")
                    print(f"    URL: {paper.paper_url}")
                    print(f"    PDF: {paper.pdf_url}")
                    print(f"    Created: {paper.created_time} | Updated: {paper.update_time}")
                    print("-" * 80)
            finally:
                db.close()
        except Exception:
            LOGGER.exception("Failed to query top papers from database.")
            return 1
        return 0

    try:
        if args.module == "trending_paper":
            pipeline.run_trending_paper_job(root_dir, args.date)
        elif args.module == "today_paper":
            pipeline.run_today_paper_job(root_dir, args.date)
        elif args.module == "anime_news":
            anime_news_pipeline.run_anime_news_job(root_dir, args.date)
    except Exception:
        LOGGER.exception("%s job failed.", args.module)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
