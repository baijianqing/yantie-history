"""Playable web surface for the Yantie meeting reconstruction."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from metaos import __version__
from metaos.yantie.api import create_yantie_api_router


def create_yantie_web_router() -> APIRouter:
    """Serve the lightweight browser UI without a frontend build step."""

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
      --ink: #17202a;
      --muted: #5b677a;
      --paper: #f7f3e8;
      --surface: #fffaf0;
      --line: #d6c9ad;
      --vermillion: #9f2d20;
      --jade: #1f6f5b;
      --indigo: #293b63;
      --gold: #b2762b;
      --mist: #edf3f4;
      --shadow: 0 16px 48px rgba(23, 32, 42, 0.14);
    }

    * { box-sizing: border-box; }

    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      font-family: "Noto Serif SC", "Songti SC", "Microsoft YaHei", serif;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(41,59,99,0.08) 1px, transparent 1px),
        linear-gradient(0deg, rgba(41,59,99,0.08) 1px, transparent 1px),
        #f6f7f3;
      background-size: 34px 34px;
    }

    button, input, textarea, select {
      font: inherit;
    }

    button {
      border: 1px solid var(--line);
      background: #fffdf7;
      color: var(--ink);
      min-height: 40px;
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
    }

    button:hover, button:focus-visible {
      border-color: var(--vermillion);
      outline: 2px solid rgba(159,45,32,0.18);
      outline-offset: 1px;
    }

    .app-shell {
      min-height: 100vh;
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 12px clamp(16px, 3vw, 40px);
      background: rgba(247, 243, 232, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
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
      width: 36px;
      height: 36px;
      border-radius: 6px;
      background: var(--vermillion);
      color: white;
      font-weight: 700;
    }

    .brand strong {
      display: block;
      font-size: 18px;
      line-height: 1.15;
      white-space: nowrap;
    }

    .brand span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }

    .nav {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .nav a {
      color: var(--ink);
      text-decoration: none;
      white-space: nowrap;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 14px;
    }

    .nav a:hover, .nav a:focus-visible {
      border-color: var(--line);
      background: #fffdf7;
      outline: none;
    }

    .hero {
      min-height: min(760px, calc(100vh - 62px));
      display: grid;
      grid-template-columns: minmax(280px, 0.94fr) minmax(360px, 1.35fr);
      gap: clamp(18px, 4vw, 44px);
      align-items: center;
      padding: clamp(28px, 5vw, 64px) clamp(16px, 5vw, 72px) 32px;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(120deg, rgba(255,250,240,0.92), rgba(237,243,244,0.84)),
        radial-gradient(circle at 80% 10%, rgba(178,118,43,0.12), transparent 32%);
    }

    .hero-copy {
      max-width: 720px;
    }

    .eyebrow {
      color: var(--vermillion);
      font-size: 14px;
      letter-spacing: 0;
      font-weight: 700;
      margin: 0 0 10px;
    }

    h1 {
      margin: 0;
      font-size: clamp(44px, 7vw, 92px);
      line-height: 0.95;
      letter-spacing: 0;
    }

    .hero-copy p {
      margin: 18px 0 0;
      max-width: 620px;
      color: #2f3a49;
      font-size: clamp(17px, 2vw, 22px);
      line-height: 1.8;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 26px;
    }

    .primary {
      background: var(--ink);
      border-color: var(--ink);
      color: #fffaf0;
    }

    .secondary {
      background: transparent;
      border-color: var(--indigo);
      color: var(--indigo);
    }

    .hero-stage {
      min-height: 520px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 12px;
    }

    .stage-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
    }

    .map-board {
      position: relative;
      min-height: 480px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: linear-gradient(160deg, #f9f3de, #edf3f4 60%, #f4f0e7);
      box-shadow: var(--shadow);
    }

    .map-board svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .map-label {
      position: absolute;
      right: 16px;
      bottom: 14px;
      max-width: min(420px, calc(100% - 32px));
      padding: 10px 12px;
      border: 1px solid rgba(23,32,42,0.18);
      border-radius: 6px;
      background: rgba(255,253,247,0.88);
      color: var(--ink);
      font-size: 13px;
      line-height: 1.55;
    }

    .band {
      padding: clamp(28px, 5vw, 54px) clamp(16px, 5vw, 72px);
      border-bottom: 1px solid var(--line);
      background: rgba(255, 253, 247, 0.76);
    }

    .band.alt {
      background: rgba(237,243,244,0.78);
    }

    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-end;
      margin-bottom: 18px;
    }

    .section-head h2 {
      margin: 0;
      font-size: clamp(24px, 3vw, 40px);
      line-height: 1.12;
    }

    .section-head p {
      max-width: 720px;
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }

    .meeting-grid {
      display: grid;
      grid-template-columns: minmax(280px, 0.78fr) minmax(320px, 1.22fr);
      gap: 18px;
      align-items: stretch;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,253,247,0.92);
      padding: 16px;
      min-width: 0;
    }

    .panel h3 {
      margin: 0 0 12px;
      font-size: 20px;
    }

    .timeline {
      display: grid;
      gap: 10px;
    }

    .event-row {
      display: grid;
      grid-template-columns: minmax(84px, 0.28fr) 1fr;
      gap: 12px;
      align-items: start;
      border-left: 3px solid var(--gold);
      padding: 8px 0 8px 12px;
    }

    .date {
      color: var(--vermillion);
      font-weight: 700;
      line-height: 1.4;
    }

    .event-row strong {
      display: block;
      line-height: 1.35;
    }

    .event-row span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      line-height: 1.55;
    }

    .seat-map {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .actor-seat {
      min-height: 118px;
      border: 1px solid #d8c6a0;
      border-radius: 8px;
      background: #fffaf0;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .actor-seat[data-position="state_policy_defender"] { border-top: 4px solid var(--indigo); }
    .actor-seat[data-position="literati_opposition"] { border-top: 4px solid var(--jade); }
    .actor-seat[data-position="regent_power"] { border-top: 4px solid var(--vermillion); }
    .actor-seat[data-position="imperial_center"] { border-top: 4px solid var(--gold); }

    .actor-seat strong {
      font-size: 18px;
      line-height: 1.2;
    }

    .actor-seat small {
      color: var(--muted);
      line-height: 1.45;
    }

    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }

    .tabs button[aria-pressed="true"] {
      background: var(--indigo);
      border-color: var(--indigo);
      color: white;
    }

    .claims-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .claim-item, .evidence-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fffdf7;
      padding: 14px;
      display: grid;
      gap: 10px;
      min-width: 0;
    }

    .claim-item strong, .evidence-item strong {
      line-height: 1.45;
    }

    .tagline {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .tag {
      border: 1px solid rgba(41,59,99,0.18);
      border-radius: 999px;
      padding: 3px 8px;
      color: var(--indigo);
      background: #f4f7fb;
      font-size: 12px;
      line-height: 1.4;
      white-space: nowrap;
    }

    .claim-actions, .evidence-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .search-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      margin-bottom: 14px;
    }

    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fffdf7;
      color: var(--ink);
      padding: 10px 12px;
      min-height: 40px;
    }

    textarea {
      min-height: 96px;
      resize: vertical;
      line-height: 1.6;
    }

    .split {
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(280px, 0.8fr);
      gap: 16px;
      align-items: start;
    }

    .evidence-list {
      display: grid;
      gap: 10px;
      max-height: 640px;
      overflow: auto;
      padding-right: 4px;
    }

    .detail-drawer {
      position: sticky;
      top: 84px;
    }

    .detail-drawer p {
      color: var(--muted);
      line-height: 1.7;
    }

    .quote {
      margin: 0;
      padding: 12px;
      border-left: 4px solid var(--vermillion);
      background: #f9f2e3;
      line-height: 1.75;
    }

    .network-wrap {
      min-height: 520px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fffdf7;
      overflow: hidden;
    }

    .network-wrap svg {
      width: 100%;
      height: 520px;
      display: block;
    }

    .judgment-grid {
      display: grid;
      grid-template-columns: minmax(280px, 0.7fr) minmax(320px, 1fr);
      gap: 16px;
      align-items: start;
    }

    .selected-list {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .selected-list li {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      background: #fffdf7;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }

    .judgment-output {
      white-space: pre-wrap;
      line-height: 1.7;
      min-height: 180px;
    }

    .status-line {
      color: var(--muted);
      font-size: 13px;
      min-height: 20px;
    }

    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      background: rgba(255,253,247,0.72);
      line-height: 1.7;
    }

    @media (max-width: 980px) {
      .hero, .meeting-grid, .split, .judgment-grid {
        grid-template-columns: 1fr;
      }

      .hero {
        min-height: auto;
      }

      .hero-stage {
        min-height: 420px;
      }

      .map-board {
        min-height: 420px;
      }

      .claims-grid {
        grid-template-columns: 1fr;
      }

      .detail-drawer {
        position: static;
      }
    }

    @media (max-width: 680px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
      }

      .nav {
        width: 100%;
      }

      .seat-map {
        grid-template-columns: 1fr;
      }

      .search-row {
        grid-template-columns: 1fr;
      }

      .event-row {
        grid-template-columns: 1fr;
      }

      h1 {
        font-size: 40px;
        line-height: 1.08;
      }

      .map-label {
        left: 16px;
        right: 16px;
      }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="seal" aria-hidden="true">盐</div>
        <div>
          <strong>盐铁会议</strong>
          <span>始元六年 · 证据驱动的历史复原</span>
        </div>
      </div>
      <nav class="nav" aria-label="主要区域">
        <a href="#meeting">会议现场</a>
        <a href="#evidence">证据室</a>
        <a href="#network">权力网</a>
        <a href="#judgment">判断卡</a>
      </nav>
    </header>

    <main>
      <section class="hero" id="top">
        <div class="hero-copy">
          <p class="eyebrow">2026 人文季 · 用 AI 重新看见人</p>
          <h1>盐铁会议历史复原</h1>
          <p id="coreQuestion">进入汉昭帝始元六年的朝堂，在盐铁官营、边费、民生、德治与权力关系之间做一次有证据的判断。</p>
          <div class="hero-actions">
            <a href="#meeting"><button class="primary">进入会议现场</button></a>
            <a href="#evidence"><button class="secondary">先查证据</button></a>
          </div>
        </div>
        <div class="hero-stage" aria-label="汉代地理与会议压力图">
          <div class="stage-toolbar">
            <span id="packStatus">读取证据包中</span>
          </div>
          <div class="map-board">
            <svg id="hanMap" viewBox="0 0 100 70" role="img" aria-label="汉代地理版图示意"></svg>
            <div class="map-label" id="mapCaption">长安不是孤立的朝堂。边塞军费、山海盐铁、转运网络，都把辩论压进同一张地图。</div>
          </div>
        </div>
      </section>

      <section class="band" id="meeting">
        <div class="section-head">
          <div>
            <p class="eyebrow">会议现场</p>
            <h2>谁坐在席上，谁在席外施力</h2>
          </div>
          <p>这里不是单纯的财政会议。桑弘羊为国家能力辩护，贤良文学以德治与民生反诘，霍光辅政格局则构成隐形边界。</p>
        </div>
        <div class="meeting-grid">
          <section class="panel">
            <h3>辩题时间线</h3>
            <div class="timeline" id="eventTimeline"></div>
          </section>
          <section class="panel">
            <h3>角色席位</h3>
            <div class="seat-map" id="actorSeats"></div>
          </section>
        </div>
      </section>

      <section class="band alt" id="claims">
        <div class="section-head">
          <div>
            <p class="eyebrow">从知识到认知</p>
            <h2>把主张分栏，而不是混成答案</h2>
          </div>
          <p>原文事实、策展推断、争议观点和个人反思被分开展示。每条历史主张都可以展开证据。</p>
        </div>
        <div class="tabs" id="claimTabs" aria-label="主张展示区"></div>
        <div class="claims-grid" id="claimList"></div>
      </section>

      <section class="band" id="evidence">
        <div class="section-head">
          <div>
            <p class="eyebrow">证据室</p>
            <h2>先看材料，再下判断</h2>
          </div>
          <p>检索只使用交付包内的精选证据，不调用模型补答。超出档案的问题会显示“档案不足”。</p>
        </div>
        <form class="search-row" id="evidenceSearch">
          <input id="queryInput" name="q" value="桑弘羊 财政" autocomplete="off" aria-label="搜索证据" />
          <button class="primary" type="submit">搜索证据</button>
        </form>
        <div class="split">
          <div class="evidence-list" id="evidenceResults"></div>
          <aside class="panel detail-drawer" id="evidenceDetail">
            <h3>证据详情</h3>
            <p>点击任意证据或主张中的“展开证据”，这里会显示原文摘录、现代转述、出处和证据边界。</p>
          </aside>
        </div>
      </section>

      <section class="band alt" id="network">
        <div class="section-head">
          <div>
            <p class="eyebrow">权力关系网</p>
            <h2>政策争论背后的权力结构</h2>
          </div>
          <p>关系图把人物、议题与史料关系放在同一张图中：哪些是明文证据，哪些只是策展推断，一眼可分。</p>
        </div>
        <div class="network-wrap">
          <svg id="powerNetwork" viewBox="0 0 960 520" role="img" aria-label="盐铁会议权力关系网"></svg>
        </div>
      </section>

      <section class="band" id="judgment">
        <div class="section-head">
          <div>
            <p class="eyebrow">用户判断卡</p>
            <h2>保留你的判断，也保留证据边界</h2>
          </div>
          <p>判断卡只在本地响应中生成，不写入历史证据包。个人反思不会被混入历史事实。</p>
        </div>
        <div class="judgment-grid">
          <section class="panel">
            <h3>已选材料</h3>
            <ul class="selected-list" id="selectedList"></ul>
            <textarea id="reflectionInput" placeholder="写下你的判断：当制度同时维持公共财政又制造民间痛感时，你倾向废止、修正，还是保留并审计？"></textarea>
            <div class="claim-actions">
              <button class="primary" id="buildJudgment" type="button">生成判断卡</button>
              <button id="clearSelection" type="button">清空选择</button>
            </div>
            <div class="status-line" id="judgmentStatus"></div>
          </section>
          <section class="panel">
            <h3>判断卡输出</h3>
            <div class="judgment-output" id="judgmentOutput">从主张或证据中选择材料后生成。</div>
          </section>
        </div>
      </section>
    </main>
  </div>

  <script>
    const apiBase = "/api/yantie";
    const state = {
      manifest: null,
      theme: null,
      actors: [],
      events: [],
      topics: [],
      claims: [],
      relations: [],
      mapLayers: [],
      selectedClaims: new Set(),
      selectedEvidence: new Set(),
      evidenceCache: new Map(),
      claimZone: "meeting"
    };

    const zoneLabels = {
      meeting: "会议现场",
      map: "地图",
      evidence_room: "证据室",
      power_network: "权力网",
      later_echo: "后世回声",
      judgment_card: "判断卡"
    };

    async function getJson(path, options = {}) {
      const response = await fetch(apiBase + path, options);
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.error ? body.error.message : "接口不可用");
      }
      return body.data;
    }

    async function boot() {
      const [manifest, theme, actors, events, topics, claims, relations, mapLayers] = await Promise.all([
        getJson("/manifest"),
        getJson("/theme"),
        getJson("/actors?include=evidence_summary"),
        getJson("/events"),
        getJson("/topics"),
        getJson("/claims"),
        getJson("/relations"),
        getJson("/map-layers")
      ]);

      state.manifest = manifest;
      state.theme = theme;
      state.actors = actors.items;
      state.events = events.items;
      state.topics = topics.items;
      state.claims = claims.items;
      state.relations = relations.items;
      state.mapLayers = mapLayers.items;

      document.getElementById("coreQuestion").textContent = theme.core_question;
      document.getElementById("packStatus").textContent = `${manifest.evidence_count} 条证据 · ${manifest.claim_count} 条主张 · 无运行时 RAG`;
      renderMap();
      renderTimeline();
      renderActors();
      renderClaimTabs();
      renderClaims();
      renderNetwork();
      renderSelection();
      await runSearch(document.getElementById("queryInput").value);
    }

    function renderMap() {
      const svg = document.getElementById("hanMap");
      const layers = state.mapLayers;
      const featureDots = layers.flatMap(layer => layer.features.map(feature => ({ layer, feature })));
      const colorFor = {
        capital: "#9f2d20",
        military_frontier: "#293b63",
        resource_point: "#1f6f5b",
        route: "#b2762b",
        region: "#5b677a",
        policy_pressure: "#7c3aed"
      };
      svg.innerHTML = `
        <defs>
          <pattern id="grain" width="7" height="7" patternUnits="userSpaceOnUse">
            <path d="M 0 7 L 7 0" stroke="rgba(23,32,42,0.08)" stroke-width="0.4" />
          </pattern>
        </defs>
        <path d="M13,45 C16,25 31,13 50,16 C66,8 83,20 87,37 C82,54 65,62 43,60 C25,62 12,56 13,45 Z"
          fill="#f6deb0" stroke="#8c6f3e" stroke-width="1.2" />
        <path d="M23,45 C36,39 49,42 62,31 C72,23 81,28 86,37" fill="none" stroke="#b2762b" stroke-width="1.2" stroke-dasharray="2 2" />
        <path d="M42,18 C48,25 58,28 63,36 C68,45 70,53 77,59" fill="none" stroke="#4f7f75" stroke-width="0.9" opacity="0.9" />
        <rect x="0" y="0" width="100" height="70" fill="url(#grain)" opacity="0.7" />
        ${featureDots.map(({ layer, feature }) => {
          const [x, y] = feature.coordinates.length === 2 ? feature.coordinates : [50, 50];
          const color = colorFor[layer.layer_type] || "#17202a";
          const textY = y > 55 ? y - 6 : Math.max(y - 2, 8);
          return `<g tabindex="0" data-feature="${feature.feature_id}">
            <circle cx="${x}" cy="${y}" r="2.7" fill="${color}" stroke="#fffaf0" stroke-width="1.2" />
            <text x="${Math.min(x + 3.5, 84)}" y="${textY}" font-size="3.4" fill="#17202a">${escapeHtml(feature.title)}</text>
          </g>`;
        }).join("")}
      `;
    }

    function renderTimeline() {
      const target = document.getElementById("eventTimeline");
      target.innerHTML = state.events.map(event => `
        <article class="event-row">
          <div class="date">${escapeHtml(event.date_label)}</div>
          <div>
            <strong>${escapeHtml(event.title)}</strong>
            <span>${escapeHtml(event.summary)}</span>
          </div>
        </article>
      `).join("");
    }

    function renderActors() {
      const order = ["actor_zhao_di", "actor_huo_guang", "actor_sang_hongyang", "actor_literati", "actor_che_qianqiu", "actor_shangguan_jie", "actor_yan_wang_dan"];
      const target = document.getElementById("actorSeats");
      const actors = [...state.actors].sort((a, b) => order.indexOf(a.actor_id) - order.indexOf(b.actor_id));
      target.innerHTML = actors.map(actor => `
        <article class="actor-seat" data-position="${escapeHtml(actor.meeting_position)}">
          <strong>${escapeHtml(actor.name)}</strong>
          <small>${escapeHtml(actor.role_title)}</small>
          <small>${escapeHtml(actor.stance_summary)}</small>
          <button type="button" data-actor="${escapeHtml(actor.actor_id)}">查看相关证据</button>
        </article>
      `).join("");
      target.querySelectorAll("[data-actor]").forEach(button => {
        button.addEventListener("click", async () => {
          document.getElementById("queryInput").value = "";
          await runSearch("", { actor_id: button.dataset.actor });
          document.getElementById("evidence").scrollIntoView({ behavior: "smooth" });
        });
      });
    }

    function renderClaimTabs() {
      const zones = [...new Set(state.claims.map(claim => claim.display_zone))];
      const target = document.getElementById("claimTabs");
      target.innerHTML = zones.map(zone => `
        <button type="button" data-zone="${escapeHtml(zone)}" aria-pressed="${zone === state.claimZone}">
          ${escapeHtml(zoneLabels[zone] || zone)}
        </button>
      `).join("");
      target.querySelectorAll("[data-zone]").forEach(button => {
        button.addEventListener("click", () => {
          state.claimZone = button.dataset.zone;
          renderClaimTabs();
          renderClaims();
        });
      });
    }

    function renderClaims() {
      const target = document.getElementById("claimList");
      const claims = state.claims.filter(claim => claim.display_zone === state.claimZone);
      if (!claims.length) {
        target.innerHTML = `<div class="empty">这个展示区暂时没有主张。</div>`;
        return;
      }
      target.innerHTML = claims.map(claim => `
        <article class="claim-item">
          <div class="tagline">
            <span class="tag">${escapeHtml(claim.claim_type)}</span>
            <span class="tag">${escapeHtml(claim.stance)}</span>
          </div>
          <strong>${escapeHtml(claim.statement)}</strong>
          ${claim.reasoning_note ? `<p>${escapeHtml(claim.reasoning_note)}</p>` : ""}
          <div class="claim-actions">
            ${claim.claim_type !== "personal_reflection_prompt" ? `<button type="button" data-select-claim="${escapeHtml(claim.claim_id)}">加入判断</button>` : ""}
            ${claim.evidence_ids.length ? `<button type="button" data-claim-evidence="${escapeHtml(claim.claim_id)}">展开证据 ${claim.evidence_ids.length}</button>` : ""}
          </div>
        </article>
      `).join("");
      target.querySelectorAll("[data-select-claim]").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedClaims.add(button.dataset.selectClaim);
          renderSelection();
        });
      });
      target.querySelectorAll("[data-claim-evidence]").forEach(button => {
        button.addEventListener("click", () => showClaimEvidence(button.dataset.claimEvidence));
      });
    }

    async function showClaimEvidence(claimId) {
      const claim = state.claims.find(item => item.claim_id === claimId);
      if (!claim) return;
      const evidenceIds = [...claim.evidence_ids, ...claim.counterevidence_ids];
      const evidenceItems = [];
      for (const evidenceId of evidenceIds) {
        evidenceItems.push(await getEvidence(evidenceId));
        state.selectedEvidence.add(evidenceId);
      }
      renderEvidenceResults(evidenceItems.map(evidence => ({ evidence, source: null, score: 0, matched_terms: [], match_reasons: ["claim_link"] })));
      renderEvidenceDetail(evidenceItems[0]);
      renderSelection();
      document.getElementById("evidence").scrollIntoView({ behavior: "smooth" });
    }

    async function getEvidence(evidenceId) {
      if (!state.evidenceCache.has(evidenceId)) {
        state.evidenceCache.set(evidenceId, await getJson(`/evidence/${encodeURIComponent(evidenceId)}`));
      }
      return state.evidenceCache.get(evidenceId);
    }

    document.getElementById("evidenceSearch").addEventListener("submit", async event => {
      event.preventDefault();
      await runSearch(document.getElementById("queryInput").value);
    });

    async function runSearch(query, extraParams = {}) {
      const params = new URLSearchParams({ q: query || "", limit: "12", ...extraParams });
      const data = await getJson(`/evidence/search?${params.toString()}`);
      const target = document.getElementById("evidenceResults");
      if (data.archive_status === "archive_insufficient") {
        target.innerHTML = `<div class="empty">档案不足：这个问题暂时没有可定位证据。你可以换成“桑弘羊 财政”“反对 盐铁 官营”“会议 结果”。</div>`;
        return;
      }
      renderEvidenceResults(data.items);
      if (data.items[0]) {
        renderEvidenceDetail(data.items[0].evidence, data.items[0].source);
      }
    }

    function renderEvidenceResults(items) {
      const target = document.getElementById("evidenceResults");
      target.innerHTML = items.map(item => {
        const evidence = item.evidence || item;
        const sourceTitle = item.source ? item.source.title : evidence.source_id;
        return `
          <article class="evidence-item">
            <div class="tagline">
              <span class="tag">${escapeHtml(evidence.evidence_kind)}</span>
              <span class="tag">${escapeHtml(evidence.certainty)}</span>
              ${item.score ? `<span class="tag">score ${item.score}</span>` : ""}
            </div>
            <strong>${escapeHtml(evidence.paraphrase_zh)}</strong>
            <small>${escapeHtml(sourceTitle)} · ${escapeHtml(evidence.canonical_location)}</small>
            <div class="evidence-actions">
              <button type="button" data-open-evidence="${escapeHtml(evidence.evidence_id)}">查看详情</button>
              <button type="button" data-select-evidence="${escapeHtml(evidence.evidence_id)}">加入判断</button>
            </div>
          </article>
        `;
      }).join("");
      target.querySelectorAll("[data-open-evidence]").forEach(button => {
        button.addEventListener("click", async () => renderEvidenceDetail(await getEvidence(button.dataset.openEvidence)));
      });
      target.querySelectorAll("[data-select-evidence]").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedEvidence.add(button.dataset.selectEvidence);
          renderSelection();
        });
      });
    }

    function renderEvidenceDetail(evidence, source = null) {
      const target = document.getElementById("evidenceDetail");
      const sourceLabel = source ? source.title : evidence.source_id;
      target.innerHTML = `
        <h3>证据详情</h3>
        ${evidence.excerpt_original ? `<blockquote class="quote">${escapeHtml(evidence.excerpt_original)}</blockquote>` : ""}
        <p><strong>转述：</strong>${escapeHtml(evidence.paraphrase_zh)}</p>
        <p><strong>出处：</strong>${escapeHtml(sourceLabel)} · ${escapeHtml(evidence.canonical_location)}</p>
        <p><strong>边界：</strong>${escapeHtml(evidence.copyright_note)}；状态 ${escapeHtml(evidence.review_status)}。</p>
        <div class="tagline">
          ${evidence.topic_ids.map(topicId => `<span class="tag">${escapeHtml(topicTitle(topicId))}</span>`).join("")}
          ${evidence.value_tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
        </div>
      `;
    }

    function topicTitle(topicId) {
      const topic = state.topics.find(item => item.topic_id === topicId);
      return topic ? topic.title : topicId;
    }

    function renderNetwork() {
      const svg = document.getElementById("powerNetwork");
      const nodes = {
        actor_huo_guang: { x: 480, y: 130, label: "霍光", color: "#9f2d20" },
        actor_zhao_di: { x: 480, y: 48, label: "汉昭帝", color: "#b2762b" },
        actor_sang_hongyang: { x: 265, y: 240, label: "桑弘羊", color: "#293b63" },
        actor_literati: { x: 690, y: 250, label: "贤良文学", color: "#1f6f5b" },
        actor_shangguan_jie: { x: 230, y: 410, label: "上官桀", color: "#5b677a" },
        actor_yan_wang_dan: { x: 480, y: 455, label: "燕王旦", color: "#5b677a" },
        actor_che_qianqiu: { x: 690, y: 405, label: "车千秋", color: "#5b677a" }
      };
      const actorRelations = state.relations.filter(relation => nodes[relation.from_id] && nodes[relation.to_id]);
      svg.innerHTML = `
        <rect x="0" y="0" width="960" height="520" fill="#fffdf7" />
        ${actorRelations.map(relation => {
          const from = nodes[relation.from_id];
          const to = nodes[relation.to_id];
          const dashed = relation.strength === "explicit_source" ? "" : "stroke-dasharray='7 7'";
          return `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="#8a7a5f" stroke-width="2" ${dashed} />`;
        }).join("")}
        ${Object.entries(nodes).map(([id, node]) => `
          <g data-network-node="${id}">
            <circle cx="${node.x}" cy="${node.y}" r="48" fill="${node.color}" opacity="0.92" />
            <text x="${node.x}" y="${node.y + 5}" text-anchor="middle" font-size="20" fill="white">${escapeHtml(node.label)}</text>
          </g>
        `).join("")}
        <text x="32" y="42" font-size="18" fill="#17202a">实线为明文关系，虚线为策展推断</text>
      `;
    }

    function renderSelection() {
      const target = document.getElementById("selectedList");
      const rows = [];
      state.selectedClaims.forEach(claimId => {
        const claim = state.claims.find(item => item.claim_id === claimId);
        rows.push(`<li>主张：${escapeHtml(claim ? claim.statement : claimId)}</li>`);
      });
      state.selectedEvidence.forEach(evidenceId => {
        rows.push(`<li>证据：${escapeHtml(evidenceId)}</li>`);
      });
      target.innerHTML = rows.length ? rows.join("") : `<li>尚未选择主张或证据。</li>`;
    }

    document.getElementById("clearSelection").addEventListener("click", () => {
      state.selectedClaims.clear();
      state.selectedEvidence.clear();
      document.getElementById("judgmentOutput").textContent = "从主张或证据中选择材料后生成。";
      renderSelection();
    });

    document.getElementById("buildJudgment").addEventListener("click", async () => {
      const status = document.getElementById("judgmentStatus");
      status.textContent = "生成中";
      try {
        const response = await fetch(apiBase + "/judgment-cards", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            selected_claim_ids: [...state.selectedClaims],
            selected_evidence_ids: [...state.selectedEvidence],
            personal_reflection: document.getElementById("reflectionInput").value || null,
            disposition: "modern_analogy_with_caution"
          })
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error ? body.error.message : "生成失败");
        const data = body.data;
        document.getElementById("judgmentOutput").textContent =
          `判断卡：${data.judgment_card_id}\\n` +
          `处置：${data.disposition}\\n` +
          `历史边界：${data.history_boundary}\\n` +
          `原文事实：${data.sections.original_facts.length} 条\\n` +
          `策展推断：${data.sections.curatorial_inferences.length} 条\\n` +
          `争议观点：${data.sections.contested_views.length} 条\\n` +
          `反思：${data.sections.personal_reflection || "未填写"}\\n` +
          `提醒：${data.caution || "无"}`;
        status.textContent = "判断卡已生成，不写入证据包";
      } catch (error) {
        status.textContent = error.message;
      }
    });

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
      document.getElementById("packStatus").textContent = "证据包读取失败";
      document.getElementById("evidenceResults").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    });
  </script>
</body>
</html>
"""
