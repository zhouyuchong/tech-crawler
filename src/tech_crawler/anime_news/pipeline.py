import logging
from datetime import date
from pathlib import Path

from tech_crawler.anime_news import crawler, summarizer
from tech_crawler.anime_news.db import AnimeNewsDatabase
from tech_crawler.trending_paper.download_papers import load_proxy_config

LOGGER = logging.getLogger(__name__)


def run_anime_news_job(root_dir, job_date=None, db_path=None):
    root_dir = Path(root_dir)
    job_date = job_date or date.today().isoformat()
    if db_path is None:
        db_path = root_dir / "data" / "anime_news" / "anime_news.db"

    proxies = load_proxy_config()
    
    # 1. Download XML
    xml_output_dir = root_dir / "data" / "anime_news" / "raw"
    xml_output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = xml_output_dir / f"news_feed_{job_date}.xml"
    
    crawler.download_rss(xml_path, proxies=proxies)
    
    # 2. Parse XML
    records = crawler.parse_rss(xml_path)
    
    # 3. Update DB and find new records
    db = AnimeNewsDatabase(db_path)
    new_records = []
    try:
        for record in records:
            if not db.get_news(record.guid):
                db.insert_news(record)
                new_records.append(record)
    finally:
        db.close()
        
    LOGGER.info("Found %d total records, %d are new.", len(records), len(new_records))
    
    # 4. Summarize new records
    if new_records:
        report_path = root_dir / "data" / "anime_news" / "anime_news_report.md"
        summarizer.summarize_news(
            new_records=new_records,
            output_path=report_path,
            proxies=proxies,
        )
        LOGGER.info("Anime news job finished successfully with %d new items summarized.", len(new_records))
    else:
        LOGGER.info("Anime news job finished successfully. No new items to summarize.")
