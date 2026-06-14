from __future__ import annotations

import unittest
from pathlib import Path

from metaos.app.run_streamlit import configure_windows_event_loop
from metaos.alpha.gate_check import TextDocument, books_with_profile, profile_field_issues, version_tuple
from metaos.alpha.gate_plan import CORE_BOOKS


class AlphaGateCheckTests(unittest.TestCase):
    def test_core_book_count_includes_added_first_rank_books(self) -> None:
        titles = {item.title for item in CORE_BOOKS}
        self.assertEqual(len(CORE_BOOKS), 32)
        for title in {"道德经", "鬼谷子", "黄帝内经", "黄帝四经", "阴符经", "易经", "资治通鉴", "理想国"}:
            self.assertIn(title, titles)

    def test_version_tuple_extracts_semver(self) -> None:
        self.assertEqual(version_tuple("v22.12.0"), (22, 12, 0))
        self.assertEqual(version_tuple("Python 3.11.9"), (3, 11, 9))

    def test_streamlit_event_loop_config_is_safe_to_call(self) -> None:
        configure_windows_event_loop()

    def test_book_profile_requires_markers(self) -> None:
        book = next(item for item in CORE_BOOKS if item.title == "论语")
        document = TextDocument(
            path=Path("library/00_metaos/books/lunyu.md"),
            text="\n".join(
                [
                    "# 论语",
                    "### 这本书在回答什么问题",
                    "它回答人在日常行动中如何通过反省、学习和实践来校准自己的注意力。",
                    "### 对 MetaOS 的作用",
                    "它为 MetaOS 提供克己、复盘、行动与学习之间关系的最高层原则。",
                    "### 它应该转化成 MetaOS 的什么机制",
                    "它应转化成每日复盘中的自我约束检查、行动兑现检查和注意力偏离提醒。",
                ]
            ),
        )
        self.assertIn(book.title, books_with_profile([document]))

    def test_todo_book_profile_is_not_ready(self) -> None:
        book = next(item for item in CORE_BOOKS if item.title == "论语")
        document = TextDocument(
            path=Path("library/00_metaos/books/lunyu.md"),
            text="\n".join(
                [
                    "# 论语",
                    "### 这本书在回答什么问题",
                    "TODO: 请填写。",
                    "### 对 MetaOS 的作用",
                    "TODO: 请填写。",
                    "### 它应该转化成 MetaOS 的什么机制",
                    "TODO: 请填写。",
                ]
            ),
        )
        self.assertNotIn(book.title, books_with_profile([document]))
        self.assertEqual(
            profile_field_issues(document.text),
            {
                "这本书在回答什么问题": "仍是 TODO 或占位内容",
                "对 MetaOS 的作用": "仍是 TODO 或占位内容",
                "它应该转化成 MetaOS 的什么机制": "仍是 TODO 或占位内容",
            },
        )


if __name__ == "__main__":
    unittest.main()
