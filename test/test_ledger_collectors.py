from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from metaos.ledger import (
    GitCommitCollectionPayload,
    MarkdownChangeCollectionPayload,
    WorkEventSource,
    collect_git_commits,
    collect_markdown_changes,
)


class LedgerCollectorTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("git") is None, "git is required for collector test")
    def test_git_commit_collector_converts_commits_to_work_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            self.run_git(repo, "init")
            self.commit_file(
                repo,
                "old.md",
                "# Old\n",
                "old commit",
                "2026-06-14T10:00:00+00:00",
            )
            self.commit_file(
                repo,
                "notes.md",
                "# Notes\n",
                "add ledger notes",
                "2026-06-15T11:00:00+00:00",
            )

            events = collect_git_commits(
                GitCommitCollectionPayload(
                    repo_path=repo,
                    date_from=date(2026, 6, 15),
                    date_to=date(2026, 6, 15),
                    related_intent_id=" intent_alpha ",
                )
            )

            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event.source, WorkEventSource.git_commit)
            self.assertEqual(event.title, "add ledger notes")
            self.assertEqual(event.date, date(2026, 6, 15))
            self.assertEqual(event.related_intent_id, "intent_alpha")
            self.assertIn("notes.md", event.metadata["changed_files"])
            self.assertEqual(event.citations[0].file_path, repo / "notes.md")
            self.assertTrue(event.source_ref)

    def test_markdown_change_collector_uses_mtime_and_first_heading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            daily = root / "daily.md"
            log = nested / "log.markdown"
            old = root / "old.md"
            ignored = root / "notes.txt"
            daily.write_text("# Daily Work\n\nBody", encoding="utf-8")
            log.write_text("Plain first line\n\nMore", encoding="utf-8")
            old.write_text("# Old", encoding="utf-8")
            ignored.write_text("# Ignored", encoding="utf-8")
            self.set_mtime(daily, datetime(2026, 6, 15, 8, tzinfo=timezone.utc))
            self.set_mtime(log, datetime(2026, 6, 15, 9, tzinfo=timezone.utc))
            self.set_mtime(old, datetime(2026, 6, 14, 9, tzinfo=timezone.utc))
            self.set_mtime(ignored, datetime(2026, 6, 15, 9, tzinfo=timezone.utc))

            events = collect_markdown_changes(
                MarkdownChangeCollectionPayload(
                    markdown_dir=root,
                    date_from=date(2026, 6, 15),
                    date_to=date(2026, 6, 15),
                )
            )

            self.assertEqual([event.source_ref for event in events], ["daily.md", "nested/log.markdown"])
            self.assertEqual([event.title for event in events], ["Daily Work", "Plain first line"])
            self.assertTrue(all(event.source == WorkEventSource.markdown_change for event in events))
            self.assertEqual(events[0].citations[0].file_path, daily)

    def test_payloads_validate_date_range_and_collectors_require_existing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(ValidationError):
                MarkdownChangeCollectionPayload(
                    markdown_dir=root,
                    date_from=date(2026, 6, 16),
                    date_to=date(2026, 6, 15),
                )
            with self.assertRaises(FileNotFoundError):
                collect_markdown_changes(
                    MarkdownChangeCollectionPayload(
                        markdown_dir=root / "missing",
                        date_from=date(2026, 6, 15),
                        date_to=date(2026, 6, 15),
                    )
                )
            with self.assertRaises(FileNotFoundError):
                collect_git_commits(
                    GitCommitCollectionPayload(
                        repo_path=root / "missing",
                        date_from=date(2026, 6, 15),
                        date_to=date(2026, 6, 15),
                    )
                )

    def run_git(self, repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)

    def commit_file(self, repo: Path, relative_path: str, content: str, message: str, iso_date: str) -> None:
        path = repo / relative_path
        path.write_text(content, encoding="utf-8")
        self.run_git(repo, "add", relative_path)
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = iso_date
        env["GIT_COMMITTER_DATE"] = iso_date
        self.run_git(
            repo,
            "-c",
            "user.name=MetaOS Test",
            "-c",
            "user.email=metaos@example.test",
            "commit",
            "-m",
            message,
            env=env,
        )

    def set_mtime(self, path: Path, value: datetime) -> None:
        timestamp = value.timestamp()
        os.utime(path, (timestamp, timestamp))


if __name__ == "__main__":
    unittest.main()

