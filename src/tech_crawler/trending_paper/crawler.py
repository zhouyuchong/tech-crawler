import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from tech_crawler.trending_paper.download_papers import Paper


LOGGER = logging.getLogger(__name__)
DEFAULT_TRENDING_PAPER_URL = "https://huggingface.co/papers/trending"
DEFAULT_DAILY_PAPER_URL = "https://huggingface.co/papers/date/2026-07-01"
DEFAULT_CRAWL_DELAY_SECONDS = 10
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def daily_paper_url(base_url, job_date):
    prefix = base_url.rsplit("/", 1)[0]
    return f"{prefix}/{job_date}"


def parse_arxiv_id(value):
    match = ARXIV_ID.search(value or "")
    if not match:
        return None
    return match.group(1)


def parse_papers(html):
    soup = BeautifulSoup(html, "html.parser")
    papers = []
    seen_urls = set()

    for heading in soup.find_all("h3"):
        link = heading.find("a", href=True)
        if not link:
            continue

        title = " ".join(link.get_text(" ", strip=True).split())
        paper_url = urljoin("https://huggingface.co", link["href"])
        arxiv_id = parse_arxiv_id(paper_url)
        if not title or not arxiv_id or paper_url in seen_urls:
            continue

        seen_urls.add(paper_url)
        papers.append(
            Paper(
                title=title,
                paper_url=paper_url,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                arxiv_id=arxiv_id,
            )
        )

    return papers


def fetch_papers(url, proxies=None, delay_seconds=DEFAULT_CRAWL_DELAY_SECONDS):
    LOGGER.info("Fetching papers page: %s", url)
    response = requests.get(
        url,
        timeout=120,
        proxies=proxies,
        headers={"User-Agent": "tech-crawler/0.1"},
    )
    response.raise_for_status()
    papers = parse_papers(response.text)
    LOGGER.info("Parsed %s papers from %s", len(papers), url)
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return papers
