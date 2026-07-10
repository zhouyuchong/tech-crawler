import logging
import time
from pathlib import Path

import requests

from tech_crawler.anime_news.db import AnimeNewsRecord
from tech_crawler.trending_paper.read_papers import load_llm_config, DEFAULT_LLM_MAX_ATTEMPTS, DEFAULT_LLM_RETRY_DELAY_SECONDS

LOGGER = logging.getLogger(__name__)


def build_prompt(new_records: list[AnimeNewsRecord]) -> str:
    prompt = "请阅读以下最新的动漫新闻列表，并用中文总结出最重要的 5 到 10 条新闻变化或动态：\n\n"
    for i, record in enumerate(new_records, start=1):
        prompt += f"新闻 {i}:\n"
        prompt += f"标题: {record.title}\n"
        prompt += f"链接: {record.link}\n"
        prompt += f"发布时间: {record.pub_date}\n"
        prompt += f"描述: {record.description}\n\n"
        
    prompt += "## 要求\n"
    prompt += "1. 输出 5 到 10 条最重要的改动或动态，以 Markdown 列表的形式呈现。\n"
    prompt += "2. 语言简练，重点突出。\n"
    prompt += "3. 每条新闻后最好能附上对应的原文链接。\n"
    return prompt


def call_llm(prompt, api_key, base_url, model, proxies=None):
    url = f"{base_url.rstrip('/')}/chat/completions"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是专业的动漫新闻资讯助手，回答必须简洁、准确、中文。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=120,
        proxies=proxies,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def summarize_news(
    new_records: list[AnimeNewsRecord],
    output_path: Path,
    api_key=None,
    base_url=None,
    model=None,
    proxies=None,
    max_attempts=DEFAULT_LLM_MAX_ATTEMPTS,
    retry_delay_seconds=DEFAULT_LLM_RETRY_DELAY_SECONDS,
):
    if not new_records:
        LOGGER.info("No new records to summarize.")
        return None

    config = load_llm_config()
    api_key = api_key or config.api_key
    base_url = base_url or config.base_url
    model = model or config.model
    
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY or OPENAI_API_KEY is required.")

    prompt = build_prompt(new_records)
    
    result = None
    for attempt in range(1, max_attempts + 1):
        try:
            LOGGER.info("Calling LLM to summarize anime news (attempt %s/%s)", attempt, max_attempts)
            result = call_llm(
                prompt,
                api_key=api_key,
                base_url=base_url,
                model=model,
                proxies=proxies,
            )
            break
        except requests.RequestException as exc:
            if attempt >= max_attempts:
                raise
            LOGGER.warning(
                "LLM call failed on attempt %s/%s, retrying after %s seconds: %s",
                attempt,
                max_attempts,
                retry_delay_seconds,
                exc,
            )
            if retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)

    if result is None:
         return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result + "\n", encoding="utf-8")
    LOGGER.info("Saved anime news summary to: %s", output_path)
    return output_path
