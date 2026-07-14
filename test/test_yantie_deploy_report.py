from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "reports" / "YT-A2-DEPLOY-001.md"
TASK_BREAKDOWN = ROOT / "docs" / "YANTIE_TASK_BREAKDOWN.md"


def test_yantie_a2_deploy_report_records_deployed_static_preview():
    text = REPORT.read_text(encoding="utf-8")

    assert "YT-A2-DEPLOY-001" in text
    assert "deployed_static_preview" in text
    assert "codex/yantie-main-experience-slice -> a637871" in text
    assert "yantie-static-github-pages -> a637871" in text
    assert "不是强制覆盖" in text


def test_yantie_a2_deploy_report_records_online_acceptance():
    text = REPORT.read_text(encoding="utf-8")

    assert "https://baijianqing.github.io/yantie-history/yantie/" in text
    assert "36/36 checks passed" in text
    assert "power-silence" in text
    assert "A2 退朝后材料导览" in text
    assert "不再停留在旧版本" in text


def test_yantie_a2_deploy_report_keeps_release_boundary():
    text = REPORT.read_text(encoding="utf-8")

    assert "GitHub Pages 静态预览版" in text
    assert "最终产品版" in text
    assert "生产级公开发布" in text
    assert "external_echo" in text
    assert "不进入史证链" in text
    assert "YT-A2-E2E-002" in text
    assert "YT-A2-REL-002" in text
    assert "YT-A2-DOC-001" in text
    assert "YT-A2-MAIN-001" in text


def test_yantie_a2_deploy_task_card_is_complete():
    text = TASK_BREAKDOWN.read_text(encoding="utf-8")

    assert "A2DEPLOY001" in text
    assert "### YT-A2-DEPLOY-001：A2 Pages 静态部署记录" in text

    section = text.split("### YT-A2-DEPLOY-001：A2 Pages 静态部署记录", 1)[1]
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
