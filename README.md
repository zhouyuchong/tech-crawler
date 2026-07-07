# Tech Crawler

Daily crawler jobs for technology content. The first implemented job collects Hugging Face trending papers, downloads daily paper PDFs, and summarizes each paper with an OpenAI-compatible LLM API.

## Setup

Install and run with `uv`:

```bash
uv sync
```

Create a local `.env` file with the required settings:

```env
TRENDING_PAPER_URL=https://huggingface.co/papers/trending
TRENDING_PAPER_DAILY_URL=https://huggingface.co/papers/date/2026-07-01

DEEPSEEK_API_KEY=your-api-key
BASE_URL=https://api.deepseek.com/v1
BASE_MODEL=deepseek-chat

USE_PROXY=0
http_proxy=http://127.0.0.1:7890
https_proxy=http://127.0.0.1:7890
all_proxy=http://127.0.0.1:7890

CRAWL_DELAY_SECONDS=30
DOWNLOAD_DELAY_SECONDS=60
DOWNLOAD_RETRY_DELAY_SECONDS=120
DOWNLOAD_MAX_ATTEMPTS=3
LLM_DELAY_SECONDS=5
```

`USE_PROXY=1` enables the proxy values above. `USE_PROXY=0` or an unset value disables proxies.

## Usage

Run the weekly trending paper job:

```bash
uv run tech-crawler --module trending_paper
```

Run the daily today paper job:

```bash
uv run tech-crawler --module today_paper
```

Backfill a specific date for daily papers:

```bash
uv run tech-crawler --module today_paper --date 2026-07-01
```

Query top papers by hotness from the database:

```bash
# Query top 10 trending papers
uv run tech-crawler --module trending_paper --top 10

# Query top 10 daily papers
uv run tech-crawler --module today_paper --top 10
```

Recommended crontab shape:

```cron
# Run trending papers weekly, today papers daily
0 8 * * 1 cd /path/to/tech_crawler && uv run tech-crawler --module trending_paper
0 8 * * * cd /path/to/tech_crawler && uv run tech-crawler --module today_paper
```

## Data Layout

- `data/papers/tech_crawler.db`: local SQLite database containing `trending_papers` and `daily_papers` registries (automatic migration from legacy text files).
- `data/papers/trending/YYYY-Www/*.pdf`: weekly trending paper PDFs.
- `data/papers/trending/YYYY-Www/*.md`: weekly trending paper summaries.
- `data/papers/YYYYMMDD/paper.txt`: daily paper metadata.
- `data/papers/YYYYMMDD/*.pdf`: downloaded daily paper PDFs.
- `data/papers/YYYYMMDD/*.md`: per-paper daily summaries.
- `data/logs/tech_crawler.log`: runtime logs.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
