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
      min-height: 66px;
      margin: 20px 0 0;
      padding: 12px 16px;
      border-left: 4px solid var(--blood);
      background: rgba(9,13,19,0.22);
      color: #ffe7b0;
      line-height: 1.65;
      box-shadow: 0 12px 34px rgba(0,0,0,0.18);
      backdrop-filter: blur(3px);
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
      background: linear-gradient(180deg, rgba(255,244,214,0.04), rgba(9,13,19,0.22));
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
      max-width: min(540px, 62%);
      padding: 12px 14px;
      border: 1px solid rgba(255,236,188,0.22);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(9,13,19,0.58), rgba(9,13,19,0.3));
      box-shadow: 0 16px 42px rgba(0,0,0,0.18);
      backdrop-filter: blur(5px);
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
      font-size: clamp(15px, 1.55vw, 18px);
      line-height: 1.58;
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
      height: 5px;
      border-radius: 999px;
      background: rgba(255,244,214,0.16);
      overflow: hidden;
    }

    .tension-fill {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: #f3c46d;
      transform-origin: left center;
      transition: width 500ms ease;
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
      background: rgba(9,13,19,0.58);
      backdrop-filter: blur(6px);
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
      gap: 2px;
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
      background: rgba(9,13,19,0.48);
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

      .tension-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
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
      audio: null,
      soundEnabled: false,
      animationTick: 0
    };

    const historicalPrelude = [
      {
            "key": "map",
            "kicker": "历史背景一 · 武帝余响",
            "title": "财政机器已经转动多年",
            "copy": "盐铁会议不是突然发生的争吵。武帝以来的边防、盐铁、均输和平准已经把议题推到长安。",
            "quote": "使孔仅、东郭咸阳乘传举行天下盐铁",
            "speaker": "历史背景",
            "stance": "财政扩张",
            "line": "在始元六年开口之前，边塞、市场和官府已经先把问题推到长安。",
            "visualMode": "background-map",
            "tension": {
                  "fiscal": 82,
                  "virtue": 28,
                  "people": 42,
                  "power": 52
            },
            "evidence": [
                  "ev:src_shiji_pingzhun:juan030:salt_iron_offices:3344bbcc",
                  "ev:src_shiji_pingzhun:juan030:sang_equal_transport:5e6f7081"
            ]
      },
      {
            "key": "court",
            "kicker": "历史背景二 · 诏问民疾苦",
            "title": "会议因民间疾苦而开",
            "copy": "朝廷召集贤良文学，不只是听政策建议，也是把各地对盐铁、榷酤、均输的痛感带进朝堂。",
            "quote": "问郡国所举贤良文学民所疾苦",
            "speaker": "诏令背景",
            "stance": "会议缘起",
            "line": "这场会议从民所疾苦开始，但它很快会撞上财政、价值和权力。",
            "visualMode": "meeting-open",
            "tension": {
                  "fiscal": 58,
                  "virtue": 68,
                  "people": 80,
                  "power": 60
            },
            "evidence": [
                  "ev:src_hanshu_zhaodi:juan007:recommend_worthy:f00d1234",
                  "ev:src_hanshu_zhaodi:juan007:meeting_edict:ccddeeff"
            ]
      }
];

    const yantielunChapters = [
      {
            "order": 1,
            "title": "本議第一",
            "speaker": "篇章旁白",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "惟始元六年，有詔書使丞相、御史與所舉賢良、文學語，問民間所疾苦。文學",
            "copy": "《盐铁论》本議第一以“惟始元六年，有詔書使丞相、御史與所舉”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_001:text_order:9fb227ef"
      },
      {
            "order": 2,
            "title": "力耕第二",
            "speaker": "大夫一方",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "大夫曰：「王者塞天財，禁關市，執準守時，以輕重御民。豐年歲登，則儲積",
            "copy": "《盐铁论》力耕第二以“大夫曰：「王者塞天財，禁關市，執準守”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_002:text_order:947d2710"
      },
      {
            "order": 3,
            "title": "通有第三",
            "speaker": "大夫一方",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "大夫曰：「燕之涿、薊，趙之邯鄲，魏之溫軹，韓之滎陽，齊之臨淄，楚之宛",
            "copy": "《盐铁论》通有第三以“大夫曰：「燕之涿、薊，趙之邯鄲，魏之”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_003:text_order:0281a6f8"
      },
      {
            "order": 4,
            "title": "錯幣第四",
            "speaker": "大夫一方",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "大夫曰：「交幣通施，民事不及，物有所幷也。計本量委，民有饑者，穀有所",
            "copy": "《盐铁论》錯幣第四以“大夫曰：「交幣通施，民事不及，物有所”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_004:text_order:a6ec58fc"
      },
      {
            "order": 5,
            "title": "禁耕第五",
            "speaker": "大夫一方",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "大夫曰：「家人有寶器，尚函匣而藏之，況人主之山海乎？夫權利之處，必在",
            "copy": "《盐铁论》禁耕第五以“大夫曰：「家人有寶器，尚函匣而藏之，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_005:text_order:3c4ac77a"
      },
      {
            "order": 6,
            "title": "復古第六",
            "speaker": "大夫一方",
            "stance": "制度缘起",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 82,
                  "virtue": 68,
                  "people": 62,
                  "power": 56
            },
            "quote": "大夫曰：「故扇水都尉彭祖寧歸，言：『鹽、鐵令品，令品甚明。卒徒衣食縣",
            "copy": "《盐铁论》復古第六以“大夫曰：「故扇水都尉彭祖寧歸，言：『”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_006:text_order:23f882b0"
      },
      {
            "order": 7,
            "title": "非鞅第七",
            "speaker": "大夫一方",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "大夫曰：「昔商君相秦也，內立法度，嚴刑罰，飭政教，奸偽無所容。外設百",
            "copy": "《盐铁论》非鞅第七以“大夫曰：「昔商君相秦也，內立法度，嚴”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_007:text_order:4286367e"
      },
      {
            "order": 8,
            "title": "晁錯第八",
            "speaker": "大夫一方",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "大夫曰：「春秋之法，君親無將，將而必誅。故臣罪莫重於弒君，子罪莫重於",
            "copy": "《盐铁论》晁錯第八以“大夫曰：「春秋之法，君親無將，將而必”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_008:text_order:b900772f"
      },
      {
            "order": 9,
            "title": "刺權第九",
            "speaker": "大夫一方",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "大夫曰：「今夫越之具區，楚之雲夢，宋之鉅野，齊之孟諸，有國之富而霸王",
            "copy": "《盐铁论》刺權第九以“大夫曰：「今夫越之具區，楚之雲夢，宋”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_009:text_order:0c197144"
      },
      {
            "order": 10,
            "title": "刺復第十",
            "speaker": "大夫一方",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "大夫曰為色矜而心不懌，曰：「但居者不知負載之勞，從旁議者與當局者異憂",
            "copy": "《盐铁论》刺復第十以“大夫曰為色矜而心不懌，曰：「但居者不”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_010:text_order:fd4ba7ba"
      },
      {
            "order": 11,
            "title": "論儒第十一",
            "speaker": "篇章旁白",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "御史曰：「文學祖述仲尼，稱誦其德，以為自古及今，未之有也。然孔子修道",
            "copy": "《盐铁论》論儒第十一以“御史曰：「文學祖述仲尼，稱誦其德，以”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_011:text_order:3e09582c"
      },
      {
            "order": 12,
            "title": "憂邊第十二",
            "speaker": "大夫一方",
            "stance": "法术与儒议",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 74,
                  "virtue": 78,
                  "people": 58,
                  "power": 66
            },
            "quote": "大夫曰：「文學言：『天下不平，庶國不寧，明王之憂也。』故王者之於天下",
            "copy": "《盐铁论》憂邊第十二以“大夫曰：「文學言：『天下不平，庶國不”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_012:text_order:9320befc"
      },
      {
            "order": 13,
            "title": "園池第十三",
            "speaker": "大夫一方",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "大夫曰：「諸侯以國為家，其憂在內。天子以八極為境，其慮在外。故宇小者",
            "copy": "《盐铁论》園池第十三以“大夫曰：「諸侯以國為家，其憂在內。天”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_013:text_order:a6336fe1"
      },
      {
            "order": 14,
            "title": "輕重第十四",
            "speaker": "篇章旁白",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "御史進曰：「昔太公封於營丘，辟草萊而居焉。地薄人少，於是通利末之道，",
            "copy": "《盐铁论》輕重第十四以“御史進曰：「昔太公封於營丘，辟草萊而”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_014:text_order:81b91673"
      },
      {
            "order": 15,
            "title": "未通第十五",
            "speaker": "篇章旁白",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "御史曰：「內郡人眾，水泉薦草，不能相贍，地勢溫濕，不宜牛馬；民跖耒而",
            "copy": "《盐铁论》未通第十五以“御史曰：「內郡人眾，水泉薦草，不能相”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_015:text_order:78b6f9ac"
      },
      {
            "order": 16,
            "title": "地廣第十六",
            "speaker": "大夫一方",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "大夫曰：「王者包含幷覆，普愛無私，不為近重施，不為遠遺恩。今俱是民也",
            "copy": "《盐铁论》地廣第十六以“大夫曰：「王者包含幷覆，普愛無私，不”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_016:text_order:2169158a"
      },
      {
            "order": 17,
            "title": "貧富第十七",
            "speaker": "大夫一方",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "大夫曰：「余結髮束修年十三，幸得宿衛，給事輦轂之下，以至卿大夫之位，",
            "copy": "《盐铁论》貧富第十七以“大夫曰：「余結髮束修年十三，幸得宿衛”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_017:text_order:56770b03"
      },
      {
            "order": 18,
            "title": "毀學第十八",
            "speaker": "大夫一方",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "大夫曰：「夫懷枉而言正，自托於無欲而實不從，此非士之情也？昔李斯與包",
            "copy": "《盐铁论》毀學第十八以“大夫曰：「夫懷枉而言正，自托於無欲而”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_018:text_order:29ef3931"
      },
      {
            "order": 19,
            "title": "褒賢第十九",
            "speaker": "大夫一方",
            "stance": "山海资源",
            "key": "map",
            "visualMode": "map-pressure",
            "tension": {
                  "fiscal": 84,
                  "virtue": 58,
                  "people": 66,
                  "power": 72
            },
            "quote": "大夫曰：「伯夷以廉饑，尾生以信死。由小器而虧大體，匹夫匹婦之為諒也，",
            "copy": "《盐铁论》褒賢第十九以“大夫曰：「伯夷以廉饑，尾生以信死。由”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_019:text_order:15df98d4"
      },
      {
            "order": 20,
            "title": "相刺第二十",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「古者，經井田，制廛里，丈夫治其田疇，女子治其麻枲，無曠地，",
            "copy": "《盐铁论》相刺第二十以“大夫曰：「古者，經井田，制廛里，丈夫”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_020:text_order:4f46cdc8"
      },
      {
            "order": 21,
            "title": "殊路第二十一",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「七十子躬受聖人之術，有名列於孔子之門，皆諸侯卿相之才，可南",
            "copy": "《盐铁论》殊路第二十一以“大夫曰：「七十子躬受聖人之術，有名列”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_021:text_order:6c6b6279"
      },
      {
            "order": 22,
            "title": "訟賢第二十二",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「剛者折，柔者卷。故季由以強梁死，宰我以柔弱殺。使二子不學，",
            "copy": "《盐铁论》訟賢第二十二以“大夫曰：「剛者折，柔者卷。故季由以強”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_022:text_order:f329e676"
      },
      {
            "order": 23,
            "title": "遵道第二十三",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「御史！」御史未應。謂丞相史曰：「文學結髮學語，服膺不舍，辭",
            "copy": "《盐铁论》遵道第二十三以“大夫曰：「御史！」御史未應。謂丞相史”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_023:text_order:ec58468b"
      },
      {
            "order": 24,
            "title": "論誹第二十四",
            "speaker": "篇章旁白",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "丞相史曰：「晏子有言：『儒者華於言而寡於實，繁於樂而舒於民，久喪以害",
            "copy": "《盐铁论》論誹第二十四以“丞相史曰：「晏子有言：『儒者華於言而”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_024:text_order:7a12414a"
      },
      {
            "order": 25,
            "title": "孝養第二十五",
            "speaker": "贤良文学",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "文學曰：「善養者不必芻豢也，善供服者不必錦繡也。以己之所有盡事其親，",
            "copy": "《盐铁论》孝養第二十五以“文學曰：「善養者不必芻豢也，善供服者”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_025:text_order:31e3350d"
      },
      {
            "order": 26,
            "title": "刺議第二十六",
            "speaker": "篇章旁白",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "丞相史曰：「山陵不讓椒跬，以成其崇；君子不辭負薪之言，以廣其名。故多",
            "copy": "《盐铁论》刺議第二十六以“丞相史曰：「山陵不讓椒跬，以成其崇；”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_026:text_order:6748d3ee"
      },
      {
            "order": 27,
            "title": "利議第二十七",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「作世明主，憂勞萬民，思念北邊之未安，故使使者舉賢良、文學高",
            "copy": "《盐铁论》利議第二十七以“大夫曰：「作世明主，憂勞萬民，思念北”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_027:text_order:ce7cd32e"
      },
      {
            "order": 28,
            "title": "國疾第二十八",
            "speaker": "贤良文学",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "文學曰：「國有賢士而不用，非士之過，有國者之恥。孔子大聖也，諸侯莫能",
            "copy": "《盐铁论》國疾第二十八以“文學曰：「國有賢士而不用，非士之過，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_028:text_order:b3020679"
      },
      {
            "order": 29,
            "title": "散不足第二十九",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「吾以賢良為少愈，乃反其幽明，若胡車相隨而鳴。諸生獨不見季夏",
            "copy": "《盐铁论》散不足第二十九以“大夫曰：「吾以賢良為少愈，乃反其幽明”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_029:text_order:d80874ba"
      },
      {
            "order": 30,
            "title": "救匱第三十",
            "speaker": "贤良文学",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "賢良曰：「蓋橈枉者以直，救文者以質。昔者，晏子相齊，一狐裘三十載。故",
            "copy": "《盐铁论》救匱第三十以“賢良曰：「蓋橈枉者以直，救文者以質。”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_030:text_order:d6027aab"
      },
      {
            "order": 31,
            "title": "箴石第三十一",
            "speaker": "篇章旁白",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "丞相曰：「吾聞諸鄭長者曰：『君子正顏色，則遠暴嫚；出辭氣，則遠鄙倍矣",
            "copy": "《盐铁论》箴石第三十一以“丞相曰：「吾聞諸鄭長者曰：『君子正顏”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_031:text_order:fde83baf"
      },
      {
            "order": 32,
            "title": "除狹第三十二",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「賢者處大林，遭風雷而不迷。愚者雖處平敞大路，猶暗惑焉。今守",
            "copy": "《盐铁论》除狹第三十二以“大夫曰：「賢者處大林，遭風雷而不迷。”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_032:text_order:c1218137"
      },
      {
            "order": 33,
            "title": "疾貪第三十三",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「然。為醫以拙矣，又多求謝。為吏既多不良矣，又侵漁百姓。長吏",
            "copy": "《盐铁论》疾貪第三十三以“大夫曰：「然。為醫以拙矣，又多求謝。”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_033:text_order:b4633e27"
      },
      {
            "order": 34,
            "title": "後刑第三十四",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「古之君子，善善而惡惡。人君不畜惡民，農夫不畜無用之苗。無用",
            "copy": "《盐铁论》後刑第三十四以“大夫曰：「古之君子，善善而惡惡。人君”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_034:text_order:5d567a2a"
      },
      {
            "order": 35,
            "title": "授時第三十五",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "seat-opposition",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「共其地，居是世也，非有災害疾疫，獨以貧窮，非惰則奢也；無奇",
            "copy": "《盐铁论》授時第三十五以“大夫曰：「共其地，居是世也，非有災害”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_035:text_order:0a85f7b7"
      },
      {
            "order": 36,
            "title": "水旱第三十六",
            "speaker": "大夫一方",
            "stance": "贤能与吏治",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 60,
                  "virtue": 86,
                  "people": 76,
                  "power": 62
            },
            "quote": "大夫曰：「禹、湯聖主，后稷、伊尹賢相也，而有水旱之災。水旱，天之所為",
            "copy": "《盐铁论》水旱第三十六以“大夫曰：「禹、湯聖主，后稷、伊尹賢相”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_036:text_order:9c0768fb"
      },
      {
            "order": 37,
            "title": "崇禮第三十七",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「飾几杖，修樽俎，為賓，非為主也。炫耀奇怪，所以陳四夷，非為",
            "copy": "《盐铁论》崇禮第三十七以“大夫曰：「飾几杖，修樽俎，為賓，非為”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_037:text_order:3915bc13"
      },
      {
            "order": 38,
            "title": "備胡第三十八",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「鄙語曰：『賢者容不辱。』以世俗言之，鄉曲有桀，人尚辟之。今",
            "copy": "《盐铁论》備胡第三十八以“大夫曰：「鄙語曰：『賢者容不辱。』以”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_038:text_order:dce6b459"
      },
      {
            "order": 39,
            "title": "執務第三十九",
            "speaker": "篇章旁白",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "丞相曰：「先王之道，軼久而難復，賢良、文學之言，深遠而難行。夫稱上聖",
            "copy": "《盐铁论》執務第三十九以“丞相曰：「先王之道，軼久而難復，賢良”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_039:text_order:149d8fea"
      },
      {
            "order": 40,
            "title": "能言第四十",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「盲者口能言白黑，而無目以別之。儒者口能言治亂，而無能以行之",
            "copy": "《盐铁论》能言第四十以“大夫曰：「盲者口能言白黑，而無目以別”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_040:text_order:ce92ad30"
      },
      {
            "order": 41,
            "title": "取下第四十一",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「不軌之民，困橈公利，而欲擅山澤。從文學、賢良之意，則利歸於",
            "copy": "《盐铁论》取下第四十一以“大夫曰：「不軌之民，困橈公利，而欲擅”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_041:text_order:2a88175a"
      },
      {
            "order": 42,
            "title": "擊之第四十二",
            "speaker": "贤良文学",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "賢良、文學既拜，咸取列大夫，辭丞相、御史。大夫曰：「前議公事，賢良、",
            "copy": "《盐铁论》擊之第四十二以“賢良、文學既拜，咸取列大夫，辭丞相、”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_042:text_order:a715de89"
      },
      {
            "order": 43,
            "title": "結和第四十三",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「漢興以來，修好結和親，所聘遺單于者甚厚；然不紀重質厚賂之故",
            "copy": "《盐铁论》結和第四十三以“大夫曰：「漢興以來，修好結和親，所聘”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_043:text_order:1ba0a5a7"
      },
      {
            "order": 44,
            "title": "誅秦第四十四",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「秦、楚、燕、齊、周之封國也；三晉之君，齊之田氏，諸侯家臣也",
            "copy": "《盐铁论》誅秦第四十四以“大夫曰：「秦、楚、燕、齊、周之封國也”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_044:text_order:8a692fc5"
      },
      {
            "order": 45,
            "title": "伐功第四十五",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「齊桓公越燕伐山戎，破孤竹，殘令支。趙武靈王踰句註，過代谷，",
            "copy": "《盐铁论》伐功第四十五以“大夫曰：「齊桓公越燕伐山戎，破孤竹，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_045:text_order:7c69ce75"
      },
      {
            "order": 46,
            "title": "西域第四十六",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「往者，匈奴據河、山之險，擅田牧之利，民富兵強，行入為寇，則",
            "copy": "《盐铁论》西域第四十六以“大夫曰：「往者，匈奴據河、山之險，擅”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_046:text_order:d68f5be9"
      },
      {
            "order": 47,
            "title": "世務第四十七",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「諸生妄言！議者令可詳用，無徒守椎車之語，滑稽而不可循。夫漢",
            "copy": "《盐铁论》世務第四十七以“大夫曰：「諸生妄言！議者令可詳用，無”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_047:text_order:0d86550d"
      },
      {
            "order": 48,
            "title": "和親第四十八",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「昔徐偃王行義而滅，魯哀公好儒而削。知文而不知武，知一而不知",
            "copy": "《盐铁论》和親第四十八以“大夫曰：「昔徐偃王行義而滅，魯哀公好”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_048:text_order:682a856d"
      },
      {
            "order": 49,
            "title": "繇役第四十九",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「屠者解分中理，可橫以手而離也；至其抽筋鑿骨，非行金斧不能決",
            "copy": "《盐铁论》繇役第四十九以“大夫曰：「屠者解分中理，可橫以手而離”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_049:text_order:5a529a3e"
      },
      {
            "order": 50,
            "title": "險固第五十",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「虎兕所以能執熊羆、服群獸者，爪牙利而攫便也。秦所以超諸侯、",
            "copy": "《盐铁论》險固第五十以“大夫曰：「虎兕所以能執熊羆、服群獸者”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_050:text_order:6fee881f"
      },
      {
            "order": 51,
            "title": "論勇第五十一",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「荊軻懷數年之謀而事不就者，尺八匕首不足恃也。秦王憚於不意，",
            "copy": "《盐铁论》論勇第五十一以“大夫曰：「荊軻懷數年之謀而事不就者，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_051:text_order:ad7e4a9a"
      },
      {
            "order": 52,
            "title": "論功第五十二",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「匈奴無城廓之守，溝池之固，修戟強弩之用，倉廩府庫之積，上無",
            "copy": "《盐铁论》論功第五十二以“大夫曰：「匈奴無城廓之守，溝池之固，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_052:text_order:2824a19e"
      },
      {
            "order": 53,
            "title": "論鄒第五十三",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「鄒子疾晚世之儒墨，不知天地之弘，昭曠之道，將一曲而欲道九折",
            "copy": "《盐铁论》論鄒第五十三以“大夫曰：「鄒子疾晚世之儒墨，不知天地”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_053:text_order:599af8e6"
      },
      {
            "order": 54,
            "title": "論菑第五十四",
            "speaker": "大夫一方",
            "stance": "边政攻守",
            "key": "network",
            "visualMode": "power-shadow",
            "tension": {
                  "fiscal": 78,
                  "virtue": 64,
                  "people": 58,
                  "power": 88
            },
            "quote": "大夫曰：「巫祝不可與並祀，諸生不可與逐語，信往疑今，非人自是。夫道古",
            "copy": "《盐铁论》論菑第五十四以“大夫曰：「巫祝不可與並祀，諸生不可與”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_054:text_order:35120a57"
      },
      {
            "order": 55,
            "title": "刑德第五十五",
            "speaker": "大夫一方",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "大夫曰：「令者所以教民也，法者所以督奸也。令嚴而民慎，法設而奸禁。罔",
            "copy": "《盐铁论》刑德第五十五以“大夫曰：「令者所以教民也，法者所以督”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_055:text_order:b8a94ea4"
      },
      {
            "order": 56,
            "title": "申韓第五十六",
            "speaker": "篇章旁白",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "御史曰：「待周公而為相，則世無列國。待孔子而後學，則世無儒、墨。夫衣",
            "copy": "《盐铁论》申韓第五十六以“御史曰：「待周公而為相，則世無列國。”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_056:text_order:e278f6ba"
      },
      {
            "order": 57,
            "title": "周秦第五十七",
            "speaker": "篇章旁白",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "御史曰：「春秋無名號，謂之雲盜，所以賤刑人而絕之人倫也。故君不臣，士",
            "copy": "《盐铁论》周秦第五十七以“御史曰：「春秋無名號，謂之雲盜，所以”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_057:text_order:4df2202d"
      },
      {
            "order": 58,
            "title": "詔聖第五十八",
            "speaker": "篇章旁白",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "御史曰：「夏後氏不倍言，殷誓，周盟，德信彌衰。無文、武之人，欲修其法",
            "copy": "《盐铁论》詔聖第五十八以“御史曰：「夏後氏不倍言，殷誓，周盟，”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_058:text_order:5d0c9d29"
      },
      {
            "order": 59,
            "title": "大論第五十九",
            "speaker": "大夫一方",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "大夫曰：「呻吟槁簡，誦死人之語，則有司不以文學。文學知獄之在廷後而不",
            "copy": "《盐铁论》大論第五十九以“大夫曰：「呻吟槁簡，誦死人之語，則有”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_059:text_order:09ff8e00"
      },
      {
            "order": 60,
            "title": "雜論第六十",
            "speaker": "篇章旁白",
            "stance": "刑德终局",
            "key": "court",
            "visualMode": "value-clash",
            "tension": {
                  "fiscal": 66,
                  "virtue": 84,
                  "people": 68,
                  "power": 78
            },
            "quote": "客曰：「余睹鹽、鐵之義，觀乎公卿、文學、賢良之論，意指殊路，各有所出",
            "copy": "《盐铁论》雜論第六十以“客曰：「余睹鹽、鐵之義，觀乎公卿、文”开篇，延续公卿与贤良文学围绕政策、价值或边政的论辩。",
            "evidenceId": "ev:src_yantielun:chapter_060:text_order:da9d4d53"
      }
];

    const debateRounds = yantielunChapters.map(chapter => ({
      key: chapter.key,
      kicker: `第${String(chapter.order).padStart(2, "0")}回合 · ${chapter.title}`,
      title: `第${chapter.order}篇：${chapter.title}`,
      copy: chapter.copy,
      quote: chapter.quote,
      speaker: chapter.speaker,
      stance: chapter.stance,
      line: `按《盐铁论》文本顺序进入《${chapter.title}》；此回合只使用本篇证据。`,
      visualMode: chapter.visualMode,
      tension: chapter.tension,
      evidence: [chapter.evidenceId]
    }));

    const judgmentScene = {
      "key": "judgment",
      "kicker": "退朝余波 · 有限结果",
      "title": "榷酤可罢，盐铁未废",
      "copy": "退朝之后，史书留下有限的结果：道德批判进入记录，财政机器仍然运转。此刻才轮到你的案牍。",
      "quote": "后罢榷酤，而盐、铁则如旧",
      "speaker": "退朝旁白",
      "stance": "历史结果",
      "line": "六十篇已过，可被记下的胜利却很有限。",
      "visualMode": "archive-closure",
      "tension": {
            "fiscal": 76,
            "virtue": 70,
            "people": 60,
            "power": 84
      },
      "evidence": [
            "ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa",
            "ev:src_yantielun_siku:preface:partial_result:1234abcd"
      ]
};
    const scenes = [...historicalPrelude, ...debateRounds, judgmentScene];

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
      document.getElementById("debateHud").innerHTML = `
        <div class="debate-card" data-visual-mode="${escapeHtml(scene.visualMode)}">
          <div class="debate-meta">
            <span class="debate-speaker">${escapeHtml(scene.speaker)}</span>
            <span class="stance-chip">${escapeHtml(scene.stance)}</span>
            <span>${escapeHtml(scene.kicker)}</span>
          </div>
          <p class="debate-line">${escapeHtml(scene.line)}</p>
          <div class="tension-grid" aria-label="本回合思想张力">
            ${axes.map(([axis, label]) => `
              <div class="tension-axis">
                <span>${label}</span>
                <div class="tension-track"><span class="tension-fill" style="width: ${Number(scene.tension[axis] || 0)}%"></span></div>
              </div>
            `).join("")}
          </div>
          <div class="evidence-seals" aria-label="本回合证据印记">
            ${scene.evidence.map((id, index) => `
              <button class="evidence-seal" type="button" data-evidence-id="${escapeHtml(id)}">证据 ${index + 1}</button>
            `).join("")}
          </div>
        </div>
      `;
    }

    function renderMap(scene) {
      const svg = document.getElementById("hanMapScene");
      const features = state.mapLayers.flatMap(layer => layer.features.map(feature => ({ layer, feature })));
      const pressureOpacity = scene.visualMode === "map-pressure" ? 0.96 : scene.visualMode === "background-map" ? 0.72 : 0.42;
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
      const oppositionLayer = scene.visualMode === "seat-opposition" ? `
        <path d="M745 382 C654 304 521 276 363 332" fill="none" stroke="#2c7a66" stroke-width="12" stroke-linecap="round" opacity="0.62"/>
        <text x="744" y="284" text-anchor="middle" fill="#dcf7df" font-size="34">民生</text>
        <text x="255" y="284" text-anchor="middle" fill="rgba(255,244,214,0.48)" font-size="28">边计</text>
      ` : "";
      const clashLayer = scene.visualMode === "value-clash" ? `
        <path d="M260 372 C392 274 608 274 740 372" fill="none" stroke="#36516c" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
        <path d="M740 392 C607 490 393 490 260 392" fill="none" stroke="#2c7a66" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
        <text x="360" y="330" text-anchor="middle" fill="#cfe5ff" font-size="42">利</text>
        <text x="640" y="444" text-anchor="middle" fill="#dcf7df" font-size="42">义</text>
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
      if (scene.visualMode === "seat-opposition") return ["actor_literati"];
      if (scene.visualMode === "value-clash") return ["actor_sang_hongyang", "actor_literati"];
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

    document.getElementById("soundToggle").addEventListener("click", async () => {
      await ensureAudio();
      state.soundEnabled = !state.soundEnabled;
      document.getElementById("soundToggle").setAttribute("aria-pressed", String(state.soundEnabled));
      if (state.soundEnabled) pulseSound("open");
    });

    document.getElementById("judgmentForm").addEventListener("submit", async event => {
      event.preventDefault();
      const sceneEvidence = scenes.flatMap(scene => scene.evidence).filter((id, index, ids) => ids.indexOf(id) === index);
      const response = await fetch(apiBase + "/judgment-cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_claim_ids: ["claim_conflict_is_moral_and_fiscal", "claim_power_network_not_optional"],
          selected_evidence_ids: sceneEvidence,
          personal_reflection: document.getElementById("reflectionInput").value || null,
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
        "map-pressure": 92,
        "seat-opposition": 146,
        "value-clash": 188,
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
