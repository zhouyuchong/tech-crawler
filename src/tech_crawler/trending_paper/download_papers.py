import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests


LOGGER = logging.getLogger(__name__)
INVALID_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]+')
WHITESPACE = re.compile(r"\s+")
DEFAULT_DOWNLOAD_DELAY_SECONDS = 20
DEFAULT_DOWNLOAD_RETRY_DELAY_SECONDS = 30


@dataclass(frozen=True)
class Paper:
    title: str
    paper_url: str
    pdf_url: str
    arxiv_id: str | None = None


def load_proxy_config():
    if os.getenv("USE_PROXY") != "1":
        os.environ["no_proxy"] = "*"
        os.environ["NO_PROXY"] = "*"
        return {"http": None, "https": None}

    http_proxy = os.getenv("http_proxy") or os.getenv("all_proxy")
    https_proxy = os.getenv("https_proxy") or os.getenv("all_proxy")
    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies or {"http": None, "https": None}


def safe_paper_filename(title, extension=".pdf", max_stem_length=180):
    stem = INVALID_FILENAME_CHARS.sub(" ", title)
    stem = WHITESPACE.sub(" ", stem).strip(" .")
    if not stem:
        stem = "paper"
    stem = stem[:max_stem_length].rstrip(" .")
    return f"{stem}{extension}"


def unique_output_path(output_dir, title, arxiv_id=None, extension=".pdf"):
    output_dir = Path(output_dir)
    candidate = output_dir / safe_paper_filename(title, extension=extension)
    if not candidate.exists():
        return candidate

    if arxiv_id:
        candidate = output_dir / safe_paper_filename(f"{title} - {arxiv_id}", extension=extension)
        if not candidate.exists():
            return candidate

    index = 2
    while True:
        candidate = output_dir / safe_paper_filename(f"{title} - {index}", extension=extension)
        if not candidate.exists():
            return candidate
        index += 1


def daily_output_dir(root_dir, job_date):
    date_slug = job_date.replace("-", "")
    return Path(root_dir) / "data" / "papers" / date_slug


def trending_output_dir(root_dir):
    return Path(root_dir) / "data" / "papers" / "trending"


def download_paper(
    paper,
    output_dir,
    proxies=None,
    delay_seconds=DEFAULT_DOWNLOAD_DELAY_SECONDS,
    max_attempts=3,
    retry_delay_seconds=DEFAULT_DOWNLOAD_RETRY_DELAY_SECONDS,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    default_output_path = output_dir / safe_paper_filename(paper.title, extension=".pdf")
    if default_output_path.exists() and default_output_path.stat().st_size > 0:
        LOGGER.info("PDF already exists, skipping download: %s", default_output_path)
        return default_output_path

    if default_output_path.exists() and default_output_path.stat().st_size == 0:
        output_path = default_output_path
    else:
        output_path = unique_output_path(output_dir, paper.title, paper.arxiv_id, extension=".pdf")

    response = None
    for attempt in range(1, max_attempts + 1):
        try:
            LOGGER.info("Downloading PDF: %s (attempt %s/%s)", paper.pdf_url, attempt, max_attempts)
            response = requests.get(
                paper.pdf_url,
                stream=True,
                timeout=180,
                proxies=proxies,
                headers={"User-Agent": "tech-crawler/0.1"},
            )
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            if attempt >= max_attempts:
                raise
            LOGGER.warning(
                "PDF download failed on attempt %s/%s, retrying after %s seconds: %s (%s)",
                attempt,
                max_attempts,
                retry_delay_seconds,
                paper.pdf_url,
                exc,
            )
            if retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)

    if response is None:
        raise RuntimeError(f"Failed to download PDF: {paper.pdf_url}")

    with output_path.open("wb") as output_file:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if chunk:
                output_file.write(chunk)

    LOGGER.info("Saved PDF: %s", output_path)
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return output_path
