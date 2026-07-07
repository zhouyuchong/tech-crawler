import datetime
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

from tech_crawler.trending_paper import crawler, download_papers, read_papers
from tech_crawler.trending_paper.db import PaperDatabase, PaperRecord

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobResult:
    trending_count: int
    trending_added_count: int
    trending_downloaded_count: int
    trending_summarized_count: int
    daily_count: int
    downloaded_count: int
    summarized_count: int


def env_int(name, default):
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        LOGGER.warning("Invalid integer for %s=%r; using %s", name, value, default)
        return default


def today_iso():
    return date.today().isoformat()


def paper_record(paper, update_time=None):
    if update_time is None:
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{paper.title}\t{paper.paper_url}\t{paper.pdf_url}\t{update_time}"


def write_daily_paper_file(output_dir, papers, update_time=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_file = output_dir / "paper.txt"
    paper_file.write_text(
        "".join(paper_record(paper, update_time=update_time) + "\n" for paper in papers),
        encoding="utf-8",
    )
    LOGGER.info("Saved daily paper metadata: %s", paper_file)
    return paper_file


def migrate_legacy_txt_to_db(root_dir, db: PaperDatabase):
    legacy_files = [
        Path(root_dir) / "data" / "papers" / "trending" / "trending_paper.txt",
        Path(root_dir) / "data" / "papers" / "trending" / "trending_papers.txt",
    ]
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for file_path in legacy_files:
        if not file_path.exists():
            continue
        try:
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                columns = line.split("\t")
                if len(columns) < 2:
                    continue
                title = columns[0]
                paper_url = columns[1]
                pdf_url = columns[2] if len(columns) > 2 else ""

                if db.get_paper("trending_papers", paper_url) is not None:
                    continue

                created_time = columns[3] if len(columns) >= 4 else now_str
                db.insert_paper(
                    "trending_papers",
                    PaperRecord(
                        paper_url=paper_url,
                        title=title,
                        pdf_url=pdf_url,
                        created_time=created_time,
                        update_time=created_time,
                        hotness=1,
                    ),
                )
            file_path.rename(file_path.with_suffix(".txt.bak"))
            LOGGER.info("Migrated legacy index %s to SQLite and renamed to .bak", file_path.name)
        except Exception:
            LOGGER.exception("Failed to migrate legacy file %s", file_path)


def update_paper_registry(db: PaperDatabase, table_name, papers, update_time=None):
    if update_time is None:
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_papers = []
    for paper in papers:
        existing = db.get_paper(table_name, paper.paper_url)
        if existing:
            db.update_paper_hotness(table_name, paper.paper_url, update_time)
        else:
            record = PaperRecord(
                paper_url=paper.paper_url,
                title=paper.title,
                pdf_url=paper.pdf_url,
                created_time=update_time,
                update_time=update_time,
                hotness=1,
            )
            db.insert_paper(table_name, record)
            new_papers.append(paper)
    return new_papers


def run_trending_paper_job(root_dir, job_date=None, update_time=None, db_path=None):
    root_dir = Path(root_dir)
    job_date = job_date or today_iso()
    if update_time is None:
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db_path is None:
        db_path = root_dir / "data" / "papers" / "tech_crawler.db"

    proxies = download_papers.load_proxy_config()
    crawl_delay = env_int("CRAWL_DELAY_SECONDS", crawler.DEFAULT_CRAWL_DELAY_SECONDS)
    download_delay = env_int("DOWNLOAD_DELAY_SECONDS", download_papers.DEFAULT_DOWNLOAD_DELAY_SECONDS)
    download_max_attempts = env_int("DOWNLOAD_MAX_ATTEMPTS", 3)
    download_retry_delay = env_int(
        "DOWNLOAD_RETRY_DELAY_SECONDS",
        download_papers.DEFAULT_DOWNLOAD_RETRY_DELAY_SECONDS,
    )
    llm_delay = env_int("LLM_DELAY_SECONDS", read_papers.DEFAULT_LLM_DELAY_SECONDS)

    trending_url = os.getenv("TRENDING_PAPER_URL", crawler.DEFAULT_TRENDING_PAPER_URL)

    LOGGER.info("Starting trending paper job for %s", job_date)
    trending_papers = crawler.fetch_papers(trending_url, proxies=proxies, delay_seconds=crawl_delay)

    db = PaperDatabase(db_path)
    try:
        migrate_legacy_txt_to_db(root_dir, db)
        new_trending_papers = update_paper_registry(db, "trending_papers", trending_papers, update_time=update_time)
    finally:
        db.close()

    trending_dir = download_papers.trending_output_dir(root_dir, job_date)
    trending_downloaded_count = 0
    trending_summarized_count = 0
    total_trending = len(new_trending_papers)

    for index, paper in enumerate(new_trending_papers, start=1):
        LOGGER.info("[Trending %s/%s] Downloading paper: %s", index, total_trending, paper.title)
        try:
            pdf_path = download_papers.download_paper(
                paper,
                trending_dir,
                proxies=proxies,
                delay_seconds=download_delay,
                max_attempts=download_max_attempts,
                retry_delay_seconds=download_retry_delay,
            )
            trending_downloaded_count += 1
        except requests.RequestException:
            LOGGER.exception("Failed to download trending paper: %s", paper.title)
            continue

        LOGGER.info("[Trending %s/%s] Summarizing paper: %s", index, total_trending, paper.title)
        try:
            summary_path = read_papers.summarize_pdf(
                pdf_path,
                delay_seconds=llm_delay,
                proxies=proxies,
            )
        except (RuntimeError, requests.RequestException, OSError):
            LOGGER.exception("Failed to summarize trending paper: %s", pdf_path)
            continue

        if summary_path is not None:
            trending_summarized_count += 1

    LOGGER.info(
        "Finished trending paper job: trending=%s added=%s trending_downloaded=%s trending_summarized=%s",
        len(trending_papers),
        len(new_trending_papers),
        trending_downloaded_count,
        trending_summarized_count,
    )
    return JobResult(
        trending_count=len(trending_papers),
        trending_added_count=len(new_trending_papers),
        trending_downloaded_count=trending_downloaded_count,
        trending_summarized_count=trending_summarized_count,
        daily_count=0,
        downloaded_count=0,
        summarized_count=0,
    )


def run_today_paper_job(root_dir, job_date=None, update_time=None, db_path=None):
    root_dir = Path(root_dir)
    job_date = job_date or today_iso()
    if update_time is None:
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db_path is None:
        db_path = root_dir / "data" / "papers" / "tech_crawler.db"

    proxies = download_papers.load_proxy_config()
    crawl_delay = env_int("CRAWL_DELAY_SECONDS", crawler.DEFAULT_CRAWL_DELAY_SECONDS)
    download_delay = env_int("DOWNLOAD_DELAY_SECONDS", download_papers.DEFAULT_DOWNLOAD_DELAY_SECONDS)
    download_max_attempts = env_int("DOWNLOAD_MAX_ATTEMPTS", 3)
    download_retry_delay = env_int(
        "DOWNLOAD_RETRY_DELAY_SECONDS",
        download_papers.DEFAULT_DOWNLOAD_RETRY_DELAY_SECONDS,
    )
    llm_delay = env_int("LLM_DELAY_SECONDS", read_papers.DEFAULT_LLM_DELAY_SECONDS)

    daily_base_url = os.getenv("TRENDING_PAPER_DAILY_URL", crawler.DEFAULT_DAILY_PAPER_URL)
    daily_url = crawler.daily_paper_url(daily_base_url, job_date)

    LOGGER.info("Starting today paper job for %s", job_date)
    daily_papers = crawler.fetch_papers(daily_url, proxies=proxies, delay_seconds=crawl_delay)

    db = PaperDatabase(db_path)
    try:
        new_daily_papers = update_paper_registry(db, "daily_papers", daily_papers, update_time=update_time)
    finally:
        db.close()

    output_dir = download_papers.daily_output_dir(root_dir, job_date)
    write_daily_paper_file(output_dir, daily_papers, update_time=update_time)

    downloaded_count = 0
    summarized_count = 0
    total_daily = len(new_daily_papers)

    for index, paper in enumerate(new_daily_papers, start=1):
        LOGGER.info("[Daily %s/%s] Downloading paper: %s", index, total_daily, paper.title)
        try:
            pdf_path = download_papers.download_paper(
                paper,
                output_dir,
                proxies=proxies,
                delay_seconds=download_delay,
                max_attempts=download_max_attempts,
                retry_delay_seconds=download_retry_delay,
            )
            downloaded_count += 1
        except requests.RequestException:
            LOGGER.exception("Failed to download paper: %s", paper.title)
            continue

        LOGGER.info("[Daily %s/%s] Summarizing paper: %s", index, total_daily, paper.title)
        try:
            summary_path = read_papers.summarize_pdf(
                pdf_path,
                delay_seconds=llm_delay,
                proxies=proxies,
            )
        except (RuntimeError, requests.RequestException, OSError):
            LOGGER.exception("Failed to summarize paper: %s", pdf_path)
            continue

        if summary_path is not None:
            summarized_count += 1

    LOGGER.info(
        "Finished today paper job: daily=%s added=%s downloaded=%s summarized=%s",
        len(daily_papers),
        len(new_daily_papers),
        downloaded_count,
        summarized_count,
    )
    return JobResult(
        trending_count=0,
        trending_added_count=0,
        trending_downloaded_count=0,
        trending_summarized_count=0,
        daily_count=len(daily_papers),
        downloaded_count=downloaded_count,
        summarized_count=summarized_count,
    )
