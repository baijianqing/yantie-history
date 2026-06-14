"""Command line gate checker for the MetaOS Alpha plan."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from metaos.alpha.gate_plan import (
    BOOK_PROFILE_MARKERS,
    CORE_BOOKS,
    MECHANISM_MARKERS,
    PERSONAL_CONTENT_MARKERS,
    PERSONAL_PATH_MARKERS,
    STAGE_RANK,
    STRUCTURED_CARD_MARKERS,
    VIDEO_STAGE_BOOKS,
    CoreBook,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}
CORE_BOOK_COUNT = len(CORE_BOOKS)
BOOK_PROFILE_DIR = PROJECT_ROOT / "library" / "00_metaos" / "core_books" / "book_profiles"
PROFILE_FIELD_TITLES = (
    "这本书在回答什么问题",
    "对 MetaOS 的作用",
    "它应该转化成 MetaOS 的什么机制",
)
PLACEHOLDER_MARKERS = ("TODO", "TBD", "待填写", "请填写")


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str
    action: str = ""
    details: dict | None = None


@dataclass(frozen=True)
class TextDocument:
    path: Path
    text: str


@dataclass(frozen=True)
class BookProfileAudit:
    book: CoreBook
    expected_path: Path
    exists: bool
    issues: dict[str, str]

    @property
    def is_ready(self) -> bool:
        return self.exists and not self.issues


def run(argv: list[str], timeout: int = 8) -> tuple[int, str]:
    command = shutil.which(argv[0]) if argv else None
    resolved_argv = [command or argv[0], *argv[1:]] if argv else argv
    try:
        completed = subprocess.run(
            resolved_argv,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") + (exc.stderr or "")
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def version_tuple(text: str) -> tuple[int, ...]:
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text)
    if not match:
        return ()
    return tuple(int(part) for part in match.groups(default="0"))


def has_command(command: str) -> bool:
    return shutil.which(command) is not None


def check_command_version(
    name: str,
    argv: list[str],
    *,
    min_version: tuple[int, ...] | None = None,
    action: str = "",
    required: bool = True,
) -> CheckResult:
    if not has_command(argv[0]):
        return CheckResult(
            name=name,
            status="fail" if required else "warn",
            message=f"{argv[0]} 未安装或不在 PATH。",
            action=action,
        )
    code, output = run(argv)
    if code != 0:
        return CheckResult(
            name=name,
            status="fail" if required else "warn",
            message=f"{argv[0]} 可找到，但版本检查失败。",
            action=action,
            details={"output": output.strip()[:1000]},
        )
    parsed = version_tuple(output)
    if min_version and parsed and parsed < min_version:
        return CheckResult(
            name=name,
            status="fail" if required else "warn",
            message=f"{name} 版本过低：{'.'.join(map(str, parsed))}，要求至少 {'.'.join(map(str, min_version))}。",
            action=action,
            details={"output": output.strip()[:1000]},
        )
    return CheckResult(name=name, status="pass", message=output.strip().splitlines()[0] if output.strip() else "ok")


def check_redis() -> CheckResult:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=1.5) as client:
            client.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = client.recv(32)
        if response.startswith(b"+PONG"):
            return CheckResult("Redis", "pass", "Redis 已在 localhost:6379 响应 PING。")
        return CheckResult(
            "Redis",
            "warn",
            "localhost:6379 有响应，但不是标准 Redis PONG。",
            action="确认端口 6379 是否被 Redis 占用。",
            details={"response": response.decode("utf-8", errors="replace")},
        )
    except OSError as exc:
        return CheckResult(
            "Redis",
            "fail",
            "Redis 未在 localhost:6379 响应。",
            action="如果 Docker 可用，执行：docker run -d --name metaos-redis -p 6379:6379 redis:7",
            details={"error": str(exc)},
        )


def check_ollama_model(model_name: str = "bge-m3") -> CheckResult:
    if not has_command("ollama"):
        return CheckResult("Ollama model", "fail", "ollama 未安装或不在 PATH。", action="安装 Ollama 后执行：ollama pull bge-m3")
    code, output = run(["ollama", "list"], timeout=20)
    if code != 0:
        return CheckResult("Ollama model", "fail", "ollama list 执行失败。", action="确认 Ollama 服务已启动。", details={"output": output.strip()[:1000]})
    if model_name.lower() in output.lower():
        return CheckResult("Ollama model", "pass", f"已找到 {model_name}。")
    return CheckResult("Ollama model", "fail", f"未找到 {model_name}。", action=f"执行：ollama pull {model_name}")


def check_python_env(env_dir: str, required_packages: dict[str, str | None], *, required: bool = True) -> list[CheckResult]:
    python_path = PROJECT_ROOT / env_dir / "Scripts" / "python.exe"
    if not python_path.exists():
        return [
            CheckResult(
                f"{env_dir} Python",
                "fail" if required else "warn",
                f"未找到 {python_path}。",
                action=f"创建或修复 {env_dir} 虚拟环境。",
            )
        ]
    snippet = "\n".join(
        [
            "import importlib.metadata as m",
            "packages = " + repr(list(required_packages)),
            "for pkg in packages:",
            "    try:",
            "        print(f'{pkg}=={m.version(pkg)}')",
            "    except Exception:",
            "        print(f'{pkg}=MISSING')",
        ]
    )
    code, output = run([str(python_path), "-c", snippet], timeout=20)
    results: list[CheckResult] = []
    if code != 0:
        return [
            CheckResult(
                f"{env_dir} packages",
                "fail" if required else "warn",
                "无法读取虚拟环境包版本。",
                action=f"执行：{python_path} -m pip install -r requirements.txt",
                details={"output": output.strip()[:1000]},
            )
        ]
    found: dict[str, str | None] = {}
    for line in output.splitlines():
        if "== " in line:
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            found[name.strip()] = version.strip()
        elif line.endswith("=MISSING"):
            found[line.removesuffix("=MISSING").strip()] = None

    missing = [pkg for pkg in required_packages if not found.get(pkg)]
    mismatched = [
        f"{pkg}=={found[pkg]}，要求 {expected}"
        for pkg, expected in required_packages.items()
        if expected is not None and found.get(pkg) and found[pkg] != expected
    ]
    if missing or mismatched:
        action = (
            f"主环境执行：{python_path} -m pip install -r requirements.txt"
            if env_dir == ".venv311"
            else f"OCR 环境执行：{python_path} -m pip install -r requirements-ocr.txt"
        )
        results.append(
            CheckResult(
                f"{env_dir} packages",
                "fail" if required else "warn",
                "虚拟环境包缺失或版本不符合要求。",
                action=action,
                details={"missing": missing, "mismatched": mismatched, "found": found},
            )
        )
    else:
        results.append(CheckResult(f"{env_dir} packages", "pass", "虚拟环境核心包满足要求。", details={"found": found}))

    code, pip_output = run([str(python_path), "-m", "pip", "check"], timeout=30)
    results.append(
        CheckResult(
            f"{env_dir} pip check",
            "pass" if code == 0 else ("fail" if required else "warn"),
            "pip check 通过。" if code == 0 else "pip check 发现依赖冲突。",
            action=f"查看并修复：{python_path} -m pip check" if code != 0 else "",
            details={"output": pip_output.strip()[:1500]},
        )
    )
    return results


def read_text(path: Path, limit_bytes: int = 1_000_000) -> str:
    raw = path.read_bytes()[:limit_bytes]
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_documents() -> list[TextDocument]:
    library = PROJECT_ROOT / "library"
    if not library.exists():
        return []
    documents: list[TextDocument] = []
    for path in library.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            documents.append(TextDocument(path=path, text=read_text(path)))
        except OSError:
            continue
    return documents


def aliases_for(book: CoreBook) -> tuple[str, ...]:
    return (book.title, *book.aliases)


def doc_matches_book(document: TextDocument, book: CoreBook) -> bool:
    haystack = f"{document.path.name}\n{document.text}".lower()
    return any(alias.lower() in haystack for alias in aliases_for(book))


def has_all_markers(text: str, markers: Iterable[str]) -> bool:
    return all(marker.lower() in text.lower() for marker in markers)


def has_any_marker(text: str, markers: Iterable[str]) -> bool:
    return any(marker.lower() in text.lower() for marker in markers)


def matching_docs(book: CoreBook, documents: list[TextDocument]) -> list[TextDocument]:
    return [document for document in documents if doc_matches_book(document, book)]


def safe_filename_part(value: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    safe = re.sub(r"\s+", "_", safe)
    return safe or "untitled"


def expected_book_profile_path(book: CoreBook) -> Path:
    book_index = next(index for index, candidate in enumerate(CORE_BOOKS, start=1) if candidate.title == book.title)
    return BOOK_PROFILE_DIR / f"{book_index:02d}_{safe_filename_part(book.title)}.md"


def section_body(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^###\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^###\s+|^##\s+|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def meaningful_section_text(body: str) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def profile_field_issues(text: str) -> dict[str, str]:
    issues: dict[str, str] = {}
    for field in PROFILE_FIELD_TITLES:
        body = section_body(text, field)
        if body is None:
            issues[field] = "缺少章节"
            continue
        meaningful = meaningful_section_text(body)
        if not meaningful:
            issues[field] = "未填写"
            continue
        if any(marker.lower() in meaningful.lower() for marker in PLACEHOLDER_MARKERS):
            issues[field] = "仍是 TODO 或占位内容"
            continue
        if len(meaningful) < 12:
            issues[field] = "内容过短"
    return issues


def is_valid_book_profile(document: TextDocument) -> bool:
    combined = f"{document.path.name}\n{document.text}"
    return has_all_markers(combined, BOOK_PROFILE_MARKERS) and not profile_field_issues(document.text)


def audit_expected_book_profiles() -> list[BookProfileAudit]:
    audits: list[BookProfileAudit] = []
    for book in CORE_BOOKS:
        expected_path = expected_book_profile_path(book)
        if not expected_path.exists():
            audits.append(
                BookProfileAudit(
                    book=book,
                    expected_path=expected_path,
                    exists=False,
                    issues={field: "文件未创建" for field in PROFILE_FIELD_TITLES},
                )
            )
            continue
        text = read_text(expected_path)
        audits.append(
            BookProfileAudit(
                book=book,
                expected_path=expected_path,
                exists=True,
                issues=profile_field_issues(text),
            )
        )
    return audits


def books_with_profile(documents: list[TextDocument]) -> set[str]:
    ready: set[str] = set()
    for book in CORE_BOOKS:
        for document in matching_docs(book, documents):
            if is_valid_book_profile(document):
                ready.add(book.title)
                break
    return ready


def books_with_structured_cards(documents: list[TextDocument]) -> set[str]:
    ready: set[str] = set()
    for book in CORE_BOOKS:
        for document in matching_docs(book, documents):
            if has_all_markers(document.text, STRUCTURED_CARD_MARKERS):
                ready.add(book.title)
                break
    return ready


def books_with_mechanism_cards(documents: list[TextDocument]) -> set[str]:
    ready: set[str] = set()
    for book in CORE_BOOKS:
        for document in matching_docs(book, documents):
            if has_any_marker(document.text, MECHANISM_MARKERS):
                ready.add(book.title)
                break
    return ready


def indexed_book_titles() -> set[str]:
    database = PROJECT_ROOT / "library" / "metaos.sqlite3"
    if not database.exists():
        return set()
    try:
        with sqlite3.connect(database) as connection:
            rows = connection.execute(
                """
                SELECT title, summary, metadata_json
                FROM knowledge_items
                WHERE id IN (
                    SELECT DISTINCT knowledge_item_id FROM chunks
                )
                """
            ).fetchall()
    except sqlite3.Error:
        return set()
    indexed: set[str] = set()
    for title, summary, metadata_json in rows:
        haystack = f"{title or ''}\n{summary or ''}\n{metadata_json or ''}".lower()
        for book in CORE_BOOKS:
            if any(alias.lower() in haystack for alias in aliases_for(book)):
                indexed.add(book.title)
    return indexed


def check_book_profiles(stage: str, documents: list[TextDocument]) -> list[CheckResult]:
    results: list[CheckResult] = []
    profile_audits = audit_expected_book_profiles()
    profile_ready = {audit.book.title for audit in profile_audits if audit.is_ready}
    missing_profile_files = [audit for audit in profile_audits if not audit.exists]
    incomplete_profiles = [audit for audit in profile_audits if audit.exists and audit.issues]
    structured_ready = books_with_structured_cards(documents)
    mechanism_ready = books_with_mechanism_cards(documents)
    indexed_ready = indexed_book_titles()

    if STAGE_RANK[stage] >= STAGE_RANK["1"]:
        results.append(
            CheckResult(
                "BookProfile files",
                "pass" if not missing_profile_files else "fail",
                f"BookProfile 文件已创建 {CORE_BOOK_COUNT - len(missing_profile_files)}/{CORE_BOOK_COUNT}。",
                action=f"在 {BOOK_PROFILE_DIR} 下创建缺失的核心书 Profile 文件。"
                if missing_profile_files
                else "",
                details={
                    "missing_files": [
                        {
                            "title": audit.book.title,
                            "path": str(audit.expected_path.relative_to(PROJECT_ROOT)),
                        }
                        for audit in missing_profile_files
                    ]
                },
            )
        )
        results.append(
            CheckResult(
                "Core BookProfiles",
                "pass" if not incomplete_profiles and not missing_profile_files else "fail",
                f"BookProfile 完成 {len(profile_ready)}/{CORE_BOOK_COUNT}。",
                action="为缺失书籍补充 BookProfile：这本书在回答什么问题 / 对 MetaOS 的作用 / 它应该转化成 MetaOS 的什么机制。"
                if incomplete_profiles or missing_profile_files
                else "",
                details={
                    "missing_files": [audit.book.title for audit in missing_profile_files],
                    "incomplete": [
                        {
                            "title": audit.book.title,
                            "path": str(audit.expected_path.relative_to(PROJECT_ROOT)),
                            "issues": audit.issues,
                        }
                        for audit in incomplete_profiles
                    ],
                    "ready": sorted(profile_ready),
                },
            )
        )

    if STAGE_RANK[stage] >= STAGE_RANK["4-5"]:
        missing_video_books = [title for title in VIDEO_STAGE_BOOKS if title not in profile_ready]
        results.append(
            CheckResult(
                "Video-stage books",
                "pass" if not missing_video_books else "fail",
                f"视频阶段优先书籍 BookProfile 完成 {len(VIDEO_STAGE_BOOKS) - len(missing_video_books)}/{len(VIDEO_STAGE_BOOKS)}。",
                action="优先补齐公开视频闭环相关书籍的 BookProfile。"
                if missing_video_books
                else "",
                details={"missing": missing_video_books},
            )
        )

    if STAGE_RANK[stage] >= STAGE_RANK["12"]:
        structured_missing_count = max(0, 12 - len(structured_ready))
        mechanism_missing_count = max(0, 6 - len(mechanism_ready))
        results.append(
            CheckResult(
                "Structured reading cards",
                "pass" if len(structured_ready) >= 12 else "fail",
                f"完整六段结构化读书卡完成 {len(structured_ready)}/12。",
                action="至少为 12 本书补齐六段：问题 / 主张 / 证据 / 反对意见 / 判断变化 / MetaOS 机制。"
                if structured_missing_count
                else "",
                details={"ready": sorted(structured_ready), "missing_count": structured_missing_count},
            )
        )
        results.append(
            CheckResult(
                "Mechanism cards",
                "pass" if len(mechanism_ready) >= 6 else "fail",
                f"机制卡完成 {len(mechanism_ready)}/6。",
                action="至少把 6 本书转化成明确产品机制卡或行动规则。"
                if mechanism_missing_count
                else "",
                details={"ready": sorted(mechanism_ready), "missing_count": mechanism_missing_count},
            )
        )

    if STAGE_RANK[stage] >= STAGE_RANK["1"]:
        unindexed = sorted(profile_ready - indexed_ready)
        results.append(
            CheckResult(
                "Book retrievability",
                "pass" if not unindexed and profile_ready else "warn",
                f"已能在知识库 chunks 中匹配到 {len(indexed_ready & profile_ready)}/{len(profile_ready)} 个 BookProfile。",
                action="把对应 BookProfile 文件通过 MetaOS 入库并完成 chunks/index；如果只是文件存在但未入库，RAG 还检索不到。"
                if unindexed or not profile_ready
                else "",
                details={"profile_ready_not_indexed": unindexed, "indexed": sorted(indexed_ready)},
            )
        )

    return results


def check_personal_materials(stage: str, documents: list[TextDocument]) -> list[CheckResult]:
    if STAGE_RANK[stage] < STAGE_RANK["2-3"]:
        return []
    if not documents:
        return [
            CheckResult(
                "Personal material ratio",
                "fail",
                "library 中没有可检查的文本材料。",
                action="先入库每日记录、决策、失败复盘、注意力漂移和未执行建议。",
            )
        ]
    personal_count = 0
    personal_paths: list[str] = []
    for document in documents:
        path_text = str(document.path.relative_to(PROJECT_ROOT)).lower().replace("\\", "/")
        content = document.text[:5000]
        is_personal = any(marker.lower() in path_text for marker in PERSONAL_PATH_MARKERS) or has_any_marker(content, PERSONAL_CONTENT_MARKERS)
        if is_personal:
            personal_count += 1
            personal_paths.append(path_text)
    ratio = personal_count / len(documents)
    return [
        CheckResult(
            "Personal material ratio",
            "pass" if ratio >= 0.4 else "fail",
            f"个人材料占比 {ratio:.1%} ({personal_count}/{len(documents)})，要求至少 40%。",
            action="把每日记录、决策、失败复盘、注意力漂移、未执行建议补入 library/00_metaos 下。"
            if ratio < 0.4
            else "",
            details={"personal_paths_sample": personal_paths[:20]},
        )
    ]


def check_environment(stage: str) -> list[CheckResult]:
    video_required = STAGE_RANK[stage] >= STAGE_RANK["4-5"]
    results = [
        check_command_version("Git", ["git", "--version"], action="安装或修复 Git for Windows。"),
        check_command_version("Python", ["python", "--version"], min_version=(3, 11), action="安装 Python 3.11，并确保 PATH 指向 3.11。"),
        check_command_version("Python launcher 3.11", ["py", "-3.11", "--version"], min_version=(3, 11), action="安装 Python launcher 或修复 py -3.11。", required=False),
        check_command_version("Docker", ["docker", "--version"], action="安装并启动 Docker Desktop。"),
        check_command_version("Ollama", ["ollama", "--version"], action="安装并启动 Ollama。"),
        check_ollama_model("bge-m3"),
        check_redis(),
        check_command_version(
            "Node for video Alpha",
            ["node", "--version"],
            min_version=(22, 0, 0),
            action="视频 Alpha 前升级到 Node 24 LTS 或至少 Node 22 LTS。",
            required=video_required,
        ),
        check_command_version(
            "npm",
            ["npm", "--version"],
            action="随 Node LTS 一起安装 npm。",
            required=video_required,
        ),
        check_command_version(
            "pnpm",
            ["pnpm", "--version"],
            action="执行：corepack enable; corepack prepare pnpm@latest --activate",
            required=video_required,
        ),
        check_command_version(
            "FFmpeg",
            ["ffmpeg", "-version"],
            action="安装 FFmpeg 并把 bin 目录加入 PATH，然后执行：ffmpeg -version",
            required=video_required,
        ),
    ]
    results.extend(
        check_python_env(
            ".venv311",
            {
                "fastapi": None,
                "streamlit": None,
                "pydantic": None,
                "redis": None,
                "rq": None,
                "chromadb": "0.4.24",
                "pymupdf": None,
                "requests": None,
            },
            required=True,
        )
    )
    results.extend(
        check_python_env(
            ".venv_ocr",
            {
                "paddleocr": None,
                "paddlepaddle": None,
                "opencv-contrib-python": None,
                "pymupdf": None,
                "pillow": None,
            },
            required=False,
        )
    )
    return results


def run_checks(stage: str) -> list[CheckResult]:
    if stage not in STAGE_RANK:
        raise ValueError(f"Unknown stage: {stage}. Valid stages: {', '.join(STAGE_RANK)}")
    documents = load_documents()
    results = check_environment(stage)
    results.extend(check_book_profiles(stage, documents))
    results.extend(check_personal_materials(stage, documents))
    return results


def status_icon(status: str) -> str:
    return {"pass": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}.get(status, "[?]")


def print_text(results: list[CheckResult], stage: str) -> int:
    print(f"MetaOS Alpha gate check: stage {stage}")
    print("=" * 42)
    for result in results:
        print(f"{status_icon(result.status)} {result.name}: {result.message}")
        if result.action:
            print(f"  action: {result.action}")
        if result.details and result.status != "pass":
            detail_text = json.dumps(result.details, ensure_ascii=False, indent=2)
            print(indent(detail_text, "  details: "))
    failures = [result for result in results if result.status == "fail"]
    warnings = [result for result in results if result.status == "warn"]
    print("=" * 42)
    print(f"Summary: {len(failures)} fail, {len(warnings)} warn, {len(results) - len(failures) - len(warnings)} pass")
    return 1 if failures else 0


def indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check MetaOS Alpha stage gates.")
    parser.add_argument("--stage", default="0", choices=sorted(STAGE_RANK, key=lambda key: STAGE_RANK[key]))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_checks(args.stage)
    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
        return 1 if any(result.status == "fail" for result in results) else 0
    return print_text(results, args.stage)


if __name__ == "__main__":
    raise SystemExit(main())
