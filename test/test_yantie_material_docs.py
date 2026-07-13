from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODERN_RESEARCH_INDEX = ROOT / "docs" / "YANTIE_A2_MODERN_RESEARCH_INDEX.md"


def test_yantie_modern_research_index_keeps_copyright_boundary():
    text = MODERN_RESEARCH_INDEX.read_text(encoding="utf-8")

    assert "YT-A2-MAT-004" in text
    assert "不写入 `evidence_pack.json`" in text
    assert "不作为盐铁会议事实的直接证据" in text
    assert "现代论文或专著全文" in text
    assert "长段摘录" in text
    assert "不得复制论文摘要或出版社介绍" in text
    assert "\n> " not in text


def test_yantie_modern_research_cards_have_required_fields():
    text = MODERN_RESEARCH_INDEX.read_text(encoding="utf-8")
    cards = re.findall(r"^### (MR-YT-\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 7

    required_fields = [
        "- 标题：",
        "- 作者/编者：",
        "- 出版信息：",
        "- 公开链接：",
        "- 观点定位：",
        "- 推荐用途：",
        "- 版权边界：",
        "- 进入 evidence pack 判断：暂不进入",
        "- 人工核验状态：verified-metadata",
    ]

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("MR-YT-"):
            continue
        for field in required_fields:
            assert field in section
