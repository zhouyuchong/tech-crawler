import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from pypdf import PdfReader


LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_LLM_DELAY_SECONDS = 5
MAX_CHARS = 60000


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str


def first_env(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def load_llm_config():
    return LLMConfig(
        api_key=first_env("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
        base_url=first_env("BASE_URL", "OPENAI_BASE_URL") or DEFAULT_BASE_URL,
        model=first_env("BASE_MODEL", "OPENAI_MODEL") or DEFAULT_MODEL,
    )


def extract_pdf_text(pdf_path, max_chars=MAX_CHARS):
    reader = PdfReader(str(pdf_path))
    chunks = []
    total_chars = 0

    for page in reader.pages:
        text = page.extract_text() or ""
        if not text.strip():
            continue
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        chunks.append(text[:remaining])
        total_chars += len(chunks[-1])

    return "\n\n".join(chunks)


def build_prompt(filename, text):
    return f"""请阅读下面论文内容，并用中文输出两部分：

## 总结
用 3-6 条要点概括论文研究问题、方法、实验和结论。

## 创新点
用 3-6 条要点详细说明论文相对已有工作的主要创新、设计亮点或贡献。
每条创新点请尽量包含：
- 是什么：这项创新具体做了什么。
- 为什么重要：它解决了什么限制、瓶颈或痛点。
- 与已有方法差异：它和常见做法、baseline 或相关工作相比有什么不同。
- 证据或效果：论文中有哪些实验结果、指标变化或案例能支持这项创新。

论文文件：{filename}

论文内容：
{text}
"""


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
                    "content": "你是严谨的论文阅读助手，回答必须简洁、准确、中文。",
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


def summarize_pdf(
    pdf_path,
    api_key=None,
    base_url=None,
    model=None,
    delay_seconds=DEFAULT_LLM_DELAY_SECONDS,
    proxies=None,
):
    pdf_path = Path(pdf_path)
    output_path = pdf_path.with_suffix(".md")
    if output_path.exists() and output_path.stat().st_size > 0:
        LOGGER.info("Markdown already exists, skipping summary: %s", output_path)
        return output_path

    config = load_llm_config()
    api_key = api_key or config.api_key
    base_url = base_url or config.base_url
    model = model or config.model
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY or OPENAI_API_KEY is required.")

    text = extract_pdf_text(pdf_path)
    if not text.strip():
        LOGGER.warning("Skipped empty PDF text: %s", pdf_path)
        return None

    prompt = build_prompt(pdf_path.name, text)
    result = call_llm(
        prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        proxies=proxies,
    )
    output_path.write_text(result + "\n", encoding="utf-8")
    LOGGER.info("Saved paper summary: %s", output_path)
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return output_path
