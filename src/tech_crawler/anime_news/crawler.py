import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

from tech_crawler.anime_news.db import AnimeNewsRecord

LOGGER = logging.getLogger(__name__)
FEED_URL = "https://www.animenewsnetwork.com/news/rss.xml"


import subprocess

def download_rss(output_path: Path, proxies=None):
    LOGGER.info("Downloading anime news RSS feed using curl...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = ["curl", "-sSL", FEED_URL, "-o", str(output_path)]
    if proxies and "http" in proxies:
        cmd.extend(["-x", proxies["http"]])
        
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        LOGGER.error("Failed to download RSS feed using curl. Return code: %s", e.returncode)
        raise
        
    LOGGER.info("Saved RSS feed to %s", output_path)
    return output_path


def parse_rss(xml_path: Path) -> list[AnimeNewsRecord]:
    LOGGER.info("Parsing RSS feed: %s", xml_path)
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except ET.ParseError as e:
        content = xml_path.read_text(encoding="utf-8", errors="ignore")
        if "Security check" in content or "<html" in content.lower():
            LOGGER.error("Failed to parse RSS feed. The response appears to be a Cloudflare block or HTML page instead of XML.")
            return []
        LOGGER.error("Failed to parse RSS feed due to XML error: %s", e)
        raise
        
    records = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in root.findall(".//item"):
        guid_elem = item.find("guid")
        title_elem = item.find("title")
        link_elem = item.find("link")
        desc_elem = item.find("description")
        pub_date_elem = item.find("pubDate")
        
        guid = guid_elem.text if guid_elem is not None else (link_elem.text if link_elem is not None else "")
        title = title_elem.text if title_elem is not None else ""
        link = link_elem.text if link_elem is not None else ""
        desc = desc_elem.text if desc_elem is not None else ""
        pub_date = pub_date_elem.text if pub_date_elem is not None else ""
        
        if not guid:
            continue
            
        records.append(AnimeNewsRecord(
            guid=guid,
            title=title,
            link=link,
            description=desc,
            pub_date=pub_date,
            created_time=now_str
        ))
        
    LOGGER.info("Found %d news items in RSS feed", len(records))
    return records
