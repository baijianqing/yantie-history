import json
from pathlib import Path
import re

from metaos.yantie import EvidencePack


ROOT = Path(__file__).resolve().parents[1]
MATERIAL_GAP = ROOT / "docs" / "YANTIE_A2_MATERIAL_GAP.md"
EVIDENCE_PACK = ROOT / "metaos" / "yantie" / "data" / "evidence_pack.json"
MODERN_RESEARCH_INDEX = ROOT / "docs" / "YANTIE_A2_MODERN_RESEARCH_INDEX.md"
HUANG_LAO_PLAN = ROOT / "docs" / "YANTIE_A2_HUANG_LAO_MATERIAL_PLAN.md"
HUANGDI_SIJING_VERIFICATION = ROOT / "docs" / "YANTIE_A2_HUANGDI_SIJING_VERIFICATION.md"
CLASSICS_CONTEXT_PLAN = ROOT / "docs" / "YANTIE_A2_CLASSICS_CONTEXT_PLAN.md"
HANSHU_CLASSICS_VERIFICATION = ROOT / "docs" / "YANTIE_A2_HANSHU_CLASSICS_VERIFICATION.md"
CHUNQIU_FANLU_VERIFICATION = ROOT / "docs" / "YANTIE_A2_CHUNQIU_FANLU_VERIFICATION.md"


def test_yantie_material_gap_pack_counts_match_evidence_pack():
    text = MATERIAL_GAP.read_text(encoding="utf-8")
    payload = json.loads(EVIDENCE_PACK.read_text(encoding="utf-8"))
    pack = EvidencePack.model_validate(payload)

    match = re.search(
        r"evidence pack 当前有 (\d+) 个 source、(\d+) 条 EvidenceUnit、(\d+) 条 Claim。",
        text,
    )

    assert match
    source_count, evidence_count, claim_count = map(int, match.groups())
    assert source_count == len(pack.sources)
    assert evidence_count == len(pack.evidence_units)
    assert claim_count == len(pack.claims)


def test_yantie_material_gap_tracks_post_court_ui_status():
    text = MATERIAL_GAP.read_text(encoding="utf-8")

    for task_id in [
        "YT-A2-MAT-006D",
        "YT-A2-MAT-006E",
        "YT-A2-MAT-006F",
        "YT-A2-MAT-006G",
        "YT-A2-MAT-007",
        "YT-A2-MAT-008",
        "YT-A2-MAT-009",
        "YT-A2-MAT-010",
    ]:
        assert task_id in text

    assert "退朝后 `classics_context` 思想透镜分组" in text
    assert "退朝后材料导览入口" in text
    assert "`material-guide` Playwright 验收场景" in text
    assert "`YT-A2-MAT-006G` | A2 材料状态文档收口" in text
    assert "`YT-A2-MAT-008` | 酒榷制度背景补强" in text
    assert "`YT-A2-MAT-009` | 贤良文学身份 Actor 证据归并" in text
    assert "`YT-A2-MAT-010` | A2 材料状态计数一致性测试" in text
    assert "《汉书·武帝纪》“初榷酒酤”" in text
    assert "贤良文学身份材料已归并到 `actor_literati`" in text
    assert "酒榷细节仍需后续任务补足" not in text
    assert "贤良文学身份仍需后续补足" not in text
    assert "如需进入主线轻提示，需另开任务验收" in text
    assert "经学透镜的退朝后分组、材料导览和 UI 呈现仍需后续任务补强" not in text
    assert "不修改 Schema、API、搜索逻辑、迁移或运行态数据" in text


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
    assert "YT-A2-MAT-005B" in text
    assert "6 条极短短摘正式写入 evidence pack" in text
    assert "不支撑 `original_fact` Claim" in text
    assert "不复制现代整理本、校注本、译本、论文或专著的长段内容" in text
    assert "本轮不修改 UI、API、Schema 或运行态数据" in text
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


def test_yantie_classics_context_plan_keeps_lens_boundary():
    text = CLASSICS_CONTEXT_PLAN.read_text(encoding="utf-8")

    assert "YT-A2-MAT-006" in text
    assert "董仲舒" in text
    assert "《汉书·董仲舒传》" in text
    assert "《汉书·武帝纪》" in text
    assert "《汉书·儒林传》" in text
    assert "《春秋公羊传》" in text
    assert "《春秋繁露》" in text
    assert "philosophy_lens" in text
    assert "不把董仲舒或《春秋繁露》当作盐铁会议现场证据" in text
    assert "不声称桑弘羊、贤良文学或霍光直接引用" in text
    assert "YT-A2-MAT-006C" in text
    assert "不新增 Claim，不修改 UI" in text
    assert "本阶段不修改 UI、API、公共 Schema 或运行态数据" in text
    assert "\n> " not in text


def test_yantie_classics_context_candidate_lenses_have_required_fields():
    text = CLASSICS_CONTEXT_PLAN.read_text(encoding="utf-8")
    cards = re.findall(r"^### (CLC-LENS-\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 6

    required_fields = [
        "- 材料方向：",
        "- 解释目标：",
        "- 对盐铁体验的作用：",
        "- 推荐标签：",
        "- 默认入口：",
        "- 入包条件：",
    ]

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("CLC-LENS-"):
            continue
        for field in required_fields:
            assert field in section


def test_yantie_hanshu_classics_verification_keeps_candidate_boundary():
    text = HANSHU_CLASSICS_VERIFICATION.read_text(encoding="utf-8")

    assert "YT-A2-MAT-006A" in text
    assert "YT-A2-MAT-006C" in text
    assert "《汉书·董仲舒传》" in text
    assert "《汉书·武帝纪》" in text
    assert "《汉书·儒林传》" in text
    assert "不支撑 `original_fact` Claim" in text
    assert "不作为盐铁会议现场事实" in text
    assert "本轮不修改 UI、API、Schema、evidence pack 或运行态数据" in text
    assert "\n> " not in text


def test_yantie_hanshu_classics_candidate_quotes_are_short_and_structured():
    text = HANSHU_CLASSICS_VERIFICATION.read_text(encoding="utf-8")
    cards = re.findall(r"^### (HSC-Q\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 12

    required_fields = [
        "- 材料层：",
        "- 候选短摘：",
        "- 出处：",
        "- 对应透镜：",
        "- 推荐标签：",
        "- 版本状态：candidate-from-ctext",
        "- 版权边界：",
        "- 入包判断：",
    ]
    excerpts = re.findall(r"- 候选短摘：`([^`]+)`", text)

    assert len(excerpts) == 12
    assert all(len(excerpt) <= 12 for excerpt in excerpts)

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("HSC-Q"):
            continue
        for field in required_fields:
            assert field in section


def test_yantie_chunqiu_fanlu_verification_keeps_textual_boundary():
    text = CHUNQIU_FANLU_VERIFICATION.read_text(encoding="utf-8")

    assert "YT-A2-MAT-006B" in text
    assert "YT-A2-MAT-006C" in text
    assert "《春秋繁露》" in text
    assert "传世文本" in text
    assert "作者归属" in text
    assert "received_text_authorship_debated" in text
    assert "不支撑 `original_fact` Claim" in text
    assert "不作为盐铁会议现场事实" in text
    assert "本轮不修改 UI、API、Schema、evidence pack 或运行态数据" in text
    assert "\n> " not in text


def test_yantie_chunqiu_fanlu_candidate_quotes_are_short_and_structured():
    text = CHUNQIU_FANLU_VERIFICATION.read_text(encoding="utf-8")
    cards = re.findall(r"^### (CFF-Q\d{3})：(.+)$", text, flags=re.MULTILINE)

    assert len(cards) == 12

    required_fields = [
        "- 材料层：",
        "- 候选短摘：",
        "- 对应透镜：",
        "- 推荐标签：",
        "- 版本状态：candidate-from-ctext",
        "- 文本性质：received_text_authorship_debated",
        "- 版权边界：",
        "- 入包判断：",
    ]
    excerpts = re.findall(r"- 候选短摘：`([^`]+)`", text)

    assert len(excerpts) == 12
    assert all(len(excerpt) <= 12 for excerpt in excerpts)

    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        if not section.startswith("CFF-Q"):
            continue
        for field in required_fields:
            assert field in section
