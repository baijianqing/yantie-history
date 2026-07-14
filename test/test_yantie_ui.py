from __future__ import annotations

import json
import re
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from metaos.yantie import create_yantie_web_app, export_yantie_static_site, render_yantie_static_html
from metaos.yantie.search import load_default_evidence_pack
from metaos.yantie.zhihu_adapter import ZhihuAdapterConfig, ZhihuExternalEchoAdapter


PACK_PATH = Path(__file__).resolve().parents[1] / "metaos" / "yantie" / "data" / "evidence_pack.json"


class YantieWebUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_yantie_web_app())

    def test_yantie_page_serves_immersive_scene_runtime(self) -> None:
        response = self.client.get("/yantie")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        self.assertIn('data-testid="immersive-yantie-scene"', html)
        self.assertIn('id="sceneCanvas"', html)
        self.assertIn('id="hanMapScene"', html)
        self.assertIn('id="courtScene"', html)
        self.assertIn('id="powerNetworkScene"', html)
        self.assertIn('id="debateHud"', html)
        self.assertIn('id="decisionDock"', html)
        self.assertIn('id="evidenceScrim"', html)
        self.assertIn('id="evidenceRibbon"', html)
        self.assertIn('id="judgmentForm"', html)
        self.assertIn('id="soundToggle"', html)

    def test_yantie_page_exposes_v3_court_pressure_opening(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('id="courtPressureOpening"', html)
        self.assertIn('data-drama-phase="map-pressure"', html)
        self.assertIn("is-prologue-active", html)
        self.assertIn("data-testid=\"han-restored-basemap\"", html)
        self.assertIn("renderHanRestoredBasemap", html)
        self.assertIn("mapPointForFeature", html)
        self.assertIn("复原叙事地图", html)
        self.assertIn("开源 GIS", html)
        self.assertIn('data-gis-mode="open-source-compatible"', html)
        self.assertIn("本地简化矢量层", html)
        self.assertIn("非精确测绘边界", html)
        self.assertIn("进入朝堂", html)
        self.assertIn("边费", html)
        self.assertIn("盐铁山海", html)
        self.assertIn("均输", html)
        self.assertIn("dramaPhase", html)
        self.assertIn("sceneProgress", html)
        self.assertIn("renderDramaOverlay", html)
        self.assertIn("dramaPhaseFor", html)
        self.assertIn("v3-map-pressure-routes", html)
        self.assertIn("v3-court-pressure-field", html)
        self.assertIn("财政压力", html)
        self.assertIn("民生反问", html)
        self.assertIn("权力边界", html)
        self.assertNotIn("v3-court-anchors", html)
        self.assertNotIn("court-anchor", html)
        self.assertNotIn("财政案席", html)
        self.assertNotIn("屏风权位", html)
        self.assertNotIn("竹简席位", html)
        self.assertNotIn("v3-court-silhouettes", html)
        self.assertNotIn("role-silhouette", html)
        self.assertNotIn("character-silhouette", html)
        self.assertIn("pressure-route", html)
        self.assertIn("new AudioContext()", html)

        forbidden_runtime_markers = [
            "ReactDOM",
            "from \"react\"",
            "from 'react'",
            "createRoot(",
            "vite/client",
            "gsap.",
            "pixi.js",
            "leaflet",
            "mapbox",
            "new THREE",
            "three.min",
        ]
        for marker in forbidden_runtime_markers:
            self.assertNotIn(marker, html)

    def test_yantie_page_exposes_v32_pressure_entry_and_standpoint_flow(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("const pressureTimeline = [", html)
        self.assertIn("const standpointRoles = [", html)
        self.assertIn("const experienceDirector = {", html)
        self.assertIn("stanceTrajectory", html)
        for phase in ["pressure_entry", "standpoint_choice", "court_debate", "power_reveal", "after_echo", "judgment"]:
            self.assertIn(phase, html)
        for pressure in ["边防", "府库", "民生", "商贾", "权力"]:
            self.assertIn(pressure, html)
        for role in ["国家财政官", "边疆将军", "地方百姓", "盐铁商人"]:
            self.assertIn(role, html)
        for pressure_node in ["武帝余响", "北边急报", "府库吃紧", "盐铁入官", "民户承压", "未央宫召议"]:
            self.assertIn(pressure_node, html)

        self.assertIn("证据支持强度", html)
        self.assertIn("不是绝对真相概率", html)
        self.assertIn('id="pressureDirectorPanel"', html)
        self.assertIn('id="stanceTrajectoryPanel"', html)
        self.assertIn("观点变化图", html)
        self.assertIn("selected_evidence_ids", html)
        self.assertIn("personal_reflection", html)
        self.assertIn("/judgment-cards", html)
        self.assertNotIn("v3-court-anchors", html)
        self.assertNotIn("role-silhouette", html)
        self.assertNotIn("character-silhouette", html)

    def test_yantie_page_hides_evidence_overlay_during_pressure_entry(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn(".stage.is-prologue-active #evidenceScrim", html)
        self.assertIn(".stage.is-prologue-active #evidenceRibbon", html)
        self.assertIn(".stage.is-prologue-active .evidence-seals", html)
        self.assertIn('id="pressureDirectorPanel"', html)

    def test_yantie_page_exposes_v33_restoration_feedback_runtime(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("const restorationSequence = [", html)
        self.assertIn("const restorationHotspots = {", html)
        self.assertIn('id="restorationStatusPanel"', html)
        self.assertIn('id="restorationDiscoveryPanel"', html)
        self.assertIn('data-testid="history-restoration-runtime"', html)
        self.assertIn("renderRestorationStatus", html)
        self.assertIn("showRestorationHotspot", html)
        self.assertIn("data-restoration-hotspot", html)
        self.assertIn("restoration-hotspot", html)
        self.assertIn("map-live-flow", html)
        self.assertIn("animateMotion", html)
        for feature_id in [
            "feature_changan",
            "feature_northern_frontier",
            "feature_jincheng",
            "feature_salt_iron_resources",
            "feature_equal_transport_routes",
        ]:
            self.assertIn(feature_id, html)
        self.assertIn("发现竹简", html)
        self.assertIn("发现案卷", html)
        self.assertIn("发现一份竹简", html)

    def test_yantie_page_reduces_duplicate_visible_copy(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("<h2>压力分布</h2>", html)
        self.assertIn("<span>证据支持</span>", html)
        self.assertIn("不是绝对真相概率", html)
        self.assertIn("带着立场入朝", html)
        self.assertNotIn("证据支持强度 ${Number(item.support.value)}", html)
        self.assertNotIn("<span>${escapeHtml(scene.kicker)}</span>", html)

    def test_yantie_page_has_overlap_resistant_layout_rules(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("overflow-wrap: anywhere", html)
        self.assertIn("max-height: min(44vh, 360px)", html)
        self.assertIn("max-height: min(28vh, 190px)", html)
        self.assertIn("max-height: min(42vh, 320px)", html)
        self.assertIn("max-height: min(52vh, 440px)", html)
        self.assertIn("max-height: calc(100% - 44px)", html)
        self.assertIn(".stage.is-prologue-active .scene-copy", html)
        self.assertIn("display: none", html)
        self.assertIn("height: 100dvh", html)
        self.assertIn("bottom: calc(env(safe-area-inset-bottom) + 12px)", html)
        self.assertIn("mobileMapPriority", html)
        self.assertIn('svg.setAttribute("preserveAspectRatio", "xMidYMid meet")', html)
        self.assertIn("mobileMapMode", html)
        self.assertIn("contain", html)
        self.assertIn("height: clamp(260px, calc(100dvh - 400px), 444px)", html)
        self.assertIn("max-height: calc(100dvh - 400px)", html)
        self.assertIn("max-height: min(34dvh, 220px)", html)
        self.assertIn("overscroll-behavior: contain", html)
        self.assertIn("touch-action: pan-y", html)
        self.assertIn(".restoration-discovery-panel.is-visible", html)
        self.assertIn("pointer-events: auto", html)
        self.assertNotIn("max-height: 86px", html)
        self.assertIn('.stage.is-prologue-active[data-experience-phase="pressure_entry"] .pressure-director-panel', html)
        self.assertIn("grid-template-columns: repeat(5, minmax(0, 1fr))", html)
        self.assertIn(".stage.is-prologue-active .scene-actions .ghost", html)
        self.assertIn("z-index: 70", html)
        self.assertIn(".judgment-output", html)
        self.assertIn("max-height: 96px", html)

    def test_yantie_page_is_guided_not_tab_driven(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('id="advanceScene"', html)
        self.assertIn('id="revealEvidence"', html)
        self.assertIn('id="rewindScene"', html)
        self.assertIn("const historicalPrelude = [", html)
        self.assertIn("const conflictActs = [", html)
        self.assertIn("const issueMatrix = [", html)
        self.assertIn("const scenes = [...historicalPrelude, ...conflictActs, judgmentScene].map", html)
        self.assertIn('"map"', html)
        self.assertIn('"court"', html)
        self.assertIn('"network"', html)
        self.assertIn('"judgment"', html)
        self.assertIn("scene-caption", html)
        self.assertIn("decision-dock", html)
        self.assertIn("evidence-scrim", html)
        self.assertIn("evidence-panel-head", html)
        self.assertIn("data-close-evidence", html)
        self.assertIn("choice-range", html)
        self.assertIn("state.userChoices", html)
        self.assertNotIn("debate-card", html)
        self.assertNotIn('id="debateHud").addEventListener("click"', html)
        self.assertNotIn('ribbon.classList.toggle("is-open")', html)
        self.assertNotIn('class="tabs"', html)
        self.assertNotIn('id="claimTabs"', html)

    def test_yantie_a1_main_experience_slice_contract_is_declared(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('data-experience-track="main-path"', html)
        self.assertIn('id: "main-experience-path"', html)
        self.assertNotIn('data-main-experience-slice="YT-A1-UI-001A"', html)
        self.assertNotIn('id: "YT-A1-UI-001A"', html)
        self.assertIn("keyEvidenceLimit: 1", html)
        self.assertIn("allowFullChapterMapBeforeDossier: false", html)
        for phase in [
            "pressure_entry",
            "first_choice",
            "perspective_formed",
            "court_entry",
            "fiscal_livelihood_conflict",
            "key_evidence",
            "judgment_shift",
            "power_silence",
            "retirement_dossier",
        ]:
            self.assertIn(phase, html)
        for hidden_surface in [
            "sixty_chapter_map",
            "full_philosophy_lenses",
            "long_evidence_reader",
            "contemporary_echo",
        ]:
            self.assertIn(hidden_surface, html)

    def test_yantie_a1_mainline_gates_deep_exploration_until_dossier(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("function isPostCourtUnlocked()", html)
        self.assertIn("function primaryEvidenceIdsForScene(scene)", html)
        self.assertIn("function syncMainExperienceControls()", html)
        self.assertIn("chapterButton.hidden = !postCourtUnlocked", html)
        self.assertIn("chapterButton.disabled = !postCourtUnlocked", html)
        self.assertIn('chapterButton.textContent = postCourtUnlocked ? "退朝后争点" : "退朝后开放"', html)
        self.assertIn("诸篇争锋将在退朝案牍后开放；当前主线只保留关键证据。", html)
        self.assertIn("primaryEvidenceIdsForScene(scene).map", html)
        self.assertIn('data-mainline-hidden="true"', html)
        self.assertIn('data-mainline-mode="${postCourtUnlocked ? "post-court" : "key-evidence"}"', html)
        self.assertIn("isPostCourtUnlocked() ? scene.evidence : primaryEvidenceIdsForScene(scene)", html)

    def test_yantie_a1_standpoint_choice_is_not_a_score_card(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("${escapeHtml(role.pressureFocus)}压力 · 入朝视角", html)
        self.assertIn("value: role.initialLeaning", html)
        self.assertNotIn("初始倾向 ${Number(role.initialLeaning)}/100", html)
        self.assertNotIn("匹配度", html)

    def test_yantie_judgment_dossier_input_is_not_covered_by_caption_hud(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('.stage[data-experience-phase="judgment"] .debate-hud', html)
        self.assertIn('.stage[data-experience-phase="judgment"] #judgmentSvg', html)
        self.assertIn('.stage[data-experience-phase="judgment"] .judgment-form', html)
        self.assertIn("opacity: 0.24", html)
        self.assertIn("opacity: 0.16", html)
        self.assertIn("display: none", html)
        self.assertIn("background: linear-gradient(180deg, #090d13, #0d1118)", html)
        self.assertIn("z-index: 12", html)

    def test_yantie_a1_post_court_explorer_is_gated_and_degraded(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('id="postCourtExplorer"', html)
        self.assertIn('aria-label="退朝后深度探索"', html)
        self.assertIn("postCourtExplorer.hidden = !postCourtUnlocked", html)
        for action in [
            "chapter-map",
            "philosophy-lens",
            "material-guide",
            "power-network",
            "external-echo",
        ]:
            self.assertIn(f'data-post-court-action="{action}"', html)
        self.assertNotIn('data-post-court-action="second-perspective"', html)
        for explore_type in [
            "historical_evidence",
            "philosophy_lens",
            "material_guide",
            "power_relation",
            "external_echo",
        ]:
            self.assertIn(f'data-explore-type="{explore_type}"', html)
        self.assertNotIn('data-explore-type="user_judgment"', html)
        self.assertIn('id="materialGuidePanel"', html)
        self.assertIn('data-material-boundary="post_court_only"', html)
        self.assertIn("function renderMaterialGuidePanel", html)
        self.assertIn("function openMaterialGuide", html)
        self.assertIn('if (action === "material-guide")', html)
        self.assertIn('id="externalEchoPanel"', html)
        self.assertIn("function isExternalEchoEnabled()", html)
        self.assertIn("function syncExternalEchoEntry(postCourtUnlocked)", html)
        self.assertIn("function renderExternalEchoPanel(message = null)", html)
        self.assertIn("async function openExternalEcho()", html)
        self.assertIn("externalButton.disabled = !enabled", html)
        self.assertIn('externalButton.dataset.echoEnabled = isExternalEchoEnabled() ? "live" : "curated"', html)
        self.assertIn("curatedExternalEchoItems", html)
        self.assertIn("/external/zhihu/search", html)
        self.assertIn("不进入证据包", html)
        self.assertIn("不支持历史事实判断", html)
        self.assertIn("查看后世评说与当代问题的摘要；只作延伸思考。", html)
        self.assertIn("退朝后开放全文争点；这里只读证据与解释边界，不改写案牍。", html)
        self.assertIn("正在回看权力遮蔽一幕；这不抹除你的退朝案牍。", html)
        self.assertIn("材料导览只在退朝后说明来源层级与进入边界", html)
        self.assertNotIn("查看 A2 补强材料", html)
        self.assertNotIn("A2 材料导览只在退朝后开放", html)

    def test_yantie_a2_post_court_material_guide_is_bounded(self) -> None:
        html = self.client.get("/yantie").text
        guide_match = re.search(
            r"const materialGuideEntries = (\[.*?\]);\n\n    const philosophyLensGroups =",
            html,
            re.S,
        )
        self.assertIsNotNone(guide_match)
        entries = json.loads(guide_match.group(1))
        entries_by_id = {entry["id"]: entry for entry in entries}

        self.assertEqual(
            set(entries_by_id),
            {
                "chronicle",
                "institutional_background",
                "textual_reception",
                "huang_lao_lens",
                "classics_context",
                "modern_research",
            },
        )
        self.assertEqual(entries_by_id["chronicle"]["source"], "《资治通鉴》卷023")
        self.assertEqual(entries_by_id["institutional_background"]["status"], "已入包 20 条")
        self.assertEqual(entries_by_id["huang_lao_lens"]["defaultEntry"], "思想透镜：黄老")
        self.assertEqual(entries_by_id["classics_context"]["defaultEntry"], "思想透镜：经学语境")
        self.assertIn("不交付论文或专著全文", entries_by_id["modern_research"]["boundary"])
        self.assertIn("始元六年诏问贤良文学", entries_by_id["chronicle"]["details"][0])
        self.assertIn("盐铁、均输、平准、酒榷", entries_by_id["institutional_background"]["details"][0])
        self.assertIn("道生法", entries_by_id["huang_lao_lens"]["details"][0])
        self.assertIn("不复制论文", entries_by_id["modern_research"]["details"][1])
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["source"])
            self.assertTrue(entry["status"])
            self.assertTrue(entry["defaultEntry"])
            self.assertTrue(entry["boundary"])
            self.assertGreaterEqual(len(entry["details"]), 3)

        self.assertIn("补充材料按用途分层展示", html)
        self.assertIn("退朝后开放 · 不自动写入案牍", html)
        self.assertNotIn("A2 补强材料按用途分层展示", html)
        self.assertNotIn('aria-label="A2 材料分层"', html)

    def test_yantie_user_facing_page_hides_internal_task_labels(self) -> None:
        html = self.client.get("/yantie").text

        self.assertNotIn("YT-A1", html)
        self.assertNotIn("YT-A2", html)
        self.assertNotIn("A1 ", html)
        self.assertNotIn("A2 ", html)

    def test_yantie_a2_post_court_philosophy_lenses_are_grouped(self) -> None:
        html = self.client.get("/yantie").text
        group_match = re.search(
            r"const philosophyLensGroups = (\[.*?\]);\n\n    const judgmentScene =",
            html,
            re.S,
        )
        self.assertIsNotNone(group_match)
        groups = json.loads(group_match.group(1))
        groups_by_id = {group["id"]: group for group in groups}

        self.assertEqual(
            set(groups_by_id),
            {"confucian", "legalist", "huang_lao", "institutional_state", "classics_context"},
        )
        self.assertEqual([group["label"] for group in groups], ["儒家", "法家", "黄老", "制度国家", "经学语境"])
        self.assertEqual(
            groups_by_id["huang_lao"]["evidenceIds"],
            [
                "ev:src_huangdi_sijing:jingfa:dao_generates_law:a2d50001",
                "ev:src_huangdi_sijing:jingfa:law_standard_rectification:a2d50002",
                "ev:src_huangdi_sijing:shiliujing:reduce_harsh_affairs:a2d50003",
                "ev:src_huangdi_sijing:shiliujing:do_not_seize_people_time:a2d50004",
                "ev:src_huangdi_sijing:cheng:name_reality_alignment:a2d50005",
                "ev:src_huangdi_sijing:shiliujing:utmost_stillness_sage:a2d50006",
            ],
        )
        self.assertEqual(
            groups_by_id["classics_context"]["evidenceIds"],
            [
                "ev:src_hanshu_dong_zhongshu:zhuan:school_officials:a2d60001",
                "ev:src_hanshu_wudi:zan:six_classics:a2d60002",
                "ev:src_hanshu_rulin:zhuan:doctor_disciples:a2d60003",
                "ev:src_chunqiu_fanlu:jiyi:virtue_over_punishment:a2d60004",
                "ev:src_chunqiu_fanlu:renfutianshu:heaven_human_correspondence:a2d60005",
                "ev:src_chunqiu_fanlu:sandai:mandate_legitimacy:a2d60006",
            ],
        )
        for group in groups:
            self.assertIn("思想透镜，不是会议事实", group["boundary"])
            self.assertTrue(group["summary"])
            self.assertTrue(group["evidenceIds"])

        self.assertIn('id="philosophyLensPanel"', html)
        self.assertIn('data-lens-boundary="philosophy_lens"', html)
        self.assertIn("function renderPhilosophyLensPanel", html)
        self.assertIn("function openPhilosophyLensExplorer", html)
        self.assertIn("data-lens-evidence-id", html)
        self.assertIn('if (action === "philosophy-lens")', html)
        self.assertIn("openPhilosophyLensExplorer()", html)
        self.assertIn("经学、黄老、儒家、法家和制度国家只在退朝后开放", html)
        self.assertIn("ev:src_chunqiu_fanlu:jiyi:virtue_over_punishment:a2d60004", html)

    def test_yantie_runtime_external_echo_mock_path_is_post_court_only(self) -> None:
        pack = load_default_evidence_pack()
        claim_count_before = len(pack.claims)
        evidence_count_before = len(pack.evidence_units)

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/v1/content/zhihu_search")
            self.assertEqual(request.url.params["count"], "3")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "title": "当代讨论：国家、市场与民生",
                                "url": "https://www.zhihu.com/question/yantie-example",
                                "summary": "只作为退朝后的外部回声，不属于会议史实证据。",
                            }
                        ]
                    }
                },
            )

        adapter = ZhihuExternalEchoAdapter(
            ZhihuAdapterConfig(access_secret="mock-secret"),
            transport=httpx.MockTransport(handler),
        )
        client = TestClient(create_yantie_web_app(external_echo_adapter=adapter))

        manifest = client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertTrue(manifest.json()["data"]["features"]["external_echo_enabled"])

        html = client.get("/yantie").text
        self.assertIn("function syncExternalEchoEntry(postCourtUnlocked)", html)
        self.assertIn('data-post-court-action="external-echo"', html)
        self.assertIn("externalButton.disabled = !enabled", html)
        self.assertIn("externalBoundaryLabel(item.source_boundary)", html)

        response = client.get(
            "/api/yantie/external/zhihu/search",
            params={"q": "盐铁会议 国家 市场 民生", "count": 3},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["source_boundary"], "external_echo")
        self.assertFalse(data["can_support_claims"])
        self.assertFalse(data["writes_to_evidence_pack"])
        self.assertEqual(data["items"][0]["source_boundary"], "external_echo")
        self.assertEqual(data["items"][0]["title"], "当代讨论：国家、市场与民生")
        self.assertEqual(len(pack.claims), claim_count_before)
        self.assertEqual(len(pack.evidence_units), evidence_count_before)

    def test_yantie_a1_screenshot_acceptance_scenarios_are_declared(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn("const acceptanceScenarios = [", html)
        self.assertIn("function applyAcceptanceScenarioFromQuery()", html)
        self.assertIn('new URLSearchParams(window.location.search).get("acceptance")', html)
        self.assertIn("stage.dataset.acceptanceScenario = scenario.id", html)
        self.assertIn("sceneIndexForAcceptanceScenario(scenario)", html)
        self.assertIn("seedAcceptanceTrajectory(scenario)", html)
        self.assertIn("await applyAcceptanceScenarioFromQuery()", html)
        self.assertIn("openKeyEvidence", html)
        self.assertIn("expandPostCourtExplorer", html)
        self.assertIn("viewportTags", html)
        self.assertIn("failLevel", html)
        for scenario in [
            "opening-map",
            "first-choice",
            "standpoint-entry",
            "court-entry",
            "fiscal-livelihood",
            "key-evidence",
            "power-silence",
            "retirement-dossier",
            "post-court-explorer",
        ]:
            self.assertIn(f'id: "{scenario}"', html)

    def test_yantie_a1_acceptance_runner_tracks_declared_scenarios(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "scripts" / "check-yantie-acceptance.mjs").read_text(
            encoding="utf-8"
        )

        self.assertIn("const scenarios = [", script)
        self.assertIn("const viewports = [", script)
        self.assertIn("inspectScenario(page, scenario, viewport)", script)
        self.assertIn("function pageScenarioFor(scenario)", script)
        self.assertIn(
            'scenario === "external-echo-boundary"',
            script,
        )
        self.assertIn("page.waitForFunction", script)
        self.assertIn('scenario === "retirement-dossier" ||', script)
        self.assertIn('scenario === "philosophy-lens"', script)
        self.assertIn('Number(window.getComputedStyle(document.querySelector(".judgment-form")).opacity', script)
        self.assertIn('[data-post-court-action="material-guide"]', script)
        self.assertIn('[data-post-court-action="philosophy-lens"]', script)
        self.assertIn('[data-post-court-action="external-echo"]', script)
        self.assertIn("#materialGuidePanel", script)
        self.assertIn("#philosophyLensPanel", script)
        self.assertIn("#externalEchoPanel", script)
        self.assertIn("reducedMotion: \"reduce\"", script)
        self.assertIn("dossier overlaps debate HUD", script)
        self.assertIn("judgment backdrop too prominent", script)
        self.assertIn("post-court details not expanded", script)
        self.assertIn("material guide boundary missing", script)
        self.assertIn("material guide has no cards", script)
        self.assertIn("philosophy lens boundary missing", script)
        self.assertIn("philosophy lens has no evidence buttons", script)
        self.assertIn("external echo entry disabled", script)
        self.assertIn("external echo panel hidden after action", script)
        self.assertIn("external echo boundary hint missing", script)
        self.assertIn("Manual review recommended", script)
        for scenario in [
            "opening-map",
            "first-choice",
            "standpoint-entry",
            "court-entry",
            "fiscal-livelihood",
            "key-evidence",
            "power-silence",
            "retirement-dossier",
            "post-court-explorer",
            "material-guide",
            "philosophy-lens",
            "external-echo-boundary",
        ]:
            self.assertIn(f'"{scenario}"', script)

    def test_yantie_page_stages_background_before_five_conflict_acts(self) -> None:
        html = self.client.get("/yantie").text

        for keyword in ["武帝余响", "诏问民疾苦", "财政先声", "民生反击", "义利显形", "治道复杂化", "权力遮蔽", "退朝"]:
            self.assertIn(keyword, html)

        for visual_mode in [
            "background-map",
            "meeting-open",
            "fiscal-ascendant",
            "livelihood-counter",
            "yi-li-clash",
            "statecraft-complexity",
            "power-shadow",
            "archive-closure",
        ]:
            self.assertIn(visual_mode, html)

        self.assertEqual(html.count('"visualMode":'), 8)
        self.assertEqual(html.count('"revealedConflict":'), 8)
        self.assertEqual(html.count('"choicePrompt":'), 5)
        self.assertGreaterEqual(html.count('"historicalEvidence": ['), 8)
        self.assertGreaterEqual(html.count('"philosophyLens": ['), 8)
        self.assertIn("evidence-seal", html)
        self.assertIn("issue-pill", html)
        self.assertIn("退朝案牍", html)

    def test_yantie_page_exposes_issue_matrix_without_chapter_player(self) -> None:
        html = self.client.get("/yantie").text

        for issue in ["盐铁", "酒榷", "均输", "平准", "边防", "农桑", "商工", "奢俭", "吏治", "教化", "义利", "权力", "后世评价"]:
            self.assertIn(issue, html)

        self.assertIn("ev:src_lunyu_liren:liren04:yi_li_lens:aa110001", html)
        self.assertIn("ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003", html)
        self.assertIn("五幕显影选择", html)
        self.assertNotIn("第60回合", html)
        self.assertNotIn("yantielunChapters", html)

    def test_yantie_page_exposes_sixty_chapter_conflict_map(self) -> None:
        html = self.client.get("/yantie").text

        match = re.search(r"const chapterConflictMap = (\[.*?\]);\n\n    const philosophyLensMeta =", html, re.S)
        self.assertIsNotNone(match)
        chapter_map = json.loads(match.group(1))

        self.assertEqual(len(chapter_map), 60)
        self.assertEqual(chapter_map[0]["title"], "本议第一")
        self.assertEqual(chapter_map[1]["title"], "力耕第二")
        self.assertEqual(chapter_map[28]["title"], "散不足第二十九")
        self.assertEqual(chapter_map[35]["title"], "水旱第三十六")
        self.assertEqual(chapter_map[55]["title"], "申韩第五十六")
        self.assertEqual(chapter_map[-1]["title"], "杂论第六十")
        self.assertEqual([item["chapterNumber"] for item in chapter_map], list(range(1, 61)))
        for item in chapter_map:
            self.assertTrue(item["historicalEvidence"], item["title"])
            self.assertTrue(item["philosophyLens"], item["title"])
            self.assertTrue(item["conflict"], item["title"])
        self.assertIn('id="chapterMapToggle"', html)
        self.assertIn('id="chapterMapPanel"', html)
        self.assertIn("buildChapterVisitSummary", html)

    def test_yantie_chapter_lenses_are_named_and_valid(self) -> None:
        html = self.client.get("/yantie").text
        chapter_match = re.search(
            r"const chapterConflictMap = (\[.*?\]);\n\n    const philosophyLensMeta =",
            html,
            re.S,
        )
        meta_match = re.search(
            r"const philosophyLensMeta = (\{.*?\});\n\n    const issueMatrix =",
            html,
            re.S,
        )
        self.assertIsNotNone(chapter_match)
        self.assertIsNotNone(meta_match)
        chapter_map = json.loads(chapter_match.group(1))
        lens_meta = json.loads(meta_match.group(1))
        pack_payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        valid_lens_ids = {
            evidence["evidence_id"]
            for evidence in pack_payload["evidence_units"]
            if "philosophy_lens" in evidence["value_tags"]
        }

        self.assertGreaterEqual(len(lens_meta), 30)
        for chapter in chapter_map:
            self.assertTrue(chapter["philosophyLens"], chapter["title"])
            for evidence_id in chapter["philosophyLens"]:
                self.assertIn(evidence_id, valid_lens_ids, chapter["title"])
                self.assertIn(evidence_id, lens_meta, chapter["title"])
                self.assertTrue(lens_meta[evidence_id]["label"], evidence_id)
                self.assertTrue(lens_meta[evidence_id]["note"], evidence_id)

        self.assertIn("lens-section-title", html)
        self.assertIn("lensMetaFor", html)
        self.assertIn("\\u4e49\\u5229\\u4e4b\\u8fa8", json.dumps(lens_meta, ensure_ascii=True))
        self.assertIn("\\u601d\\u60f3\\u900f\\u955c\\uff0c\\u4e0d\\u662f\\u4f1a\\u8bae\\u4e8b\\u5b9e", json.dumps(html, ensure_ascii=True))
        self.assertNotIn("ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa", {
            evidence_id for chapter in chapter_map for evidence_id in chapter["philosophyLens"]
        })

    def test_yantie_page_uses_only_yantie_api_surface_and_local_audio(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('const apiBase = "/api/yantie";', html)
        self.assertIn('const yantieRuntimeMode = document.documentElement.dataset.yantieRuntime || "api";', html)
        self.assertIn('const staticPackUrl = "data/evidence_pack.json";', html)
        self.assertIn('narrative: { src: "assets/audio/narrative.mp3"', html)
        self.assertIn('debate: { src: "assets/audio/debate.mp3"', html)
        self.assertIn('reflection: { src: "assets/audio/reflection.mp3"', html)
        self.assertIn("syncMusicToExperience", html)
        self.assertIn("activateMusicTrack", html)
        self.assertIn("getStaticData", html)
        self.assertIn("createStaticJudgmentCard", html)
        self.assertIn('getData("/manifest")', html)
        self.assertIn('getData("/claims")', html)
        self.assertIn('/judgment-cards"', html)
        self.assertIn("new AudioContext()", html)
        self.assertNotIn("/alpha/", html)
        self.assertIn('/external/zhihu/search', html)
        self.assertNotIn("developer.zhihu.com", html.lower())
        self.assertNotIn("access_secret", html.lower())
        self.assertNotIn("YANTIE_ZHIHU_ACCESS_SECRET", html)
        self.assertNotIn("elevenlabs", html.lower())
        self.assertNotIn("suno", html.lower())
        self.assertNotIn("runway", html.lower())

    def test_yantie_static_html_uses_github_pages_data_adapter(self) -> None:
        html = render_yantie_static_html()

        self.assertIn('<html lang="zh-CN" data-yantie-runtime="static">', html)
        self.assertIn('static_github_pages: true', html)
        self.assertIn("loadStaticPack", html)
        self.assertIn("staticSearchEvidence", html)
        self.assertIn("static_judgment:", html)
        self.assertIn("data/evidence_pack.json", html)
        self.assertNotIn("workers.dev", html.lower())

    def test_yantie_static_site_export_writes_pages_bundle(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            target = export_yantie_static_site(Path(tmp_dir) / "yantie")

            index_path = target / "index.html"
            pack_path = target / "data" / "evidence_pack.json"
            self.assertTrue(index_path.exists())
            self.assertTrue(pack_path.exists())
            self.assertTrue((target / ".nojekyll").exists())
            self.assertTrue((target / "assets" / "audio" / "narrative.mp3").exists())
            self.assertTrue((target / "assets" / "audio" / "debate.mp3").exists())
            self.assertTrue((target / "assets" / "audio" / "reflection.mp3").exists())
            self.assertIn('data-yantie-runtime="static"', index_path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(pack_path.read_text(encoding="utf-8"))["pack_id"], "yantie_meeting_v1")

    def test_standalone_app_serves_ui_and_api_together(self) -> None:
        ui_response = self.client.get("/")
        self.assertEqual(ui_response.status_code, 200)
        self.assertEqual(str(ui_response.url).rstrip("/"), "http://testserver/yantie")

        manifest = self.client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["data"]["pack_id"], "yantie_meeting_v1")

        search = self.client.get(
            "/api/yantie/evidence/search",
            params={"q": "\u4f1a\u8bae \u7ed3\u679c", "limit": 3},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["data"]["archive_status"], "ok")


if __name__ == "__main__":
    unittest.main()
