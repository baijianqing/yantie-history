from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md


ROOT = Path("library/01_ai_stack")

HEADERS = {
    "User-Agent": "MetaOS-KnowledgeBaseBot/0.1 (+local personal knowledge base)"
}

REQUEST_TIMEOUT = 60
SLEEP_SECONDS = 0.5
FAILED_URLS = []


@dataclass
class Source:
    name: str
    folder: str
    start_urls: list[str]
    same_domain_only: bool = True
    max_pages: int = 8


SOURCES = [
    Source(
        name="Chroma",
        folder="chroma",
        start_urls=[
            "https://docs.trychroma.com/docs/overview/getting-started",
            "https://docs.trychroma.com/docs/overview/introduction",
        ],
        max_pages=10,
    ),
    Source(
        name="LangGraph",
        folder="langgraph",
        start_urls=[
            "https://docs.langchain.com/oss/python/langgraph/overview",
        ],
        max_pages=10,
    ),
    Source(
        name="MCP",
        folder="mcp",
        start_urls=[
            "https://modelcontextprotocol.io/docs/getting-started/intro",
        ],
        max_pages=10,
    ),
    Source(
        name="OpenAI Agents SDK",
        folder="agents/openai_agents_sdk",
        start_urls=[
            "https://developers.openai.com/api/docs/guides/agents",
            "https://openai.github.io/openai-agents-python/quickstart/",
            "https://openai.github.io/openai-agents-python/agents/",
            "https://openai.github.io/openai-agents-python/tools/",
        ],
        max_pages=12,
    ),
    Source(
        name="ONNX Runtime",
        folder="onnxruntime",
        start_urls=[
            "https://onnxruntime.ai/docs/",
            "https://onnxruntime.ai/docs/get-started/",
            "https://onnxruntime.ai/docs/get-started/with-python.html",
            "https://onnxruntime.ai/docs/install/",
        ],
        max_pages=12,
    ),
    Source(
        name="Ollama",
        folder="ollama",
        start_urls=[
            "https://docs.ollama.com/api/introduction",
            "https://github.com/ollama/ollama/tree/main/docs",
        ],
        max_pages=10,
    ),
    Source(
        name="vLLM",
        folder="vllm",
        start_urls=[
            "https://docs.vllm.ai/",
            "https://vllm.ai/",
            "https://github.com/vllm-project/vllm",
        ],
        max_pages=10,
    ),
    Source(
        name="llama.cpp",
        folder="llama_cpp",
        start_urls=[
            "https://github.com/ggml-org/llama.cpp",
            "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/build.md",
            "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/install.md",
        ],
        max_pages=8,
    ),
    Source(
        name="BGE / FlagEmbedding",
        folder="bge_flagembedding",
        start_urls=[
            "https://bge-model.com/",
            "https://github.com/FlagOpen/FlagEmbedding",
            "https://hf-mirror.com/BAAI/bge-m3",
            "https://huggingface.co/BAAI/bge-m3",
            "https://arxiv.org/abs/2402.03216",
        ],
        max_pages=10,
    ),
]


def safe_filename(url: str, index: int) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        path = "index"

    name = f"{parsed.netloc}_{path}"
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    name = name.strip("_")

    if len(name) > 120:
        name = name[:120]

    return f"{index:03d}_{name}.md"


def fetch_html(url: str, retries: int = 3) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            print(f"[fetch attempt {attempt}/{retries}] {url}")

            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            if (
                "text/html" not in content_type
                and "text/plain" not in content_type
                and "text/markdown" not in content_type
            ):
                print(f"[skip non-html] {url} ({content_type})")
                return None

            return resp.text

        except Exception as exc:
            print(f"[fetch failed] attempt {attempt}/{retries}: {url}: {exc}")

            if attempt < retries:
                time.sleep(2 * attempt)

    FAILED_URLS.append(
        {
            "url": url,
            "error": "fetch_failed_after_retries",
            "retries": retries,
        }
    )

    return None


def html_to_markdown(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else url
    body = soup.body or soup

    content = md(str(body), heading_style="ATX")

    return f"""---
source_url: {url}
title: {json.dumps(title, ensure_ascii=False)}
fetched_at: {time.strftime("%Y-%m-%d %H:%M:%S")}
---

# {title}

{content}
"""


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        if not href or href.startswith("#"):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.scheme not in {"http", "https"}:
            continue

        full_url = full_url.split("#")[0]

        if full_url not in links:
            links.append(full_url)

    return links


def is_allowed_link(source: Source, url: str, start_domain: str) -> bool:
    parsed = urlparse(url)

    if source.same_domain_only and parsed.netloc != start_domain:
        return False

    # 避免抓太多无关页面
    blocked_ext = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".zip", ".tar", ".gz", ".whl", ".exe",
        ".mp4", ".pdf",
    )

    if parsed.path.lower().endswith(blocked_ext):
        return False

    return True

def file_exists_and_not_empty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0

def crawl_source(source: Source) -> None:
    out_dir = ROOT / source.folder
    out_dir.mkdir(parents=True, exist_ok=True)

    visited: set[str] = set()
    queue: list[str] = list(source.start_urls)
    saved = []

    print(f"\n=== {source.name} ===")
    print(f"folder: {out_dir}")

    while queue and len(visited) < source.max_pages:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        filename = safe_filename(url, len(saved) + 1)
        output_path = out_dir / filename

        # 如果目标文件已经存在，并且大小不为 0，则跳过下载和覆盖
        if file_exists_and_not_empty(output_path):
            print(f"[skip existing] {output_path}")
            saved.append(
                {
                    "url": url,
                    "file": filename,
                    "status": "skipped_existing",
                }
            )
            continue

        print(f"[fetch] {url}")

        html = fetch_html(url)
        if html is None:
            continue

        md_text = html_to_markdown(html, url)
        output_path.write_text(md_text, encoding="utf-8")

        saved.append(
            {
                "url": url,
                "file": filename,
                "status": "downloaded",
            }
        )

        start_domain = urlparse(source.start_urls[0]).netloc

        for link in extract_links(html, url):
            if link not in visited and is_allowed_link(source, link, start_domain):
                queue.append(link)

        time.sleep(SLEEP_SECONDS)

    manifest = {
        "name": source.name,
        "folder": str(out_dir),
        "start_urls": source.start_urls,
        "saved_count": len(saved),
        "saved": saved,
    }

    manifest_path = out_dir / "_manifest.json"

    # manifest 每次更新即可，它是索引记录，不是正文文档
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (out_dir / ".gitkeep").touch(exist_ok=True)

    print(f"[done] {source.name}: processed {len(saved)} pages")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)

    for source in SOURCES:
        crawl_source(source)

    failed_path = ROOT / "_failed_urls.json"

    failed_path.write_text(
        json.dumps(FAILED_URLS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n全部抓取完成。")
    print(f"输出目录: {ROOT.resolve()}")
    print(f"失败链接数量: {len(FAILED_URLS)}")
    print(f"失败记录: {failed_path}")


if __name__ == "__main__":
    main()
