from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path("library/02_ai_market")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


DOCS = [
    {
        "name": "Stanford AI Index Report 2026",
        "url": "https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf",
        "path": ROOT / "ai_index" / "stanford_ai_index_report_2026.pdf",
        "type": "pdf",
    },
    {
        "name": "CB Insights State of AI 2025",
        "url": "https://www.cbinsights.com/research/report/ai-trends-2025/",
        "path": ROOT / "cbinsights" / "cbinsights_state_of_ai_2025.html",
        "type": "html",
        "note": "CB Insights 通常需要网页表单下载完整报告；脚本先保存官方入口页。",
    },
    {
        "name": "State of AI Report 2025 - Homepage",
        "url": "https://www.stateof.ai/",
        "path": ROOT / "state_of_ai" / "state_of_ai_report_2025_homepage.html",
        "type": "html",
    },
    {
        "name": "State of AI Report 2025 - Google Slides PDF Export",
        "url": "https://docs.google.com/presentation/d/1xiLl0VdrlNMAei8pmaX4ojIOfej6lhvZbOIK7Z6C-Go/export/pdf",
        "path": ROOT / "state_of_ai" / "state_of_ai_report_2025_slides.pdf",
        "type": "pdf",
        "note": "如果 Google 拒绝直接下载，请打开 stateof.ai 手动点击 Download 2025 Report。",
    },
    {
        "name": "OECD.AI Policy Observatory",
        "url": "https://oecd.ai/",
        "path": ROOT / "policy" / "oecd_ai_policy_observatory_homepage.html",
        "type": "html",
    },
    {
        "name": "OECD.AI Policy Navigator",
        "url": "https://oecd.ai/en/dashboards/overview",
        "path": ROOT / "policy" / "oecd_ai_policy_navigator.html",
        "type": "html",
    },
    {
        "name": "OECD.AI Index 2026",
        "url": "https://www.oecd.org/content/dam/oecd/en/publications/reports/2026/02/oecd-ai-observatory-index_8f5fa0f2/32c01014-en.pdf",
        "path": ROOT / "policy" / "oecd_ai_index_2026.pdf",
        "type": "pdf",
    },
    {
        "name": "International AI Safety Report 2026",
        "url": "https://internationalaisafetyreport.org/sites/default/files/2026-02/international-ai-safety-report-2026_1.pdf",
        "path": ROOT / "policy" / "international_ai_safety_report_2026.pdf",
        "type": "pdf",
    },
    {
        "name": "International AI Safety Report - Homepage",
        "url": "https://internationalaisafetyreport.org/",
        "path": ROOT / "policy" / "international_ai_safety_report_homepage.html",
        "type": "html",
    },
    {
        "name": "AI Agent Index 2025",
        "url": "https://aiagentindex.mit.edu/data/2025-AI-Agent-Index.pdf",
        "path": ROOT / "ai_agent_index" / "ai_agent_index_2025.pdf",
        "type": "pdf",
    },
    {
        "name": "AI Agent Index - Homepage",
        "url": "https://aiagentindex.mit.edu/",
        "path": ROOT / "ai_agent_index" / "ai_agent_index_homepage.html",
        "type": "html",
    },
]


def ensure_dirs() -> None:
    for subdir in [
        "ai_index",
        "cbinsights",
        "state_of_ai",
        "policy",
        "ai_agent_index",
    ]:
        path = ROOT / subdir
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").touch(exist_ok=True)


def download_file(url: str, target: Path, expected_type: str) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)

    print(f"下载: {url}")
    response = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if expected_type == "pdf" and "pdf" not in content_type:
        # 有些站点会返回 HTML 登录页/确认页，不要误存成 PDF。
        fallback = target.with_suffix(".download_failed.html")
        fallback.write_bytes(response.content)
        return {
            "ok": False,
            "url": url,
            "target": str(target),
            "saved_as": str(fallback),
            "content_type": content_type,
            "reason": "预期 PDF，但服务器返回的不是 PDF，已保存返回页面供手动检查。",
        }

    target.write_bytes(response.content)

    return {
        "ok": True,
        "url": url,
        "target": str(target),
        "content_type": content_type,
        "bytes": len(response.content),
    }


def write_url_record(doc: dict) -> None:
    record_path = doc["path"].with_suffix(".url.txt")
    record_path.parent.mkdir(parents=True, exist_ok=True)

    text = [
        f"name: {doc['name']}",
        f"url: {doc['url']}",
        f"type: {doc['type']}",
    ]

    if doc.get("note"):
        text.append(f"note: {doc['note']}")

    record_path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    ensure_dirs()

    manifest = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(ROOT),
        "items": [],
    }

    for doc in DOCS:
        write_url_record(doc)

        try:
            result = download_file(doc["url"], doc["path"], doc["type"])
        except Exception as e:
            result = {
                "ok": False,
                "url": doc["url"],
                "target": str(doc["path"]),
                "error": repr(e),
            }

        result["name"] = doc["name"]
        result["note"] = doc.get("note", "")
        manifest["items"].append(result)

        status = "OK" if result.get("ok") else "FAILED"
        print(f"{status}: {doc['name']} -> {result.get('target')}")

    manifest_path = ROOT / "manifest_ai_market_docs.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("完成。manifest:")
    print(manifest_path)


if __name__ == "__main__":
    main()