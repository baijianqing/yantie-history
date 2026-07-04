"""Immersive web surface for the Yantie meeting reconstruction."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from metaos import __version__
from metaos.yantie.api import create_yantie_api_router


def create_yantie_web_router() -> APIRouter:
    """Serve the browser experience without a frontend build step."""

    router = APIRouter(tags=["yantie-web"])

    @router.get("/", include_in_schema=False)
    def redirect_home() -> RedirectResponse:
        return RedirectResponse("/yantie")

    @router.get("/yantie", response_class=HTMLResponse)
    def yantie_home() -> HTMLResponse:
        return HTMLResponse(YANTIE_HTML)

    return router


def create_yantie_web_app() -> FastAPI:
    """Create a standalone app for local playtesting and screenshots."""

    app = FastAPI(title="Yantie Meeting Reconstruction", version=__version__)
    app.include_router(create_yantie_api_router())
    app.include_router(create_yantie_web_router())
    return app


YANTIE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>盐铁会议历史复原</title>
  <style>
    :root {
      --ink: #101820;
      --paper: #efe3c4;
      --paper-soft: #f7edd2;
      --night: #121926;
      --blood: #9a241c;
      --gold: #c49245;
      --jade: #2c7a66;
      --steel: #36516c;
      --ash: #64748b;
      --line: rgba(255, 236, 188, 0.36);
      --shadow: 0 22px 80px rgba(0, 0, 0, 0.34);
    }

    * { box-sizing: border-box; }

    html, body { min-height: 100%; }

    body {
      margin: 0;
      overflow-x: hidden;
      background: #090d13;
      color: #fff4d6;
      font-family: "Noto Serif SC", "Songti SC", "Microsoft YaHei", serif;
    }

    button, textarea {
      font: inherit;
    }

    button {
      min-height: 42px;
      border: 1px solid rgba(255, 236, 188, 0.42);
      border-radius: 6px;
      background: rgba(16, 24, 32, 0.74);
      color: #fff4d6;
      cursor: pointer;
      padding: 9px 14px;
    }

    button:hover, button:focus-visible {
      border-color: #f3c46d;
      outline: 2px solid rgba(243, 196, 109, 0.18);
      outline-offset: 2px;
    }

    .stage {
      position: relative;
      min-height: 100vh;
      overflow: hidden;
      isolation: isolate;
      background:
        linear-gradient(180deg, rgba(9, 13, 19, 0.24), rgba(9, 13, 19, 0.92)),
        radial-gradient(circle at 50% 12%, rgba(196, 146, 69, 0.28), transparent 36%),
        #090d13;
    }

    .scene-canvas {
      position: fixed;
      inset: 0;
      width: 100vw;
      height: 100vh;
      z-index: -3;
      background: #111927;
    }

    .grain {
      position: fixed;
      inset: 0;
      z-index: -2;
      pointer-events: none;
      opacity: 0.22;
      background-image:
        linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px),
        linear-gradient(0deg, rgba(255,255,255,0.06) 1px, transparent 1px);
      background-size: 36px 36px;
      mix-blend-mode: soft-light;
    }

    .vignette {
      position: fixed;
      inset: 0;
      z-index: -1;
      pointer-events: none;
      background:
        radial-gradient(circle at center, transparent 0 42%, rgba(3, 6, 10, 0.38) 74%, rgba(3, 6, 10, 0.72) 100%),
        linear-gradient(90deg, rgba(5,8,12,0.52), transparent 22% 78%, rgba(5,8,12,0.52));
    }

    .topline {
      position: fixed;
      left: 0;
      right: 0;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px clamp(16px, 4vw, 48px);
      background: linear-gradient(180deg, rgba(9,13,19,0.92), rgba(9,13,19,0.12));
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .seal {
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border-radius: 6px;
      background: var(--blood);
      color: white;
      font-weight: 800;
      box-shadow: 0 8px 26px rgba(154,36,28,0.35);
    }

    .brand strong {
      display: block;
      font-size: 18px;
      line-height: 1.15;
      white-space: nowrap;
    }

    .brand span, .scene-meter {
      color: rgba(255,244,214,0.74);
      font-size: 12px;
      line-height: 1.35;
    }

    .top-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .sound-toggle[aria-pressed="true"] {
      background: rgba(196, 146, 69, 0.22);
      border-color: rgba(243, 196, 109, 0.82);
    }

    .scene-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(320px, 0.9fr) minmax(420px, 1.1fr);
      gap: clamp(18px, 5vw, 70px);
      align-items: center;
      padding: 92px clamp(16px, 5vw, 72px) 88px;
    }

    .story-panel {
      max-width: 760px;
      min-width: 0;
    }

    .chapter-kicker {
      color: #f3c46d;
      font-size: 14px;
      font-weight: 700;
      margin: 0 0 14px;
    }

    .scene-title {
      margin: 0;
      font-size: clamp(42px, 6.5vw, 92px);
      line-height: 1.02;
      letter-spacing: 0;
      text-wrap: balance;
      text-shadow: 0 12px 38px rgba(0,0,0,0.34);
    }

    .scene-copy {
      max-width: 660px;
      margin: 18px 0 0;
      color: rgba(255,244,214,0.9);
      font-size: clamp(16px, 1.7vw, 21px);
      line-height: 1.75;
    }

    .quote-line {
      min-height: 80px;
      margin: 20px 0 0;
      padding: 16px 18px;
      border-left: 4px solid var(--blood);
      background: rgba(9,13,19,0.46);
      color: #ffe7b0;
      line-height: 1.8;
      box-shadow: var(--shadow);
    }

    .scene-actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 26px;
    }

    .primary {
      background: #fff4d6;
      border-color: #fff4d6;
      color: #111927;
      font-weight: 700;
    }

    .ghost {
      background: rgba(9,13,19,0.28);
    }

    .scene-world {
      position: relative;
      min-height: 640px;
      border: 1px solid rgba(255,236,188,0.24);
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(255,244,214,0.08), rgba(9,13,19,0.4));
      overflow: hidden;
      box-shadow: var(--shadow);
    }

    .debate-hud {
      position: absolute;
      left: 18px;
      right: 18px;
      top: 18px;
      z-index: 8;
      display: grid;
      gap: 12px;
      pointer-events: none;
    }

    .debate-card {
      display: grid;
      gap: 10px;
      max-width: 620px;
      padding: 14px 16px;
      border: 1px solid rgba(255,236,188,0.28);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(9,13,19,0.84), rgba(9,13,19,0.52));
      box-shadow: 0 18px 52px rgba(0,0,0,0.28);
      backdrop-filter: blur(10px);
    }

    .debate-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      color: rgba(255,244,214,0.72);
      font-size: 12px;
      font-weight: 700;
    }

    .debate-speaker {
      color: #fff4d6;
      font-size: 18px;
    }

    .stance-chip {
      border: 1px solid rgba(243,196,109,0.45);
      border-radius: 999px;
      padding: 3px 8px;
      color: #f3c46d;
    }

    .debate-line {
      margin: 0;
      color: #ffe7b0;
      font-size: clamp(17px, 2vw, 22px);
      line-height: 1.65;
    }

    .conflict-question {
      margin: 0;
      color: rgba(255,244,214,0.9);
      font-size: 14px;
      line-height: 1.6;
    }

    .voice-pair {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .voice-chip {
      min-width: 0;
      border: 1px solid rgba(255,236,188,0.18);
      border-radius: 8px;
      padding: 8px;
      background: rgba(255,244,214,0.07);
    }

    .voice-chip strong {
      display: block;
      color: #f3c46d;
      font-size: 12px;
      margin-bottom: 3px;
    }

    .voice-chip span {
      display: block;
      color: rgba(255,244,214,0.8);
      font-size: 13px;
      line-height: 1.55;
    }

    .tension-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }

    .tension-axis {
      display: grid;
      gap: 5px;
      min-width: 0;
      color: rgba(255,244,214,0.72);
      font-size: 12px;
    }

    .tension-axis span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .tension-track {
      position: relative;
      height: 5px;
      border-radius: 999px;
      background: rgba(255,244,214,0.16);
      overflow: hidden;
    }

    .tension-fill {
      position: absolute;
      inset: 0 auto 0 0;
      display: block;
      height: 100%;
      border-radius: inherit;
      background: #f3c46d;
      transform-origin: left center;
      transition: width 500ms ease;
    }

    .tension-fill.is-before {
      background: rgba(255,244,214,0.24);
    }

    .tension-fill.is-after {
      background: linear-gradient(90deg, #f3c46d, #fff4d6);
      box-shadow: 0 0 12px rgba(243,196,109,0.45);
    }

    .choice-panel {
      display: grid;
      gap: 6px;
      padding-top: 2px;
    }

    .choice-panel label {
      color: rgba(255,244,214,0.84);
      font-size: 13px;
      line-height: 1.55;
    }

    .choice-row {
      display: grid;
      grid-template-columns: minmax(56px, auto) 1fr minmax(56px, auto);
      align-items: center;
      gap: 8px;
      color: rgba(255,244,214,0.68);
      font-size: 12px;
      font-weight: 700;
    }

    .choice-range {
      width: 100%;
      accent-color: #f3c46d;
    }

    .issue-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: rgba(255,244,214,0.72);
      font-size: 12px;
    }

    .issue-pill {
      border: 1px solid rgba(255,236,188,0.18);
      border-radius: 999px;
      padding: 4px 8px;
      background: rgba(9,13,19,0.28);
    }

    .evidence-seals {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      pointer-events: auto;
    }

    .evidence-seal {
      min-height: 32px;
      padding: 5px 9px;
      border-color: rgba(255,236,188,0.28);
      background: rgba(154,36,28,0.36);
      color: #fff4d6;
      font-size: 12px;
      font-weight: 700;
    }

    .map-layer,
    .court-layer,
    .network-layer,
    .judgment-layer {
      position: absolute;
      inset: 0;
      opacity: 0;
      transform: scale(1.03);
      transition: opacity 680ms ease, transform 900ms ease;
      pointer-events: none;
    }

    .map-layer.is-active,
    .court-layer.is-active,
    .network-layer.is-active,
    .judgment-layer.is-active {
      opacity: 1;
      transform: scale(1);
    }

    .map-layer svg,
    .court-layer svg,
    .network-layer svg,
    .judgment-layer svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .evidence-ribbon {
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 18px;
      display: grid;
      gap: 8px;
      max-height: 38%;
      overflow: auto;
      padding: 12px;
      border: 1px solid rgba(255,236,188,0.26);
      border-radius: 8px;
      background: rgba(9,13,19,0.74);
      backdrop-filter: blur(10px);
      transform: translateY(calc(100% + 24px));
      transition: transform 360ms ease;
      pointer-events: auto;
    }

    .evidence-ribbon.is-open {
      transform: translateY(0);
    }

    .evidence-item {
      display: grid;
      gap: 4px;
      border-left: 3px solid rgba(243,196,109,0.7);
      padding-left: 10px;
    }

    .evidence-item strong {
      color: #fff4d6;
      line-height: 1.5;
      font-size: 15px;
    }

    .evidence-item span {
      color: rgba(255,244,214,0.72);
      line-height: 1.55;
      font-size: 13px;
    }

    .timeline-rail {
      position: fixed;
      left: clamp(16px, 4vw, 48px);
      right: clamp(16px, 4vw, 48px);
      bottom: 18px;
      z-index: 12;
      display: grid;
      gap: 6px;
      pointer-events: none;
    }

    .rail-step {
      height: 4px;
      border-radius: 999px;
      background: rgba(255,244,214,0.18);
      overflow: hidden;
    }

    .rail-step span {
      display: block;
      height: 100%;
      width: 0;
      background: #f3c46d;
      transition: width 520ms ease;
    }

    .rail-step.is-past span,
    .rail-step.is-current span {
      width: 100%;
    }

    .judgment-form {
      position: absolute;
      inset: auto 22px 22px 22px;
      display: grid;
      gap: 10px;
      pointer-events: auto;
      opacity: 0;
      transform: translateY(18px);
      transition: opacity 500ms ease, transform 500ms ease;
    }

    .judgment-layer.is-active .judgment-form {
      opacity: 1;
      transform: translateY(0);
    }

    textarea {
      min-height: 114px;
      width: 100%;
      resize: vertical;
      border: 1px solid rgba(255,236,188,0.36);
      border-radius: 8px;
      background: rgba(9,13,19,0.72);
      color: #fff4d6;
      padding: 12px;
      line-height: 1.7;
    }

    .judgment-output {
      min-height: 90px;
      color: rgba(255,244,214,0.82);
      line-height: 1.65;
      white-space: pre-wrap;
    }

    .scene-footnote {
      position: fixed;
      right: clamp(16px, 4vw, 48px);
      bottom: 34px;
      z-index: 12;
      max-width: 360px;
      color: rgba(255,244,214,0.64);
      font-size: 12px;
      line-height: 1.55;
      text-align: right;
      pointer-events: none;
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
      }
    }

    @media (max-width: 980px) {
      .scene-shell {
        grid-template-columns: 1fr;
        padding-top: 92px;
      }

      .scene-world {
        min-height: 520px;
      }

      .scene-footnote {
        display: none;
      }
    }

    @media (max-width: 640px) {
      .topline {
        align-items: flex-start;
        flex-direction: column;
        padding: 12px 16px;
      }

      .top-actions {
        width: 100%;
        justify-content: space-between;
      }

      .scene-shell {
        padding: 126px 14px 42px;
      }

      .scene-title {
        font-size: 38px;
        line-height: 1.06;
      }

      .scene-copy {
        font-size: 16px;
        line-height: 1.72;
      }

      .quote-line {
        min-height: 82px;
        padding: 12px;
      }

      .scene-world {
        min-height: 440px;
      }

      .debate-hud {
        left: 10px;
        right: 10px;
        top: 10px;
      }

      .debate-card {
        padding: 11px;
      }

      .voice-pair {
        grid-template-columns: 1fr;
      }

      .tension-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .choice-row {
        grid-template-columns: 1fr;
      }

      .timeline-rail {
        left: 14px;
        right: 14px;
      }
    }
  </style>
</head>
<body>
  <main class="stage" data-testid="immersive-yantie-scene">
    <canvas id="sceneCanvas" class="scene-canvas" aria-hidden="true"></canvas>
    <div class="grain" aria-hidden="true"></div>
    <div class="vignette" aria-hidden="true"></div>

    <header class="topline">
      <div class="brand">
        <div class="seal" aria-hidden="true">盐</div>
        <div>
          <strong>盐铁会议</strong>
          <span>始元六年 · 朝堂复原</span>
        </div>
      </div>
      <div class="top-actions">
        <span class="scene-meter" id="packStatus">读取史料中</span>
        <button id="soundToggle" class="sound-toggle" type="button" aria-pressed="false">声场</button>
      </div>
    </header>

    <section class="scene-shell">
      <article class="story-panel">
        <p class="chapter-kicker" id="chapterKicker">风入长安</p>
        <h1 class="scene-title" id="sceneTitle">盐铁会议历史复原</h1>
        <p class="scene-copy" id="sceneCopy">一场财政会议，正在变成价值和权力的审判。</p>
        <blockquote class="quote-line" id="sceneQuote">边塞军费、山海盐铁、转运网络，都在向长安汇聚。</blockquote>
        <div class="scene-actions">
          <button id="advanceScene" class="primary" type="button">继续进入</button>
          <button id="revealEvidence" class="ghost" type="button">史料浮现</button>
          <button id="rewindScene" class="ghost" type="button">回看</button>
        </div>
      </article>

      <section class="scene-world" aria-label="盐铁会议沉浸式场景">
        <div id="debateHud" class="debate-hud" aria-live="polite"></div>
        <div id="mapScene" class="map-layer is-active" data-scene-layer="map">
          <svg id="hanMapScene" viewBox="0 0 1000 680" role="img" aria-label="动态汉代版图"></svg>
        </div>
        <div id="courtScene" class="court-layer" data-scene-layer="court">
          <svg id="courtSvg" viewBox="0 0 1000 680" role="img" aria-label="朝堂席位与辩论"></svg>
        </div>
        <div id="networkScene" class="network-layer" data-scene-layer="network">
          <svg id="powerNetworkScene" viewBox="0 0 1000 680" role="img" aria-label="权力关系网"></svg>
        </div>
        <div id="judgmentScene" class="judgment-layer" data-scene-layer="judgment">
          <svg id="judgmentSvg" viewBox="0 0 1000 680" role="img" aria-label="退朝案牍收束场景"></svg>
          <form class="judgment-form" id="judgmentForm">
            <textarea id="reflectionInput" placeholder="写下你的退朝案牍：当边费、与民争利和权力阴影同时成立时，制度应废止、修正，还是保留并审计？"></textarea>
            <button class="primary" type="submit">钤下案牍</button>
            <div id="judgmentOutput" class="judgment-output">你的退朝案牍不会写入历史证据包。</div>
          </form>
        </div>
        <aside id="evidenceRibbon" class="evidence-ribbon" aria-label="关键证据"></aside>
      </section>
    </section>

    <div class="timeline-rail" id="timelineRail" aria-hidden="true"></div>
    <p class="scene-footnote" id="historyBoundary">历史事实来自精选 evidence_pack.json；声音与动画只负责临场感，不生成史实。</p>
  </main>

  <script>
    const apiBase = "/api/yantie";
    const state = {
      manifest: null,
      actors: [],
      events: [],
      claims: [],
      relations: [],
      mapLayers: [],
      evidenceById: new Map(),
      sceneIndex: 0,
      userChoices: {},
      audio: null,
      soundEnabled: false,
      animationTick: 0
    };

    const historicalPrelude = [
      {
            "key": "map",
            "kicker": "历史入场一 · 武帝余响",
            "title": "财政机器已经转动多年",
            "copy": "盐铁会议不是突然发生的争吵。武帝以来的边防、盐铁、均输和平准，早已把国家财政和民间生计拧在一起。",
            "quote": "盐铁官、均输、平准，皆以给边费、平物价为名进入制度。",
            "speaker": "历史背景",
            "stance": "财政扩张",
            "line": "在始元六年开口之前，边塞、市场和官府已经先把问题推到了长安。",
            "revealedConflict": "制度压力先于辩论出现。",
            "dominantForce": "财政",
            "opposingVoices": [
                  {
                        "side": "国家",
                        "text": "边防、府库和转运先把问题推向朝堂。"
                  },
                  {
                        "side": "民间",
                        "text": "制度运转多年，痛感也已经累积多年。"
                  }
            ],
            "visualMode": "background-map",
            "tensionBefore": {
                  "fiscal": 62,
                  "virtue": 24,
                  "people": 34,
                  "power": 42
            },
            "tensionAfter": {
                  "fiscal": 82,
                  "virtue": 28,
                  "people": 42,
                  "power": 52
            },
            "historicalEvidence": [
                  "ev:src_shiji_pingzhun:juan030:salt_iron_offices:3344bbcc",
                  "ev:src_shiji_pingzhun:juan030:sang_equal_transport:5e6f7081"
            ],
            "philosophyLens": []
      },
      {
            "key": "court",
            "kicker": "历史入场二 · 诏问民疾苦",
            "title": "会议因民间疾苦而开",
            "copy": "朝廷召集贤良文学，不只是听政策建议，也是把各地对盐铁、榷酤、均输的痛感带进朝堂。",
            "quote": "问郡国所举贤良文学民所疾苦。议罢盐铁榷酤。",
            "speaker": "诏令背景",
            "stance": "会议缘起",
            "line": "这场会议从民所疾苦开始，但它很快会撞上财政、价值和权力。",
            "revealedConflict": "民间疾苦获得发言入口，但入口本身仍由朝廷打开。",
            "dominantForce": "民生",
            "opposingVoices": [
                  {
                        "side": "朝廷",
                        "text": "问疾苦，是治理危机的制度化回应。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "能开口，不等于能决定结果。"
                  }
            ],
            "visualMode": "meeting-open",
            "tensionBefore": {
                  "fiscal": 58,
                  "virtue": 48,
                  "people": 62,
                  "power": 56
            },
            "tensionAfter": {
                  "fiscal": 58,
                  "virtue": 68,
                  "people": 80,
                  "power": 60
            },
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_benyi:meeting_opening:a1b2c3d4",
                  "ev:src_hanshu_zhaodi:juan007:meeting_edict:ccddeeff"
            ],
            "philosophyLens": []
      }
];

    const conflictActs = [
      {
            "key": "act-fiscal",
            "layer": "map",
            "kicker": "第一幕 · 财政先声",
            "title": "国家能力先占上风",
            "copy": "边防、府库、盐铁和均输一起压上案前。此刻桑弘羊一方的理由很强：没有财政能力，德治也没有边界。",
            "quote": "边用度不足，故兴盐、铁，设酒榷，置均输。",
            "speaker": "桑弘羊一方",
            "stance": "国家能力",
            "line": "若边费无着、转运不继，国家先失去保护百姓的能力。",
            "revealedConflict": "财政必要性先把道德批判逼到后场。",
            "dominantForce": "财政",
            "opposingVoices": [
                  {
                        "side": "大夫",
                        "text": "盐铁均输不是奢侈，是边防和府库的筋骨。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "当国家以利入市，百姓先承受制度的重量。"
                  }
            ],
            "choicePrompt": "这一刻，你更愿意先承认财政必要性，还是先追问它的边界？",
            "choiceLeft": "财政必要",
            "choiceRight": "追问边界",
            "visualMode": "fiscal-ascendant",
            "tensionBefore": {
                  "fiscal": 58,
                  "virtue": 34,
                  "people": 40,
                  "power": 50
            },
            "tensionAfter": {
                  "fiscal": 96,
                  "virtue": 32,
                  "people": 46,
                  "power": 58
            },
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d",
                  "ev:src_shiji_pingzhun:juan030:frontier_supply:66778899"
            ],
            "philosophyLens": [
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ]
      },
      {
            "key": "act-livelihood",
            "layer": "court",
            "kicker": "第二幕 · 民生反击",
            "title": "与民争利让财政问题变形",
            "copy": "贤良文学没有先争算法，而是把官营制度描述为国家伸进日用之物。财政技术开始变成治理正当性问题。",
            "quote": "今郡国有盐、铁、酒榷，均输，与民争利。",
            "speaker": "贤良文学",
            "stance": "德治民生",
            "line": "若官府亲自逐利，百姓面对的就不只是价格，而是权力进入日常。",
            "revealedConflict": "民生痛感把财政技术推向治理正当性。",
            "dominantForce": "民生",
            "opposingVoices": [
                  {
                        "side": "贤良文学",
                        "text": "官府入市逐利，百姓会把国家能力感受成盘剥。"
                  },
                  {
                        "side": "大夫",
                        "text": "没有制度调度，豪强和商贾也会吞掉民间余利。"
                  }
            ],
            "choicePrompt": "当制度同时可能抑制豪强、也可能扰民时，你先看见哪一面？",
            "choiceLeft": "抑制豪强",
            "choiceRight": "扰民逐利",
            "visualMode": "livelihood-counter",
            "tensionBefore": {
                  "fiscal": 88,
                  "virtue": 38,
                  "people": 44,
                  "power": 56
            },
            "tensionAfter": {
                  "fiscal": 50,
                  "virtue": 88,
                  "people": 90,
                  "power": 58
            },
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_benyi:literati_abolish:0a1b2c3d",
                  "ev:src_yantielun:juan01_benyi:literati_equal_transport_abuse:abcd5678"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_lianghuiwang:liang01:renyi_over_profit:aa110002"
            ]
      },
      {
            "key": "act-yili",
            "layer": "court",
            "kicker": "第三幕 · 义利显形",
            "title": "争论不再只是算账",
            "copy": "双方仍在谈盐铁、均输和边费，但争论已经升高：国家能不能以利为治理逻辑，财政能力有没有义的边界。",
            "quote": "诸侯不言利害，大夫不言得丧。",
            "speaker": "双方交锋",
            "stance": "义利冲突",
            "line": "财政说必要，儒生问边界；真正相撞的，是国家能力能否越过德治。",
            "revealedConflict": "义与利从政策背后显影，成为整场辩论的价值核心。",
            "dominantForce": "义利",
            "opposingVoices": [
                  {
                        "side": "大夫",
                        "text": "利不是私欲，若能给边费、平物价，就是国家能力。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "国家一旦以利为先，义就会退成装饰。"
                  }
            ],
            "choicePrompt": "如果利能支撑公共秩序，它是否仍应被义严格约束？",
            "choiceLeft": "公共之利",
            "choiceRight": "义的边界",
            "visualMode": "yi-li-clash",
            "tensionBefore": {
                  "fiscal": 78,
                  "virtue": 66,
                  "people": 70,
                  "power": 58
            },
            "tensionAfter": {
                  "fiscal": 84,
                  "virtue": 92,
                  "people": 76,
                  "power": 64
            },
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_benyi:virtue_vs_profit:44556677",
                  "ev:src_yantielun:juan01_benyi:military_strategy_reply:55667788"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001",
                  "ev:src_mengzi_lianghuiwang:liang01:renyi_over_profit:aa110002"
            ]
      },
      {
            "key": "act-statecraft",
            "layer": "court",
            "kicker": "第四幕 · 治道复杂化",
            "title": "儒家不是不要制度，国家能力也不是天然正当",
            "copy": "冲突在这里变得更难：荀子与管子式视角提醒我们，富国、裕民、礼义和物资调度并非互相排斥。问题变成制度如何受约束。",
            "quote": "衣食者民之本，稼穑者民之务也。",
            "speaker": "策展旁白",
            "stance": "治道张力",
            "line": "一个世界把农桑当作根本，另一个世界已经离不开商工和转运。真正的问题是制度如何不吞没民生。",
            "revealedConflict": "简单的儒法二分被打破，制度能力与民生礼义必须同时接受审问。",
            "dominantForce": "治道",
            "opposingVoices": [
                  {
                        "side": "制度",
                        "text": "没有调度、仓储和财政，秩序只是愿望。"
                  },
                  {
                        "side": "德义",
                        "text": "没有节用、裕民和约束，制度会自己变成目的。"
                  }
            ],
            "choicePrompt": "你更担心国家能力不足，还是更担心制度能力失去约束？",
            "choiceLeft": "能力不足",
            "choiceRight": "失去约束",
            "visualMode": "statecraft-complexity",
            "tensionBefore": {
                  "fiscal": 74,
                  "virtue": 76,
                  "people": 72,
                  "power": 56
            },
            "tensionAfter": {
                  "fiscal": 82,
                  "virtue": 84,
                  "people": 82,
                  "power": 62
            },
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_jingeng:agriculture_base:88990011",
                  "ev:src_yantielun:juan01_benyi:commerce_utility:66778899",
                  "ev:src_yantielun:juan01_benyi:great_officer_equal_transport:77889900"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003",
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ]
      },
      {
            "key": "act-power",
            "layer": "network",
            "kicker": "第五幕 · 权力遮蔽",
            "title": "公共辩论有它的政治边界",
            "copy": "当用户以为自己在看一场公共辩论时，霍光辅政、桑弘羊的政治位置和后续清算浮现出来：思想冲突不是在真空中发生。",
            "quote": "桑弘羊建造酒榷盐铁，为国兴利，伐其功。",
            "speaker": "权力阴影",
            "stance": "权力边界",
            "line": "辩论仍在继续，但谁能决定辩论的边界，已经站在席位之外。",
            "revealedConflict": "权力压过思想，让会议结果显得有限而残酷。",
            "dominantForce": "权力",
            "opposingVoices": [
                  {
                        "side": "记录",
                        "text": "道德批判进入文本，成为后世可听见的声音。"
                  },
                  {
                        "side": "权力",
                        "text": "榷酤可罢，盐铁未废；政治格局决定可改变的边界。"
                  }
            ],
            "choicePrompt": "当思想被权力记录也被权力限制时，你更看重发声本身，还是制度结果？",
            "choiceLeft": "发声本身",
            "choiceRight": "制度结果",
            "visualMode": "power-shadow",
            "tensionBefore": {
                  "fiscal": 76,
                  "virtue": 78,
                  "people": 70,
                  "power": 62
            },
            "tensionAfter": {
                  "fiscal": 70,
                  "virtue": 54,
                  "people": 52,
                  "power": 98
            },
            "historicalEvidence": [
                  "ev:src_hanshu_zhaodi:juan007:huo_in_power:33445566",
                  "ev:src_hanshu_huoguang:juan068:sang_resentment:778899aa",
                  "ev:src_hanshu_zhaodi:juan007:rebellion_record:ddee0011"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ]
      }
];

    const issueMatrix = [
      {
            "issue": "盐铁",
            "acts": [
                  "act-fiscal",
                  "act-livelihood",
                  "act-yili"
            ],
            "chapters": "本议、禁耕、复古等",
            "summary": "国家垄断资源如何同时体现财政能力和逐利风险。"
      },
      {
            "issue": "酒榷",
            "acts": [
                  "act-livelihood",
                  "act-power"
            ],
            "chapters": "本议、散不足、后世评价",
            "summary": "有限让步如何暴露会议结果的边界。"
      },
      {
            "issue": "均输",
            "acts": [
                  "act-fiscal",
                  "act-livelihood",
                  "act-statecraft"
            ],
            "chapters": "本议、力耕、通有无等",
            "summary": "转运调度在便利与扰民之间摇摆。"
      },
      {
            "issue": "平准",
            "acts": [
                  "act-fiscal",
                  "act-statecraft"
            ],
            "chapters": "平准书背景、盐铁论相关辩题",
            "summary": "国家入市平物价，也打开官府经商争议。"
      },
      {
            "issue": "边防",
            "acts": [
                  "act-fiscal",
                  "act-yili"
            ],
            "chapters": "本议、击之、和亲等",
            "summary": "边费压力是财政官营最强的现实理由。"
      },
      {
            "issue": "农桑",
            "acts": [
                  "act-livelihood",
                  "act-statecraft"
            ],
            "chapters": "禁耕、水旱、未通等",
            "summary": "务本并非怀旧，而是把衣食生产视为政治根基。"
      },
      {
            "issue": "商工",
            "acts": [
                  "act-fiscal",
                  "act-statecraft"
            ],
            "chapters": "通有无、错币、轻重等",
            "summary": "流通、工商业和国家调度构成制度能力的一面。"
      },
      {
            "issue": "奢俭",
            "acts": [
                  "act-yili",
                  "act-statecraft"
            ],
            "chapters": "散不足、崇礼、贫富等",
            "summary": "消费秩序连接民风、财富分配和政治伦理。"
      },
      {
            "issue": "吏治",
            "acts": [
                  "act-livelihood",
                  "act-power"
            ],
            "chapters": "刺权、论诽、执务等",
            "summary": "制度是否扰民，最终落到官吏执行与权力约束。"
      },
      {
            "issue": "教化",
            "acts": [
                  "act-yili",
                  "act-statecraft"
            ],
            "chapters": "相刺、殊路、论儒等",
            "summary": "德义不是装饰，而是治理目标与边界。"
      },
      {
            "issue": "义利",
            "acts": [
                  "act-yili"
            ],
            "chapters": "本议、非鞅、论儒等",
            "summary": "全书反复追问利能否成为国家治理的首要语言。"
      },
      {
            "issue": "权力",
            "acts": [
                  "act-power"
            ],
            "chapters": "刺权、杂论、汉书霍光传背景",
            "summary": "会议被记录，也被辅政格局和后续政治危机限制。"
      },
      {
            "issue": "后世评价",
            "acts": [
                  "act-power"
            ],
            "chapters": "四库提要、历代接受",
            "summary": "文本保留辩论，也带有著述立场与后人解释。"
      }
];

    const judgmentScene = {
      "key": "judgment",
      "layer": "judgment",
      "kicker": "退朝余波 · 有限结果",
      "title": "榷酤可罢，盐铁未废",
      "copy": "退朝之后，史书留下有限的结果：道德批判进入记录，财政机器仍然运转。此刻才轮到你的案牍。",
      "quote": "后罢榷酤，而盐、铁则如旧。",
      "speaker": "退朝旁白",
      "stance": "历史结果",
      "line": "五幕显影不会替你给出答案，它只把财政、民生、义利、治道和权力同时摆到案前。",
      "revealedConflict": "思想被记录，制度只部分改变。",
      "dominantForce": "退朝",
      "opposingVoices": [
            {
                  "side": "历史",
                  "text": "榷酤可罢，盐铁未废。"
            },
            {
                  "side": "你",
                  "text": "判断必须区分事实、解释和个人反思。"
            }
      ],
      "visualMode": "archive-closure",
      "tensionBefore": {
            "fiscal": 70,
            "virtue": 54,
            "people": 52,
            "power": 98
      },
      "tensionAfter": {
            "fiscal": 76,
            "virtue": 70,
            "people": 60,
            "power": 84
      },
      "historicalEvidence": [
            "ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa",
            "ev:src_yantielun_siku:preface:partial_result:1234abcd"
      ],
      "philosophyLens": []
};

    const scenes = [...historicalPrelude, ...conflictActs, judgmentScene].map(scene => ({
      ...scene,
      key: scene.layer || scene.key,
      actKey: scene.key,
      evidence: [...(scene.historicalEvidence || []), ...(scene.philosophyLens || [])]
    }));

    async function boot() {
      const [manifest, actors, events, claims, relations, mapLayers] = await Promise.all([
        getData("/manifest"),
        getData("/actors?include=evidence_summary"),
        getData("/events"),
        getData("/claims"),
        getData("/relations"),
        getData("/map-layers")
      ]);
      state.manifest = manifest;
      state.actors = actors.items;
      state.events = events.items;
      state.claims = claims.items;
      state.relations = relations.items;
      state.mapLayers = mapLayers.items;
      document.getElementById("packStatus").textContent = `${manifest.evidence_count} 条证据 · 无运行时模型`;
      renderRail();
      renderStaticScenes();
      await renderScene();
      startCanvas();
    }

    async function getData(path, options = {}) {
      const response = await fetch(apiBase + path, options);
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ? body.error.message : "接口不可用");
      return body.data;
    }

    async function getEvidence(evidenceId) {
      if (!state.evidenceById.has(evidenceId)) {
        state.evidenceById.set(evidenceId, await getData(`/evidence/${encodeURIComponent(evidenceId)}`));
      }
      return state.evidenceById.get(evidenceId);
    }

    function renderRail() {
      document.getElementById("timelineRail").style.gridTemplateColumns = `repeat(${scenes.length}, minmax(0, 1fr))`;
      document.getElementById("timelineRail").innerHTML = scenes.map((scene, index) =>
        `<div class="rail-step" data-step="${index}"><span></span></div>`
      ).join("");
    }

    function updateRail() {
      document.querySelectorAll(".rail-step").forEach((node, index) => {
        node.classList.toggle("is-past", index < state.sceneIndex);
        node.classList.toggle("is-current", index === state.sceneIndex);
      });
    }

    function renderStaticScenes() {
      renderRoundVisual(scenes[0]);
    }

    function renderRoundVisual(scene) {
      renderMap(scene);
      renderCourt(scene);
      renderNetwork(scene);
      renderJudgmentBackdrop(scene);
    }

    function renderDebateHud(scene) {
      const axes = [
        ["fiscal", "财政国家"],
        ["virtue", "儒家德治"],
        ["people", "民生痛感"],
        ["power", "权力压迫"]
      ];
      if (scene.choicePrompt && state.userChoices[scene.actKey] == null) {
        state.userChoices[scene.actKey] = 50;
      }
      const issues = issueMatrix.filter(issue => issue.acts.includes(scene.actKey)).slice(0, 5);
      const tensionBefore = scene.tensionBefore || scene.tension || {};
      const tensionAfter = scene.tensionAfter || scene.tension || {};
      const voices = scene.opposingVoices || [];
      const evidenceButtons = [
        ...(scene.historicalEvidence || []).map((id, index) => ({ id, label: `史证 ${index + 1}` })),
        ...(scene.philosophyLens || []).map((id, index) => ({ id, label: `透镜 ${index + 1}` }))
      ];
      document.getElementById("debateHud").innerHTML = `
        <div class="debate-card" data-visual-mode="${escapeHtml(scene.visualMode)}">
          <div class="debate-meta">
            <span class="debate-speaker">${escapeHtml(scene.speaker)}</span>
            <span class="stance-chip">${escapeHtml(scene.stance)}</span>
            <span>${escapeHtml(scene.kicker)}</span>
          </div>
          <p class="debate-line">${escapeHtml(scene.line)}</p>
          <p class="conflict-question">${escapeHtml(scene.revealedConflict || "")}</p>
          ${voices.length ? `
            <div class="voice-pair" aria-label="本幕两股声音">
              ${voices.map(voice => `
                <div class="voice-chip">
                  <strong>${escapeHtml(voice.side)}</strong>
                  <span>${escapeHtml(voice.text)}</span>
                </div>
              `).join("")}
            </div>
          ` : ""}
          <div class="tension-grid" aria-label="本幕思想张力变化">
            ${axes.map(([axis, label]) => `
              <div class="tension-axis">
                <span>${label}</span>
                <div class="tension-track">
                  <span class="tension-fill is-before" style="width: ${Number(tensionBefore[axis] || 0)}%"></span>
                  <span class="tension-fill is-after" style="width: ${Number(tensionAfter[axis] || 0)}%"></span>
                </div>
              </div>
            `).join("")}
          </div>
          ${scene.choicePrompt ? `
            <div class="choice-panel">
              <label for="choice-${escapeHtml(scene.actKey)}">${escapeHtml(scene.choicePrompt)}</label>
              <div class="choice-row">
                <span>${escapeHtml(scene.choiceLeft || "此端")}</span>
                <input class="choice-range" id="choice-${escapeHtml(scene.actKey)}" type="range" min="0" max="100" value="${Number(state.userChoices[scene.actKey] || 50)}" data-act-key="${escapeHtml(scene.actKey)}" />
                <span>${escapeHtml(scene.choiceRight || "彼端")}</span>
              </div>
            </div>
          ` : ""}
          ${issues.length ? `
            <div class="issue-strip" aria-label="全文争点矩阵旁路">
              ${issues.map(issue => `<span class="issue-pill" title="${escapeHtml(issue.summary)}">${escapeHtml(issue.issue)}</span>`).join("")}
            </div>
          ` : ""}
          <div class="evidence-seals" aria-label="本幕证据印记">
            ${evidenceButtons.map(item => `
              <button class="evidence-seal" type="button" data-evidence-id="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>
            `).join("")}
          </div>
        </div>
      `;
    }

    function renderMap(scene) {
      const svg = document.getElementById("hanMapScene");
      const features = state.mapLayers.flatMap(layer => layer.features.map(feature => ({ layer, feature })));
      const pressureOpacity = scene.visualMode === "fiscal-ascendant" ? 0.96 : scene.visualMode === "background-map" ? 0.72 : 0.42;
      svg.innerHTML = `
        <defs>
          <linearGradient id="mapLand" x1="0" x2="1">
            <stop offset="0" stop-color="#d2af70"/>
            <stop offset="0.55" stop-color="#efcf8e"/>
            <stop offset="1" stop-color="#b88c53"/>
          </linearGradient>
          <filter id="softGlow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <rect width="1000" height="680" fill="rgba(9,13,19,0.32)"/>
        <path d="M103 420 C122 239 269 120 470 151 C633 78 844 182 878 365 C825 559 624 607 399 592 C218 607 86 532 103 420 Z"
          fill="url(#mapLand)" opacity="0.88" stroke="#6e522d" stroke-width="8"/>
        <path d="M168 426 C306 352 467 373 604 270 C711 191 813 246 874 362"
          fill="none" stroke="#9b6422" stroke-width="8" stroke-dasharray="18 18" opacity="0.88"/>
        <path d="M423 148 C474 229 586 279 626 375 C669 477 703 552 801 611"
          fill="none" stroke="#2c7a66" stroke-width="7" opacity="0.76"/>
        <g opacity="${pressureOpacity}">
          <path d="M744 198 C650 252 590 296 500 356 C421 409 312 421 190 451" fill="none" stroke="#9a241c" stroke-width="12" stroke-linecap="round" stroke-dasharray="20 16"/>
          <circle cx="742" cy="195" r="34" fill="rgba(154,36,28,0.58)" stroke="#fff4d6" stroke-width="3"/>
          <text x="742" y="204" text-anchor="middle" fill="#fff4d6" font-size="24">边费</text>
          <circle cx="500" cy="356" r="30" fill="rgba(54,81,108,0.62)" stroke="#fff4d6" stroke-width="3"/>
          <text x="500" y="365" text-anchor="middle" fill="#fff4d6" font-size="22">均输</text>
          <circle cx="190" cy="451" r="30" fill="rgba(44,122,102,0.62)" stroke="#fff4d6" stroke-width="3"/>
          <text x="190" y="460" text-anchor="middle" fill="#fff4d6" font-size="22">盐铁</text>
        </g>
        <path d="M604 116 C645 151 700 156 742 195" fill="none" stroke="#f5e4ba" stroke-width="3" opacity="0.6"/>
        <path d="M195 225 C237 201 302 187 359 193" fill="none" stroke="#f5e4ba" stroke-width="3" opacity="0.52"/>
        ${features.map(({ layer, feature }) => {
          const [x, y] = feature.coordinates.length === 2 ? feature.coordinates : [50, 50];
          const px = x * 10;
          const py = y * 9.2;
          const color = layer.layer_type === "capital" ? "#9a241c" : layer.layer_type === "military_frontier" ? "#2f4f88" : "#2c7a66";
          const labelY = py > 560 ? py - 42 : py - 16;
          return `<g filter="url(#softGlow)" data-feature="${escapeHtml(feature.feature_id)}">
            <circle cx="${px}" cy="${py}" r="18" fill="${color}" stroke="#fff4d6" stroke-width="6"/>
            <text x="${Math.min(px + 28, 820)}" y="${labelY}" fill="#fff4d6" font-size="30">${escapeHtml(feature.title)}</text>
          </g>`;
        }).join("")}
      `;
    }

    function renderCourt(scene) {
      const svg = document.getElementById("courtSvg");
      const seats = [
        ["actor_zhao_di", 500, 102, "#c49245"],
        ["actor_huo_guang", 500, 206, "#9a241c"],
        ["actor_sang_hongyang", 255, 382, "#36516c"],
        ["actor_literati", 745, 382, "#2c7a66"],
        ["actor_che_qianqiu", 500, 484, "#64748b"],
        ["actor_shangguan_jie", 280, 542, "#64748b"],
        ["actor_yan_wang_dan", 720, 542, "#64748b"]
      ];
      const activeActors = activeCourtActors(scene);
      const openingLayer = scene.visualMode === "meeting-open" ? `
        <path d="M500 102 C448 196 400 292 255 382" fill="none" stroke="#f3c46d" stroke-width="8" stroke-linecap="round" opacity="0.48"/>
        <path d="M500 102 C554 196 600 292 745 382" fill="none" stroke="#f3c46d" stroke-width="8" stroke-linecap="round" opacity="0.48"/>
        <text x="500" y="284" text-anchor="middle" fill="#ffe7b0" font-size="34">诏问民疾苦</text>
      ` : "";
      const oppositionLayer = scene.visualMode === "livelihood-counter" ? `
        <path d="M745 382 C654 304 521 276 363 332" fill="none" stroke="#2c7a66" stroke-width="12" stroke-linecap="round" opacity="0.62"/>
        <text x="744" y="284" text-anchor="middle" fill="#dcf7df" font-size="34">民生</text>
        <text x="255" y="284" text-anchor="middle" fill="rgba(255,244,214,0.48)" font-size="28">边计</text>
      ` : "";
      const clashLayer = scene.visualMode === "yi-li-clash" || scene.visualMode === "statecraft-complexity" ? `
        <path d="M260 372 C392 274 608 274 740 372" fill="none" stroke="#36516c" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
        <path d="M740 392 C607 490 393 490 260 392" fill="none" stroke="#2c7a66" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
        <text x="360" y="330" text-anchor="middle" fill="#cfe5ff" font-size="42">${scene.visualMode === "statecraft-complexity" ? "制" : "利"}</text>
        <text x="640" y="444" text-anchor="middle" fill="#dcf7df" font-size="42">${scene.visualMode === "statecraft-complexity" ? "民" : "义"}</text>
      ` : "";
      svg.innerHTML = `
        <rect width="1000" height="680" fill="rgba(9,13,19,0.18)"/>
        <path d="M116 588 C205 301 337 164 500 158 C663 164 795 301 884 588" fill="none" stroke="rgba(255,236,188,0.22)" stroke-width="4"/>
        <path d="M140 608 L860 608" stroke="rgba(255,236,188,0.22)" stroke-width="4"/>
        <path d="M500 125 L500 608" stroke="rgba(255,236,188,0.16)" stroke-width="3"/>
        <path d="M292 382 C400 300 600 300 708 382" fill="none" stroke="#f3c46d" stroke-width="5" stroke-dasharray="14 16"/>
        ${openingLayer}
        ${oppositionLayer}
        ${clashLayer}
        ${seats.map(([actorId, x, y, color]) => {
          const actor = state.actors.find(item => item.actor_id === actorId);
          const isActive = activeActors.includes(actorId);
          const opacity = activeActors.length === 0 || isActive ? 0.94 : 0.34;
          const stroke = isActive ? "#f3c46d" : "#fff4d6";
          const strokeWidth = isActive ? 8 : 3;
          return `<g data-actor="${actorId}">
            <circle cx="${x}" cy="${y}" r="50" fill="${color}" opacity="${opacity}" stroke="${stroke}" stroke-width="${strokeWidth}"/>
            <text x="${x}" y="${y + 8}" text-anchor="middle" fill="#fff4d6" font-size="24">${escapeHtml(actor ? actor.name : actorId)}</text>
          </g>`;
        }).join("")}
        <text x="500" y="650" text-anchor="middle" fill="rgba(255,244,214,0.66)" font-size="22">朝堂不是中立空间，席位本身就是压力。</text>
      `;
    }

    function activeCourtActors(scene) {
      if (scene.visualMode === "meeting-open") return ["actor_zhao_di", "actor_huo_guang", "actor_literati", "actor_sang_hongyang", "actor_che_qianqiu"];
      if (scene.visualMode === "fiscal-ascendant") return ["actor_sang_hongyang"];
      if (scene.visualMode === "livelihood-counter") return ["actor_literati"];
      if (scene.visualMode === "yi-li-clash" || scene.visualMode === "statecraft-complexity") return ["actor_sang_hongyang", "actor_literati"];
      return [];
    }

    function renderNetwork(scene) {
      const svg = document.getElementById("powerNetworkScene");
      const nodes = {
        actor_huo_guang: { x: 500, y: 156, label: "霍光", color: "#9a241c" },
        actor_sang_hongyang: { x: 278, y: 328, label: "桑弘羊", color: "#36516c" },
        actor_literati: { x: 720, y: 328, label: "贤良文学", color: "#2c7a66" },
        actor_shangguan_jie: { x: 260, y: 514, label: "上官桀", color: "#64748b" },
        actor_yan_wang_dan: { x: 514, y: 560, label: "燕王旦", color: "#64748b" },
        actor_zhao_di: { x: 734, y: 154, label: "昭帝", color: "#c49245" }
      };
      const lines = state.relations.filter(relation => nodes[relation.from_id] && nodes[relation.to_id]);
      const powerOpacity = scene.visualMode === "power-shadow" ? 0.86 : 0.42;
      svg.innerHTML = `
        <rect width="1000" height="680" fill="rgba(9,13,19,0.24)"/>
        ${lines.map(relation => {
          const from = nodes[relation.from_id];
          const to = nodes[relation.to_id];
          const width = relation.strength === "explicit_source" ? 5 : 3;
          const dash = relation.strength === "explicit_source" ? "" : "stroke-dasharray='13 12'";
          return `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="rgba(243,196,109,0.62)" stroke-width="${width}" ${dash}/>`;
        }).join("")}
        ${Object.entries(nodes).map(([id, node]) => `
          <g data-node="${id}">
            <circle cx="${node.x}" cy="${node.y}" r="58" fill="${node.color}" stroke="#fff4d6" stroke-width="3"/>
            <text x="${node.x}" y="${node.y + 8}" text-anchor="middle" fill="#fff4d6" font-size="26">${escapeHtml(node.label)}</text>
          </g>
        `).join("")}
        <path d="M500 214 C432 302 408 428 278 328 C442 402 584 402 720 328 C596 426 572 302 500 214 Z"
          fill="rgba(154,36,28,${powerOpacity})" opacity="${scene.visualMode === "power-shadow" ? 0.42 : 0.12}"/>
        <text x="500" y="258" text-anchor="middle" fill="#fff4d6" font-size="34" opacity="${scene.visualMode === "power-shadow" ? 0.94 : 0.42}">权力决定辩论边界</text>
        <text x="500" y="630" text-anchor="middle" fill="rgba(255,244,214,0.68)" font-size="22">实线是史料明示，虚线是策展推断。争论之后，是清算。</text>
      `;
    }

    function renderJudgmentBackdrop(scene) {
      document.getElementById("judgmentSvg").innerHTML = `
        <rect width="1000" height="680" fill="rgba(9,13,19,0.24)"/>
        <path d="M205 150 C344 88 662 88 795 150 C842 310 812 470 708 538 C587 612 412 612 292 538 C188 470 158 310 205 150 Z"
          fill="rgba(255,244,214,0.12)" stroke="rgba(255,236,188,0.42)" stroke-width="4"/>
        <path d="M322 220 L678 220 L704 492 L296 492 Z" fill="rgba(239,227,196,0.16)" stroke="rgba(255,236,188,0.5)" stroke-width="3"/>
        <text x="500" y="162" text-anchor="middle" fill="#fff4d6" font-size="50">退朝案牍</text>
        <text x="500" y="218" text-anchor="middle" fill="rgba(255,244,214,0.72)" font-size="24">个人反思不会成为历史事实。</text>
      `;
    }

    async function renderScene() {
      const scene = scenes[state.sceneIndex];
      renderRoundVisual(scene);
      renderDebateHud(scene);
      document.getElementById("chapterKicker").textContent = scene.kicker;
      document.getElementById("sceneTitle").textContent = scene.title;
      document.getElementById("sceneCopy").textContent = scene.copy;
      document.getElementById("sceneQuote").textContent = scene.quote;
      document.getElementById("advanceScene").textContent = state.sceneIndex === scenes.length - 1 ? "停在案前" : "继续进入";
      document.getElementById("rewindScene").style.visibility = state.sceneIndex === 0 ? "hidden" : "visible";
      document.querySelectorAll("[data-scene-layer]").forEach(layer => layer.classList.remove("is-active"));
      const layerId = scene.key === "map" ? "mapScene" : scene.key === "court" ? "courtScene" : scene.key === "network" ? "networkScene" : "judgmentScene";
      document.getElementById(layerId).classList.add("is-active");
      document.getElementById("evidenceRibbon").classList.remove("is-open");
      updateRail();
      await preloadSceneEvidence(scene);
      pulseSound(scene.visualMode || scene.key);
    }

    async function preloadSceneEvidence(scene) {
      await Promise.all(scene.evidence.map(getEvidence));
    }

    async function openEvidence(focusEvidenceId = null) {
      const scene = scenes[state.sceneIndex];
      const evidenceIds = focusEvidenceId ? [focusEvidenceId] : scene.evidence;
      const evidenceItems = await Promise.all(evidenceIds.map(getEvidence));
      const ribbon = document.getElementById("evidenceRibbon");
      ribbon.innerHTML = evidenceItems.map(evidence => `
        <div class="evidence-item">
          <strong>${escapeHtml(evidence.excerpt_original || evidence.paraphrase_zh)}</strong>
          <span>${escapeHtml(evidence.paraphrase_zh)}</span>
          <span>${escapeHtml(evidence.source_id)} · ${escapeHtml(evidence.canonical_location)}</span>
        </div>
      `).join("");
      ribbon.classList.toggle("is-open");
      pulseSound("evidence");
    }

    document.getElementById("advanceScene").addEventListener("click", async () => {
      if (state.sceneIndex < scenes.length - 1) {
        state.sceneIndex += 1;
        await renderScene();
      }
    });

    document.getElementById("rewindScene").addEventListener("click", async () => {
      if (state.sceneIndex > 0) {
        state.sceneIndex -= 1;
        await renderScene();
      }
    });

    document.getElementById("revealEvidence").addEventListener("click", () => openEvidence());

    document.getElementById("debateHud").addEventListener("click", event => {
      const target = event.target.closest("[data-evidence-id]");
      if (!target) return;
      openEvidence(target.dataset.evidenceId);
    });

    document.getElementById("debateHud").addEventListener("input", event => {
      const target = event.target.closest("[data-act-key]");
      if (!target) return;
      state.userChoices[target.dataset.actKey] = Number(target.value);
    });

    document.getElementById("soundToggle").addEventListener("click", async () => {
      await ensureAudio();
      state.soundEnabled = !state.soundEnabled;
      document.getElementById("soundToggle").setAttribute("aria-pressed", String(state.soundEnabled));
      if (state.soundEnabled) pulseSound("open");
    });

    function buildChoiceSummary() {
      return conflictActs.map(act => {
        const value = Number(state.userChoices[act.key] ?? 50);
        const leaning = value < 40 ? act.choiceLeft : value > 60 ? act.choiceRight : "保留张力";
        return `${act.kicker}：${leaning}（${value}/100）`;
      }).join("\\n");
    }

    document.getElementById("judgmentForm").addEventListener("submit", async event => {
      event.preventDefault();
      const sceneEvidence = scenes.flatMap(scene => scene.evidence).filter((id, index, ids) => ids.indexOf(id) === index);
      const reflectionText = document.getElementById("reflectionInput").value || "";
      const choiceSummary = `五幕显影选择：\\n${buildChoiceSummary()}`;
      const response = await fetch(apiBase + "/judgment-cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_claim_ids: ["claim_conflict_is_moral_and_fiscal", "claim_power_network_not_optional"],
          selected_evidence_ids: sceneEvidence,
          personal_reflection: [choiceSummary, reflectionText].filter(Boolean).join("\\n\\n") || null,
          disposition: "modern_analogy_with_caution"
        })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ? body.error.message : "判断卡生成失败");
      const data = body.data;
      document.getElementById("judgmentOutput").textContent =
        `退朝案牍 ${data.judgment_card_id}\\n` +
        `原文事实 ${data.sections.original_facts.length} 条 · 策展推断 ${data.sections.curatorial_inferences.length} 条\\n` +
        `${data.history_boundary}\\n${data.caution || ""}`;
      pulseSound("judgment");
    });

    async function ensureAudio() {
      if (state.audio) return;
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const context = new AudioContext();
      const master = context.createGain();
      master.gain.value = 0.045;
      master.connect(context.destination);
      state.audio = { context, master };
    }

    function pulseSound(kind) {
      if (!state.soundEnabled || !state.audio) return;
      const { context, master } = state.audio;
      const now = context.currentTime;
      const osc = context.createOscillator();
      const gain = context.createGain();
      const freqs = {
        "background-map": 88,
        "meeting-open": 118,
        "fiscal-ascendant": 92,
        "livelihood-counter": 146,
        "yi-li-clash": 188,
        "statecraft-complexity": 164,
        "power-shadow": 68,
        "archive-closure": 176,
        map: 96,
        court: 128,
        network: 72,
        judgment: 180,
        evidence: 232,
        open: 156
      };
      osc.frequency.value = freqs[kind] || 110;
      osc.type = kind === "power-shadow" || kind === "network" ? "sawtooth" : "sine";
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(kind === "evidence" ? 0.09 : 0.055, now + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.72);
      osc.connect(gain);
      gain.connect(master);
      osc.start(now);
      osc.stop(now + 0.78);
    }

    function startCanvas() {
      const canvas = document.getElementById("sceneCanvas");
      const context = canvas.getContext("2d");
      const resize = () => {
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(window.innerWidth * ratio);
        canvas.height = Math.floor(window.innerHeight * ratio);
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
      };
      window.addEventListener("resize", resize);
      resize();

      const draw = () => {
        const width = window.innerWidth;
        const height = window.innerHeight;
        state.animationTick += 0.008;
        const gradient = context.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, "#101820");
        gradient.addColorStop(0.52, state.sceneIndex >= 3 ? "#180d10" : "#172438");
        gradient.addColorStop(1, "#070a0f");
        context.fillStyle = gradient;
        context.fillRect(0, 0, width, height);

        context.save();
        context.globalAlpha = 0.24;
        context.strokeStyle = "#f3c46d";
        context.lineWidth = 1;
        for (let i = 0; i < 28; i += 1) {
          const y = ((i * 44) + (state.animationTick * 38)) % (height + 120) - 80;
          context.beginPath();
          context.moveTo(-60, y);
          context.bezierCurveTo(width * 0.24, y - 40, width * 0.72, y + 50, width + 60, y - 10);
          context.stroke();
        }
        context.restore();

        context.save();
        context.globalAlpha = 0.18 + Math.sin(state.animationTick * 4) * 0.04;
        context.fillStyle = state.sceneIndex >= 3 ? "#9a241c" : "#c49245";
        context.beginPath();
        context.arc(width * 0.74, height * 0.22, Math.min(width, height) * 0.18, 0, Math.PI * 2);
        context.fill();
        context.restore();

        requestAnimationFrame(draw);
      };
      draw();
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    boot().catch(error => {
      document.getElementById("packStatus").textContent = "史料读取失败";
      document.getElementById("sceneCopy").textContent = error.message;
    });
  </script>
</body>
</html>
"""
