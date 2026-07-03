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
      padding: 92px clamp(16px, 5vw, 72px) 40px;
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
      font-size: clamp(46px, 8vw, 116px);
      line-height: 0.96;
      letter-spacing: 0;
      text-wrap: balance;
      text-shadow: 0 12px 38px rgba(0,0,0,0.34);
    }

    .scene-copy {
      max-width: 660px;
      margin: 22px 0 0;
      color: rgba(255,244,214,0.9);
      font-size: clamp(17px, 2vw, 23px);
      line-height: 1.85;
    }

    .quote-line {
      min-height: 92px;
      margin: 24px 0 0;
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
      grid-template-columns: repeat(5, 1fr);
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
        font-size: 42px;
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
          <svg id="judgmentSvg" viewBox="0 0 1000 680" role="img" aria-label="判断卡收束场景"></svg>
          <form class="judgment-form" id="judgmentForm">
            <textarea id="reflectionInput" placeholder="写下你的判断：当财政必要、民间痛感和权力斗争同时出现时，制度应废止、修正，还是保留并审计？"></textarea>
            <button class="primary" type="submit">作出判断</button>
            <div id="judgmentOutput" class="judgment-output">你的判断不会写入历史证据包。</div>
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

    const scenes = [
      {
        key: "map",
        kicker: "风入长安",
        title: "盐铁会议历史复原",
        copy: "边塞军费、山海盐铁、均输路线，一起把始元六年的朝堂推向一场不可回避的争论。",
        quote: "边用度不足，故兴盐、铁，设酒榷，置均输",
        evidence: ["ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d", "ev:src_shiji_pingzhun:juan030:sang_equal_transport:5e6f7081"]
      },
      {
        key: "court",
        kicker: "朝堂开议",
        title: "席位已经排定",
        copy: "桑弘羊站在国家能力一侧，贤良文学站在民生与德治一侧；汉昭帝在场，霍光的影子也在场。",
        quote: "有司问郡国所举贤良文学民所疾苦",
        evidence: ["ev:src_yantielun:juan01_benyi:meeting_opening:a1b2c3d4", "ev:src_hanshu_zhaodi:juan007:meeting_edict:ccddeeff"]
      },
      {
        key: "court",
        kicker: "义利相击",
        title: "财政理由撞上德治判断",
        copy: "一方说边防不能空，一方说国家不应与民争利。争论的锋刃，不在盐铁本身，而在国家该怎样使用力量。",
        quote: "今郡国有盐、铁、酒榷，均输，与民争利",
        evidence: ["ev:src_yantielun:juan01_benyi:literati_abolish:0a1b2c3d", "ev:src_yantielun:juan01_benyi:virtue_vs_profit:44556677"]
      },
      {
        key: "network",
        kicker: "霍光的阴影",
        title: "政策之后，是权力",
        copy: "盐铁会议不是悬浮的公共辩论。桑弘羊、上官桀、燕王旦和霍光的关系，会在会后一年的政治危机里显出血色。",
        quote: "桑弘羊怨霍光，与上官桀等相结",
        evidence: ["ev:src_hanshu_huoguang:juan068:sang_resentment:778899aa", "ev:src_hanshu_zhaodi:juan007:rebellion_record:ddee0011"]
      },
      {
        key: "judgment",
        kicker: "你的判断",
        title: "当证据逼近你",
        copy: "此刻不需要再翻标签。你只需要回答：财政必要性、民间痛感、权力斗争同时成立时，你如何判断一个制度？",
        quote: "后罢榷酤，而盐、铁则如旧",
        evidence: ["ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa", "ev:src_yantielun_siku:preface:partial_result:1234abcd"]
      }
    ];

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
      renderMap();
      renderCourt();
      renderNetwork();
      renderJudgmentBackdrop();
    }

    function renderMap() {
      const svg = document.getElementById("hanMapScene");
      const features = state.mapLayers.flatMap(layer => layer.features.map(feature => ({ layer, feature })));
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

    function renderCourt() {
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
      svg.innerHTML = `
        <rect width="1000" height="680" fill="rgba(9,13,19,0.18)"/>
        <path d="M116 588 C205 301 337 164 500 158 C663 164 795 301 884 588" fill="none" stroke="rgba(255,236,188,0.22)" stroke-width="4"/>
        <path d="M140 608 L860 608" stroke="rgba(255,236,188,0.22)" stroke-width="4"/>
        <path d="M500 125 L500 608" stroke="rgba(255,236,188,0.16)" stroke-width="3"/>
        <path d="M292 382 C400 300 600 300 708 382" fill="none" stroke="#f3c46d" stroke-width="5" stroke-dasharray="14 16"/>
        ${seats.map(([actorId, x, y, color]) => {
          const actor = state.actors.find(item => item.actor_id === actorId);
          return `<g data-actor="${actorId}">
            <circle cx="${x}" cy="${y}" r="50" fill="${color}" opacity="0.92" stroke="#fff4d6" stroke-width="3"/>
            <text x="${x}" y="${y + 8}" text-anchor="middle" fill="#fff4d6" font-size="24">${escapeHtml(actor ? actor.name : actorId)}</text>
          </g>`;
        }).join("")}
        <text x="500" y="650" text-anchor="middle" fill="rgba(255,244,214,0.66)" font-size="22">朝堂不是中立空间，席位本身就是压力。</text>
      `;
    }

    function renderNetwork() {
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
        <text x="500" y="630" text-anchor="middle" fill="rgba(255,244,214,0.68)" font-size="22">实线是史料明示，虚线是策展推断。争论之后，是清算。</text>
      `;
    }

    function renderJudgmentBackdrop() {
      document.getElementById("judgmentSvg").innerHTML = `
        <rect width="1000" height="680" fill="rgba(9,13,19,0.24)"/>
        <path d="M205 150 C344 88 662 88 795 150 C842 310 812 470 708 538 C587 612 412 612 292 538 C188 470 158 310 205 150 Z"
          fill="rgba(255,244,214,0.12)" stroke="rgba(255,236,188,0.42)" stroke-width="4"/>
        <text x="500" y="265" text-anchor="middle" fill="#fff4d6" font-size="50">证据抵达，判断开始</text>
        <text x="500" y="325" text-anchor="middle" fill="rgba(255,244,214,0.72)" font-size="24">个人反思不会成为历史事实。</text>
      `;
    }

    async function renderScene() {
      const scene = scenes[state.sceneIndex];
      document.getElementById("chapterKicker").textContent = scene.kicker;
      document.getElementById("sceneTitle").textContent = scene.title;
      document.getElementById("sceneCopy").textContent = scene.copy;
      document.getElementById("sceneQuote").textContent = scene.quote;
      document.getElementById("advanceScene").textContent = state.sceneIndex === scenes.length - 1 ? "停在这里" : "继续进入";
      document.getElementById("rewindScene").style.visibility = state.sceneIndex === 0 ? "hidden" : "visible";
      document.querySelectorAll("[data-scene-layer]").forEach(layer => layer.classList.remove("is-active"));
      const layerId = scene.key === "map" ? "mapScene" : scene.key === "court" ? "courtScene" : scene.key === "network" ? "networkScene" : "judgmentScene";
      document.getElementById(layerId).classList.add("is-active");
      document.getElementById("evidenceRibbon").classList.remove("is-open");
      updateRail();
      await preloadSceneEvidence(scene);
      pulseSound(scene.key);
    }

    async function preloadSceneEvidence(scene) {
      await Promise.all(scene.evidence.map(getEvidence));
    }

    async function openEvidence() {
      const scene = scenes[state.sceneIndex];
      const evidenceItems = await Promise.all(scene.evidence.map(getEvidence));
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

    document.getElementById("revealEvidence").addEventListener("click", openEvidence);

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
        `判断卡 ${data.judgment_card_id}\\n` +
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
      const freqs = { map: 96, court: 128, network: 72, judgment: 180, evidence: 232, open: 156 };
      osc.frequency.value = freqs[kind] || 110;
      osc.type = kind === "network" ? "sawtooth" : "sine";
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
