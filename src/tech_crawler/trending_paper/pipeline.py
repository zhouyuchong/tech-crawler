import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

from tech_crawler.trending_paper import crawler, download_papers, read_papers


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobResult:
    trending_count: int
    trending_added_count: int
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


def paper_record(paper):
    return f"{paper.title}\t{paper.paper_url}\t{paper.pdf_url}"


def existing_paper_urls(index_path):
    urls = set()
    paths = [Path(index_path), Path(index_path).with_name("trending_papers.txt")]
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            columns = line.split("\t")
            if len(columns) >= 2:
                urls.add(columns[1])
    return urls


def append_new_trending_papers(index_path, papers):
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    seen_urls = existing_paper_urls(index_path)
    new_papers = [paper for paper in papers if paper.paper_url not in seen_urls]

    if not new_papers:
        LOGGER.info("No new trending papers to append.")
        return 0

    with index_path.open("a", encoding="utf-8") as output:
        for paper in new_papers:
            output.write(paper_record(paper) + "\n")
    LOGGER.info("Appended %s new trending papers to %s", len(new_papers), index_path)
    return len(new_papers)


def write_daily_paper_file(output_dir, papers):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_file = output_dir / "paper.txt"
    paper_file.write_text(
        "".join(paper_record(paper) + "\n" for paper in papers),
        encoding="utf-8",
    )
    LOGGER.info("Saved daily paper metadata: %s", paper_file)
    return paper_file


def run_trending_paper_job(root_dir, job_date=None):
    root_dir = Path(root_dir)
    job_date = job_date or today_iso()
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
    daily_base_url = os.getenv("TRENDING_PAPER_DAILY_URL", crawler.DEFAULT_DAILY_PAPER_URL)
    daily_url = crawler.daily_paper_url(daily_base_url, job_date)

    LOGGER.info("Starting trending paper job for %s", job_date)
    trending_papers = crawler.fetch_papers(trending_url, proxies=proxies, delay_seconds=crawl_delay)
    index_path = root_dir / "data" / "papers" / "trending" / "trending_paper.txt"
    trending_added_count = append_new_trending_papers(index_path, trending_papers)

    daily_papers = crawler.fetch_papers(daily_url, proxies=proxies, delay_seconds=crawl_delay)
    output_dir = download_papers.daily_output_dir(root_dir, job_date)
    write_daily_paper_file(output_dir, daily_papers)

    downloaded_count = 0
    summarized_count = 0
    for paper in daily_papers:
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
        "Finished trending paper job: trending=%s added=%s daily=%s downloaded=%s summarized=%s",
        len(trending_papers),
        trending_added_count,
        len(daily_papers),
        downloaded_count,
        summarized_count,
    )
    return JobResult(
        trending_count=len(trending_papers),
        trending_added_count=trending_added_count,
        daily_count=len(daily_papers),
        downloaded_count=downloaded_count,
        summarized_count=summarized_count,
    )
