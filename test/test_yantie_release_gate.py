from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "reports" / "YT-A2-E2E-001.md"
TASK_BREAKDOWN = ROOT / "docs" / "YANTIE_TASK_BREAKDOWN.md"


def test_yantie_a2_release_gate_records_blocked_deploy_status():
    text = REPORT.read_text(encoding="utf-8")

    assert "YT-A2-E2E-001" in text
    assert "blocked_deploy_pending" in text
    assert "passed_static_candidate" in text
    assert "blocked_stale_deployment" in text
    assert "not_authorized" in text
    assert "当前线上 Pages 不能宣布为最新版本发布通过" in text


def test_yantie_a2_release_gate_records_local_and_remote_checks():
    text = REPORT.read_text(encoding="utf-8")

    assert "36/36 checks passed" in text
    assert "87 passed" in text
    assert "382 passed" in text
    assert "https://baijianqing.github.io/yantie-history/yantie/" in text
    assert "[data-post-court-action=\"material-guide\"]" in text
    assert "线上 Pages 很可能仍是旧版本" in text


def test_yantie_a2_release_gate_keeps_manual_review_and_next_steps():
    text = REPORT.read_text(encoding="utf-8")

    assert "power-silence" in text
    assert "人工观感复核" in text
    assert "passed_static_preview" in text
    assert "YT-A2-DEPLOY-001" in text
    assert "YT-A2-E2E-002" in text
    assert "YT-A2-REL-002" in text
    assert "下一步应优先完成部署和线上复验" in text


def test_yantie_a2_release_gate_task_card_is_complete():
    text = TASK_BREAKDOWN.read_text(encoding="utf-8")

    assert "A2E2E001" in text
    assert "### YT-A2-E2E-001：A2 静态发布门报告" in text

    section = text.split("### YT-A2-E2E-001：A2 静态发布门报告", 1)[1]
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
