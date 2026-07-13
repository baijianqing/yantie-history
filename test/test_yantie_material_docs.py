from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODERN_RESEARCH_INDEX = ROOT / "docs" / "YANTIE_A2_MODERN_RESEARCH_INDEX.md"
HUANG_LAO_PLAN = ROOT / "docs" / "YANTIE_A2_HUANG_LAO_MATERIAL_PLAN.md"
HUANGDI_SIJING_VERIFICATION = ROOT / "docs" / "YANTIE_A2_HUANGDI_SIJING_VERIFICATION.md"


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


def test_yantie_huang_lao_plan_keeps_lens_boundary():
    text = HUANG_LAO_PLAN.read_text(encoding="utf-8")

    assert "YT-A2-MAT-005" in text
    assert "黄帝四经" in text
    assert "黄老帛书" in text
    assert "philosophy_lens" in text
    assert "不作为盐铁会议事实" in text
    assert "不声称桑弘羊、贤良文学或霍光直接引用" in text
    assert "本轮不修改 UI、API、Schema、evidence pack 或运行态数据" in text
    assert "\n> " not in text


def test_yantie_huang_lao_candidate_lenses_have_required_fields():
    text = HUANG_LAO_PLAN.read_text(encoding="utf-8")
    cards = re.findall(r"^### (HLS-LENS-\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 6

    required_fields = [
        "- 材料方向：",
        "- 解释目标：",
        "- 对盐铁体验的作用：",
        "- 推荐标签：",
        "- 入包条件：",
    ]

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("HLS-LENS-"):
            continue
        for field in required_fields:
            assert field in section


def test_yantie_huangdi_sijing_verification_keeps_candidate_boundary():
    text = HUANGDI_SIJING_VERIFICATION.read_text(encoding="utf-8")

    assert "YT-A2-MAT-005A" in text
    assert "暂不进入 evidence pack" in text
    assert "不支撑 `original_fact` Claim" in text
    assert "不复制现代整理本、校注本、译本、论文或专著的长段内容" in text
    assert "本轮不修改 UI、API、Schema、evidence pack 或运行态数据" in text
    assert "\n> " not in text


def test_yantie_huangdi_sijing_candidate_quotes_are_short_and_structured():
    text = HUANGDI_SIJING_VERIFICATION.read_text(encoding="utf-8")
    cards = re.findall(r"^### (HLQ-\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 7

    required_fields = [
        "- 材料层：",
        "- 候选短摘：",
        "- 对应透镜：",
        "- 推荐标签：",
        "- 版本状态：candidate-from-ctext",
        "- 版权边界：",
        "- 入包判断：",
    ]
    excerpts = re.findall(r"- 候选短摘：`([^`]+)`", text)

    assert len(excerpts) == 7
    assert all(len(excerpt) <= 12 for excerpt in excerpts)

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("HLQ-"):
            continue
        for field in required_fields:
            assert field in section
