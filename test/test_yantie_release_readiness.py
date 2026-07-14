from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "reports" / "YT-A2-RELEASE-READINESS.md"
TASK_BREAKDOWN = ROOT / "docs" / "YANTIE_TASK_BREAKDOWN.md"


def test_yantie_a2_release_readiness_report_records_preview_status():
    text = REPORT.read_text(encoding="utf-8")

    assert "YT-A2-REL-001" in text
    assert "preview_ready_with_conditions" in text
    assert "GitHub Pages 静态预览版" in text
    assert "最终产品版" in text
    assert "生产级公开发布" in text
    assert "当前不适合作为" in text
    assert "当前分支仍有未推送提交" in text


def test_yantie_a2_release_readiness_report_records_release_risks():
    text = REPORT.read_text(encoding="utf-8")

    assert "36/36 checks passed" in text
    assert "83 passed" in text
    assert "power-silence" in text
    assert "Playwright" in text
    assert "external_echo" in text
    assert "不进入史证链" in text
    assert "live adapter" in text


def test_yantie_a2_release_readiness_task_card_is_complete():
    text = TASK_BREAKDOWN.read_text(encoding="utf-8")

    assert "A2REL001" in text
    assert "### YT-A2-REL-001：A2 发布适用性收口" in text

    section = text.split("### YT-A2-REL-001：A2 发布适用性收口", 1)[1]
    required_fields = [
        "任务 ID",
        "价值",
        "依赖",
        "允许修改范围",
        "禁止修改范围",
        "输入",
        "输出",
        "接口",
        "验收标准",
        "测试命令",
        "回滚方式",
        "文档更新",
    ]

    for field in required_fields:
        assert f"- {field}：" in section
