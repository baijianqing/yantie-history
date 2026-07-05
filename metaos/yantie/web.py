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
      overflow-x: hidden;
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
      grid-column: 1;
      grid-row: 1;
      max-width: 760px;
      min-width: 0;
      align-self: center;
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
      grid-column: 2;
      grid-row: 1 / span 2;
      position: relative;
      min-height: 640px;
      border: 1px solid rgba(255,236,188,0.24);
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(255,244,214,0.08), rgba(9,13,19,0.4));
      overflow: hidden;
      box-shadow: var(--shadow);
    }

    .stage.is-prologue-active .scene-shell {
      grid-template-columns: 1fr;
      gap: 0;
      align-items: stretch;
      padding: 88px clamp(14px, 4vw, 54px) 64px;
    }

    .stage.is-prologue-active .story-panel {
      position: fixed;
      left: clamp(18px, 5vw, 70px);
      bottom: clamp(22px, 8vh, 82px);
      z-index: 18;
      width: min(560px, calc(100vw - 36px));
      max-width: none;
      pointer-events: auto;
    }

    .stage.is-prologue-active .chapter-kicker {
      margin-bottom: 10px;
      text-shadow: 0 8px 28px rgba(0,0,0,0.64);
    }

    .stage.is-prologue-active .scene-title {
      font-size: clamp(32px, 5vw, 58px);
      line-height: 1.04;
      max-width: 12em;
    }

    .stage.is-prologue-active .scene-copy {
      max-width: 460px;
      margin-top: 12px;
      font-size: clamp(15px, 1.45vw, 18px);
      line-height: 1.72;
      text-shadow: 0 8px 24px rgba(0,0,0,0.72);
    }

    .stage.is-prologue-active .quote-line,
    .stage.is-prologue-active #revealEvidence,
    .stage.is-prologue-active #evidenceScrim,
    .stage.is-prologue-active #evidenceRibbon,
    .stage.is-prologue-active .evidence-seals,
    .stage.is-prologue-active #chapterMapToggle,
    .stage.is-prologue-active #rewindScene,
    .stage.is-prologue-active #decisionDock,
    .stage.is-prologue-active #debateHud,
    .stage.is-prologue-active #timelineRail,
    .stage.is-prologue-active .scene-footnote {
      display: none;
    }

    .stage.is-prologue-active .scene-actions {
      margin-top: 18px;
    }

    .stage.is-prologue-active #advanceScene:disabled {
      cursor: not-allowed;
      opacity: 0.48;
    }

    .stage.is-prologue-active .scene-world {
      grid-column: 1;
      grid-row: 1;
      min-height: calc(100vh - 152px);
      border: 0;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
    }

    .court-pressure-opening {
      position: absolute;
      inset: 0;
      z-index: 5;
      pointer-events: none;
      overflow: hidden;
    }

    .prologue-map-note {
      position: absolute;
      right: 22px;
      bottom: 18px;
      z-index: 6;
      max-width: 270px;
      color: rgba(255,244,214,0.6);
      font-size: 11px;
      line-height: 1.55;
      text-align: right;
      opacity: 0;
      transition: opacity 420ms ease;
    }

    .stage.is-prologue-active .prologue-map-note {
      opacity: 1;
    }

    .pressure-director-panel {
      position: absolute;
      top: clamp(78px, 10vh, 118px);
      right: clamp(16px, 4vw, 42px);
      z-index: 7;
      width: min(430px, calc(100vw - 32px));
      padding: 16px;
      border: 1px solid rgba(255,236,188,0.24);
      border-radius: 8px;
      background: rgba(9,13,19,0.48);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
      color: #fff4d6;
      pointer-events: auto;
    }

    .stage:not(.is-prologue-active) .pressure-director-panel {
      display: none;
    }

    .pressure-director-panel h2 {
      margin: 0 0 8px;
      font-size: 20px;
      line-height: 1.35;
    }

    .pressure-director-panel p {
      margin: 0;
      color: rgba(255,244,214,0.78);
      line-height: 1.62;
    }

    .pressure-time {
      display: inline-flex;
      margin-bottom: 10px;
      padding: 3px 8px;
      border: 1px solid rgba(243,196,109,0.36);
      border-radius: 999px;
      color: #f3c46d;
      font-size: 12px;
      font-weight: 700;
      background: rgba(154,36,28,0.14);
    }

    .pressure-grid {
      display: grid;
      gap: 9px;
      margin: 14px 0;
    }

    .pressure-row {
      display: grid;
      grid-template-columns: 46px minmax(0, 1fr) 34px;
      align-items: center;
      gap: 8px;
      color: rgba(255,244,214,0.78);
      font-size: 12px;
    }

    .pressure-bar,
    .support-track {
      height: 7px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255,244,214,0.13);
    }

    .pressure-bar i,
    .support-track i {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #36516c, #f3c46d, #9a241c);
    }

    .support-strength {
      display: grid;
      grid-template-columns: 116px minmax(0, 1fr) 30px;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      color: rgba(255,244,214,0.66);
      font-size: 12px;
    }

    .support-note {
      margin-top: 8px;
      color: rgba(255,244,214,0.56);
      font-size: 11px;
      line-height: 1.5;
    }

    .standpoint-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .standpoint-card {
      min-height: 132px;
      padding: 12px;
      border: 1px solid rgba(255,236,188,0.2);
      border-radius: 6px;
      color: #fff4d6;
      text-align: left;
      cursor: pointer;
      background: rgba(255,244,214,0.08);
      transition: border-color 180ms ease, background 180ms ease, transform 180ms ease;
    }

    .standpoint-card.is-selected {
      border-color: rgba(243,196,109,0.82);
      background: rgba(154,36,28,0.2);
      transform: translateY(-2px);
    }

    .standpoint-card strong,
    .standpoint-card span {
      display: block;
    }

    .standpoint-card strong {
      margin-bottom: 7px;
      color: #ffe7b0;
      font-size: 14px;
    }

    .standpoint-card span {
      color: rgba(255,244,214,0.72);
      font-size: 12px;
      line-height: 1.5;
    }

    .drama-thread {
      position: absolute;
      left: 9%;
      right: 9%;
      top: 12%;
      height: 2px;
      background: linear-gradient(90deg, transparent, rgba(243,196,109,0.94), rgba(154,36,28,0.74), transparent);
      transform-origin: left center;
      animation: pressureThread 7.2s ease-in-out infinite;
      opacity: 0.72;
    }

    .drama-thread.is-second {
      top: 21%;
      animation-delay: -2.4s;
      opacity: 0.48;
    }

    .drama-thread.is-third {
      top: 31%;
      animation-delay: -4.8s;
      opacity: 0.36;
    }

    .drama-route-labels {
      position: absolute;
      inset: 16px 18px auto 18px;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: rgba(255,244,214,0.72);
      font-size: 12px;
      font-weight: 700;
    }

    .drama-route-labels span {
      border: 1px solid rgba(255,236,188,0.18);
      border-radius: 999px;
      padding: 4px 8px;
      background: rgba(9,13,19,0.36);
      backdrop-filter: blur(4px);
    }

    .stage.is-prologue-active .drama-thread,
    .stage.is-prologue-active .drama-route-labels,
    .stage.is-prologue-active .drama-progress {
      display: none;
    }

    .drama-progress {
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 18px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }

    .drama-step {
      height: 4px;
      border-radius: 999px;
      background: rgba(255,244,214,0.16);
      overflow: hidden;
    }

    .drama-step span {
      display: block;
      width: 26%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #f3c46d, #9a241c);
      transition: width 520ms ease;
    }

    .scene-world[data-drama-phase="meeting-threshold"] .drama-step span { width: 48%; }
    .scene-world[data-drama-phase="fiscal-pressure"] .drama-step span { width: 68%; }
    .scene-world[data-drama-phase="livelihood-counter"] .drama-step span { width: 82%; }
    .scene-world[data-drama-phase="power-shadow"] .drama-step span { width: 100%; }

    @keyframes pressureThread {
      0% { transform: scaleX(0.18) translateX(-8%); opacity: 0; }
      18% { opacity: 0.72; }
      58% { transform: scaleX(0.88) translateX(5%); opacity: 0.86; }
      100% { transform: scaleX(1) translateX(12%); opacity: 0; }
    }

    .debate-hud {
      position: absolute;
      left: 16px;
      right: 16px;
      bottom: 16px;
      z-index: 8;
      display: grid;
      pointer-events: none;
    }

    .scene-caption {
      display: grid;
      gap: 6px;
      max-width: min(520px, 72%);
      padding: 10px 12px;
      border: 1px solid rgba(255,236,188,0.28);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(9,13,19,0.58), rgba(9,13,19,0.24));
      box-shadow: 0 12px 36px rgba(0,0,0,0.22);
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
      font-size: 15px;
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
      font-size: clamp(15px, 1.5vw, 18px);
      line-height: 1.55;
    }

    .decision-dock {
      grid-column: 1;
      grid-row: 2;
      align-self: start;
      display: grid;
      gap: 12px;
      max-width: 700px;
      padding: 14px 16px;
      border: 1px solid rgba(255,236,188,0.22);
      border-radius: 8px;
      background: rgba(9,13,19,0.42);
      box-shadow: 0 14px 42px rgba(0,0,0,0.22);
      backdrop-filter: blur(8px);
    }

    .decision-dock.is-empty {
      display: none;
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

    .evidence-seal em {
      display: block;
      margin-top: 3px;
      color: rgba(255,244,214,0.56);
      font-size: 10px;
      font-style: normal;
      line-height: 1.2;
    }

    .lens-section {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid rgba(255,236,188,0.16);
      border-radius: 8px;
      background: rgba(255,244,214,0.055);
    }

    .lens-section-title {
      margin: 0;
      color: rgba(255,244,214,0.74);
      font-size: 12px;
      font-weight: 700;
    }

    .lens-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .lens-seal {
      display: grid;
      gap: 3px;
      min-height: 58px;
      text-align: left;
      border-color: rgba(243,196,109,0.34);
      background: rgba(31,79,82,0.36);
    }

    .lens-seal strong {
      color: #fff4d6;
      font-size: 13px;
      line-height: 1.25;
    }

    .lens-seal span {
      color: rgba(255,244,214,0.68);
      font-size: 11px;
      line-height: 1.35;
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

    .han-restored-basemap .region-fill {
      filter: url(#restoredPaper);
    }

    .han-restored-basemap .region-boundary {
      stroke-dasharray: 10 9;
    }

    .han-restored-basemap .gis-grid {
      opacity: 0.16;
      stroke-dasharray: 4 14;
    }

    .han-restored-basemap .han-river {
      fill: none;
      stroke: rgba(86,128,150,0.64);
      stroke-width: 5;
      stroke-linecap: round;
    }

    .han-restored-basemap .frontier-ridge {
      fill: none;
      stroke: rgba(255,236,188,0.24);
      stroke-width: 5;
      stroke-linecap: round;
      stroke-dasharray: 12 10;
    }

    .han-restored-basemap .region-label,
    .han-restored-basemap .route-label,
    .han-restored-basemap .map-source-label {
      font-weight: 700;
      paint-order: stroke;
      stroke: rgba(9,13,19,0.78);
      stroke-width: 5px;
      stroke-linejoin: round;
    }

    .map-feature-marker text {
      paint-order: stroke;
      stroke: rgba(9,13,19,0.74);
      stroke-width: 5px;
      stroke-linejoin: round;
    }

    .stage.is-prologue-active .map-feature-marker text {
      font-size: 18px;
      opacity: 0.82;
    }

    .pressure-route {
      stroke-dasharray: 18 18;
      animation: routeMarch 3.8s linear infinite;
    }

    .capital-pulse,
    .resource-pulse {
      transform-origin: center;
      animation: mapPulse 2.8s ease-in-out infinite;
    }

    .resource-pulse.is-frontier { animation-delay: -0.8s; }
    .resource-pulse.is-transport { animation-delay: -1.6s; }

    .court-threshold-wash {
      opacity: 0;
      transition: opacity 560ms ease;
    }

    .scene-world[data-drama-phase="meeting-threshold"] .court-threshold-wash,
    .scene-world[data-drama-phase="fiscal-pressure"] .court-threshold-wash,
    .scene-world[data-drama-phase="livelihood-counter"] .court-threshold-wash,
    .scene-world[data-drama-phase="power-shadow"] .court-threshold-wash {
      opacity: 0.68;
    }

    @keyframes routeMarch {
      to { stroke-dashoffset: -72; }
    }

    @keyframes mapPulse {
      0%, 100% { opacity: 0.46; transform: scale(0.92); }
      50% { opacity: 0.92; transform: scale(1.08); }
    }


    .chapter-map-scrim {
      position: fixed;
      inset: 0;
      z-index: 40;
      background: rgba(3, 6, 10, 0.5);
      opacity: 0;
      pointer-events: none;
      transition: opacity 260ms ease;
    }

    .chapter-map-scrim.is-open {
      opacity: 1;
      pointer-events: auto;
    }

    .chapter-map-panel {
      position: fixed;
      inset: 72px clamp(16px, 4vw, 48px) 58px clamp(16px, 4vw, 48px);
      z-index: 45;
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
      gap: 16px;
      padding: 16px;
      border: 1px solid rgba(255,236,188,0.28);
      border-radius: 8px;
      background: rgba(9,13,19,0.9);
      box-shadow: 0 24px 80px rgba(0,0,0,0.48);
      backdrop-filter: blur(14px);
      opacity: 0;
      transform: translateY(22px);
      pointer-events: none;
      transition: opacity 260ms ease, transform 320ms ease;
    }

    .chapter-map-panel.is-open {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }

    .chapter-map-head {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid rgba(255,236,188,0.16);
      padding-bottom: 10px;
    }

    .chapter-map-title {
      margin: 0;
      color: #fff4d6;
      font-size: 18px;
    }

    .chapter-grid {
      min-height: 0;
      overflow: auto;
      display: grid;
      gap: 12px;
      padding-right: 4px;
    }

    .juan-band {
      display: grid;
      gap: 8px;
    }

    .juan-title {
      color: rgba(255,244,214,0.72);
      font-size: 12px;
    }

    .chapter-node-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(142px, 1fr));
      gap: 8px;
    }

    .chapter-node {
      min-height: 94px;
      text-align: left;
      display: grid;
      align-content: start;
      gap: 5px;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid rgba(255,236,188,0.18);
      background: rgba(255,244,214,0.06);
      color: #fff4d6;
      cursor: pointer;
    }

    .chapter-node.is-active {
      border-color: rgba(243,196,109,0.82);
      background: rgba(243,196,109,0.14);
    }

    .chapter-node strong {
      font-size: 13px;
      line-height: 1.35;
    }

    .chapter-node span {
      color: rgba(255,244,214,0.68);
      font-size: 12px;
      line-height: 1.45;
    }

    .chapter-detail {
      min-height: 0;
      overflow: auto;
      display: grid;
      align-content: start;
      gap: 12px;
      padding: 12px;
      border-left: 1px solid rgba(255,236,188,0.16);
    }

    .chapter-detail h3 {
      margin: 0;
      color: #fff4d6;
      font-size: 22px;
    }

    .chapter-conflict {
      margin: 0;
      color: #f3c46d;
      line-height: 1.6;
      font-size: 16px;
    }

    .chapter-map-close {
      width: 34px;
      height: 34px;
      display: inline-grid;
      place-items: center;
      border-radius: 8px;
      border: 1px solid rgba(255,236,188,0.28);
      background: rgba(255,244,214,0.08);
      color: #fff4d6;
      cursor: pointer;
    }

    .evidence-scrim {
      position: fixed;
      inset: 0;
      z-index: 50;
      background: rgba(3, 6, 10, 0.44);
      opacity: 0;
      pointer-events: none;
      transition: opacity 260ms ease;
    }

    .evidence-scrim.is-open {
      opacity: 1;
      pointer-events: auto;
    }

    .evidence-ribbon {
      position: fixed;
      top: 84px;
      right: clamp(16px, 4vw, 48px);
      bottom: 72px;
      z-index: 60;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 12px;
      width: min(520px, calc(100vw - 32px));
      overflow: hidden;
      padding: 14px;
      border: 1px solid rgba(255,236,188,0.28);
      border-radius: 8px;
      background: rgba(9,13,19,0.9);
      box-shadow: 0 24px 80px rgba(0,0,0,0.48);
      backdrop-filter: blur(14px);
      opacity: 0;
      transform: translateX(calc(100% + 64px));
      transition: opacity 260ms ease, transform 360ms ease;
      pointer-events: none;
    }

    .evidence-ribbon.is-open {
      opacity: 1;
      transform: translateX(0);
      pointer-events: auto;
    }

    .evidence-panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(255,236,188,0.16);
    }

    .evidence-panel-title {
      margin: 0;
      color: #fff4d6;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .evidence-close {
      width: 34px;
      height: 34px;
      display: inline-grid;
      place-items: center;
      border-radius: 8px;
      border: 1px solid rgba(255,236,188,0.28);
      background: rgba(255,244,214,0.08);
      color: #fff4d6;
      cursor: pointer;
    }

    .evidence-list {
      display: grid;
      align-content: start;
      gap: 12px;
      min-height: 0;
      overflow: auto;
      padding-right: 4px;
    }

    .evidence-item {
      display: grid;
      gap: 4px;
      border-left: 3px solid rgba(243,196,109,0.7);
      padding-left: 10px;
    }

    .evidence-item.is-lens {
      border-left-color: rgba(100,196,187,0.9);
      background: rgba(100,196,187,0.06);
      padding: 10px 10px 10px 12px;
      border-radius: 8px;
    }

    .evidence-boundary {
      display: inline-flex;
      width: fit-content;
      border: 1px solid rgba(100,196,187,0.34);
      border-radius: 999px;
      padding: 2px 7px;
      color: #b7fff4;
      font-size: 11px;
      font-weight: 700;
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

    .stance-trajectory-panel {
      max-height: 174px;
      margin-bottom: 10px;
      padding: 12px;
      overflow: auto;
      border: 1px solid rgba(255,236,188,0.18);
      border-radius: 6px;
      color: rgba(255,244,214,0.72);
      background: rgba(9,13,19,0.36);
      font-size: 12px;
      line-height: 1.55;
    }

    .stance-trajectory-panel strong {
      display: block;
      margin-bottom: 6px;
      color: #ffe7b0;
      font-size: 13px;
    }

    .stance-trajectory-panel ol {
      display: grid;
      gap: 5px;
      margin: 0;
      padding-left: 18px;
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


    @media (max-width: 780px) {
      .chapter-map-panel {
        inset: 68px 10px 18px 10px;
        grid-template-columns: 1fr;
        overflow: auto;
      }

      .chapter-map-head {
        position: sticky;
        top: 0;
        z-index: 2;
        background: rgba(9,13,19,0.94);
      }

      .chapter-detail {
        border-left: 0;
        border-top: 1px solid rgba(255,236,188,0.16);
        padding: 12px 0 0;
      }

      .chapter-node-grid {
        grid-template-columns: 1fr;
      }

      .lens-grid {
        grid-template-columns: 1fr;
      }
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

      .story-panel,
      .scene-world,
      .decision-dock {
        grid-column: auto;
        grid-row: auto;
      }

      .story-panel {
        order: 1;
      }

      .scene-world {
        order: 2;
      }

      .decision-dock {
        order: 3;
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

      .stage.is-prologue-active .scene-shell {
        padding: 94px 0 0;
      }

      .stage.is-prologue-active .story-panel {
        left: 16px;
        right: 16px;
        bottom: 22px;
        width: auto;
      }

      .stage.is-prologue-active .scene-world {
        min-height: calc(100vh - 94px);
      }

      .pressure-director-panel {
        top: 104px;
        left: 12px;
        right: 12px;
        width: auto;
        max-height: 42vh;
        overflow: auto;
        padding: 12px;
      }

      .standpoint-grid {
        grid-template-columns: 1fr;
      }

      .standpoint-card {
        min-height: 92px;
      }

      .stage.is-prologue-active .scene-title {
        font-size: 32px;
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

      .drama-route-labels {
        inset: 12px 10px auto 10px;
        font-size: 11px;
      }

      .debate-hud {
        left: 10px;
        right: 10px;
        bottom: 10px;
      }

      .scene-caption {
        max-width: 100%;
        padding: 11px;
      }

      .scene-caption .debate-meta {
        font-size: 11px;
      }

      .scene-caption .debate-line {
        font-size: 14px;
        line-height: 1.45;
      }

      .evidence-ribbon {
        top: 72px;
        right: 10px;
        bottom: 20px;
        left: 10px;
        width: auto;
        transform: translateY(calc(100% + 48px));
      }

      .evidence-ribbon.is-open {
        transform: translateY(0);
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
          <button id="chapterMapToggle" class="ghost" type="button">诸篇争锋</button>
          <button id="rewindScene" class="ghost" type="button">回看</button>
        </div>
      </article>

      <section class="scene-world" aria-label="盐铁会议沉浸式场景">
        <div id="debateHud" class="debate-hud" aria-live="polite"></div>
        <div id="courtPressureOpening" class="court-pressure-opening" data-drama-phase="map-pressure" aria-hidden="true">
          <div class="drama-thread"></div>
          <div class="drama-thread is-second"></div>
          <div class="drama-thread is-third"></div>
          <div class="drama-route-labels">
            <span>边塞</span>
            <span>盐铁</span>
            <span>均输</span>
            <span>长安</span>
          </div>
          <p class="prologue-map-note">开源 GIS 方案兼容的汉昭帝时期复原叙事地图；本地矢量层绘制，不伪装成精确测绘边界。</p>
          <div id="pressureDirectorPanel" class="pressure-director-panel" aria-live="polite"></div>
          <div class="drama-progress" aria-hidden="true">
            <div class="drama-step"><span></span></div>
            <div class="drama-step"><span></span></div>
            <div class="drama-step"><span></span></div>
            <div class="drama-step"><span></span></div>
          </div>
        </div>
        <div id="mapScene" class="map-layer is-active" data-scene-layer="map">
          <svg id="hanMapScene" viewBox="0 0 1000 680" role="img" aria-label="动态汉代版图"></svg>
        </div>
        <div id="courtScene" class="court-layer" data-scene-layer="court">
          <svg id="courtSvg" viewBox="0 0 1000 680" role="img" aria-label="朝堂压力场与辩论"></svg>
        </div>
        <div id="networkScene" class="network-layer" data-scene-layer="network">
          <svg id="powerNetworkScene" viewBox="0 0 1000 680" role="img" aria-label="权力关系网"></svg>
        </div>
        <div id="judgmentScene" class="judgment-layer" data-scene-layer="judgment">
          <svg id="judgmentSvg" viewBox="0 0 1000 680" role="img" aria-label="退朝案牍收束场景"></svg>
          <form class="judgment-form" id="judgmentForm">
            <div id="stanceTrajectoryPanel" class="stance-trajectory-panel" aria-label="观点变化图"></div>
            <textarea id="reflectionInput" placeholder="写下你的退朝案牍：当边费、与民争利和权力阴影同时成立时，制度应废止、修正，还是保留并审计？"></textarea>
            <button class="primary" type="submit">钤下案牍</button>
            <div id="judgmentOutput" class="judgment-output">你的退朝案牍不会写入历史证据包。</div>
          </form>
        </div>
      </section>
      <aside id="decisionDock" class="decision-dock is-empty" aria-label="思想判断区"></aside>
    </section>

    <div id="chapterMapScrim" class="chapter-map-scrim" aria-hidden="true"></div>
    <aside id="chapterMapPanel" class="chapter-map-panel" aria-label="诸篇争锋"></aside>
    <div id="evidenceScrim" class="evidence-scrim" aria-hidden="true"></div>
    <aside id="evidenceRibbon" class="evidence-ribbon" aria-label="关键证据"></aside>
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
      visitedChapters: new Set(),
      visitedLensIds: new Set(),
      activeChapterIndex: 0,
      chapterMapOpen: false,
      audio: null,
      soundEnabled: false,
      dramaPhase: "map-pressure",
      sceneProgress: 0,
      animationTick: 0,
      experiencePhase: "pressure_entry",
      pressureIndex: 0,
      userStandpoint: null,
      stanceTrajectory: []
    };

    const pressureTimeline = [
      {
        key: "wudi-afterglow",
        time: "公元前 87 年后",
        title: "武帝余响还在运转",
        narration: "战争、转运、盐铁和平准没有随武帝去世而停止。财政机器继续转动，会议尚未开始，压力已经存在。",
        mapFocus: "feature_changan",
        pressure: { frontier: 58, treasury: 72, livelihood: 38, merchants: 48, power: 44 },
        evidence: ["ev:src_shiji_pingzhun:juan030:salt_iron_offices:3344bbcc"],
        support: 95
      },
      {
        key: "frontier-report",
        time: "北边急报",
        title: "边防压力向长安逼近",
        narration: "北边军费与粮草不是抽象数字。边塞每一次吃紧，都会把府库、运输和征敛一起推向朝堂。",
        mapFocus: "feature_northern_frontier",
        pressure: { frontier: 92, treasury: 80, livelihood: 42, merchants: 46, power: 58 },
        evidence: ["ev:src_shiji_pingzhun:juan030:frontier_supply:66778899"],
        support: 95
      },
      {
        key: "treasury-tight",
        time: "府库吃紧",
        title: "国家先感到缺钱",
        narration: "财政官看到的是府库、边费和制度调度。若国家先失去筹措能力，道德理想也会失去执行边界。",
        mapFocus: "feature_equal_transport_routes",
        pressure: { frontier: 86, treasury: 94, livelihood: 48, merchants: 54, power: 64 },
        evidence: ["ev:src_shiji_pingzhun:juan030:sang_equal_transport:5e6f7081"],
        support: 95
      },
      {
        key: "salt-iron-office",
        time: "盐铁入官",
        title: "山海之利被纳入制度",
        narration: "盐铁资源从地方、商贾和山海之间被拉入国家网络。它可能抑制豪强，也可能让官府更深地进入民生日用。",
        mapFocus: "feature_salt_iron_resources",
        pressure: { frontier: 74, treasury: 88, livelihood: 66, merchants: 82, power: 70 },
        evidence: ["ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d"],
        support: 80
      },
      {
        key: "livelihood-burden",
        time: "民户承压",
        title: "百姓开始感到制度的重量",
        narration: "当政策落到盐价、铁器、徭役和农桑上，财政技术就变成了生活经验。民间痛感开始反问国家能力的边界。",
        mapFocus: "feature_jincheng",
        pressure: { frontier: 66, treasury: 76, livelihood: 92, merchants: 72, power: 68 },
        evidence: ["ev:src_yantielun:juan01_benyi:literati_abolish:0a1b2c3d"],
        support: 80
      },
      {
        key: "summon-court",
        time: "始元六年",
        title: "未央宫召议",
        narration: "朝廷问民所疾苦。会议即将开始，但每个人带进朝堂的不是观点本身，而是自己承受的压力。",
        mapFocus: "feature_changan",
        pressure: { frontier: 78, treasury: 82, livelihood: 86, merchants: 68, power: 88 },
        evidence: ["ev:src_hanshu_zhaodi:juan007:meeting_edict:ccddeeff"],
        support: 95
      }
    ];

    const standpointRoles = [
      {
        id: "fiscal-official",
        label: "国家财政官",
        pressureFocus: "府库",
        initialLeaning: 28,
        innerVoice: "若府库空虚，边防与赈济都只是愿望。"
      },
      {
        id: "frontier-general",
        label: "边疆将军",
        pressureFocus: "边防",
        initialLeaning: 34,
        innerVoice: "粮草一断，城塞先替朝堂承受后果。"
      },
      {
        id: "local-household",
        label: "地方百姓",
        pressureFocus: "民生",
        initialLeaning: 74,
        innerVoice: "制度说是为国，落到日用便是负担。"
      },
      {
        id: "salt-iron-merchant",
        label: "盐铁商人",
        pressureFocus: "商贾",
        initialLeaning: 62,
        innerVoice: "官府入市，豪强未必消失，生计却先被改写。"
      }
    ];

    const experienceDirector = {
      phases: ["pressure_entry", "standpoint_choice", "court_debate", "power_reveal", "after_echo", "judgment"],
      pressureLabels: {
        frontier: "边防",
        treasury: "府库",
        livelihood: "民生",
        merchants: "商贾",
        power: "权力"
      },
      supportLabel(value) {
        if (value >= 90) return "核心史料直接支持";
        if (value >= 75) return "史料加策展推断";
        return "思想透镜解释";
      },
      phaseForScene(scene) {
        if (state.experiencePhase === "pressure_entry" || state.experiencePhase === "standpoint_choice") return state.experiencePhase;
        if (scene.key === "judgment") return "judgment";
        if (scene.visualMode === "power-shadow") return "power_reveal";
        if (scene.key === "network") return "power_reveal";
        return "court_debate";
      },
      recordTrajectory(point) {
        const index = state.stanceTrajectory.findIndex(item => item.stage === point.stage);
        if (index >= 0) {
          state.stanceTrajectory[index] = point;
        } else {
          state.stanceTrajectory.push(point);
        }
      }
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
            "line": "辩论仍在继续，但谁能决定辩论的边界，已经在发声之外。",
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

    const chapterConflictMap = [
      {
            "chapterNumber": 1,
            "juan": "卷一",
            "title": "本议第一",
            "slug": "benyi",
            "actKey": "act-livelihood",
            "issue": "monopoly",
            "conflict": "盐铁酒榷均输是救边费，还是与民争利？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "制度必须供给边防与府库。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "治道应先抑末利、开仁义。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_benyi:meeting_opening:a1b2c3d4"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001",
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011"
            ],
            "visualCue": "monopoly"
      },
      {
            "chapterNumber": 2,
            "juan": "卷一",
            "title": "力耕第二",
            "slug": "ligeng",
            "actKey": "act-livelihood",
            "issue": "agriculture",
            "conflict": "农桑为本与国家调剂如何共存？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "储积调剂可以救乏绝。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "务本力耕才是民生根基。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_jingeng:agriculture_base:88990011"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_tengwen:tengwen01:constant_livelihood:aa110009",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "agriculture"
      },
      {
            "chapterNumber": 3,
            "juan": "卷一",
            "title": "通有第三",
            "slug": "tongyou",
            "actKey": "act-statecraft",
            "issue": "market",
            "conflict": "城市商路是流通之利，还是逐末之源？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "通有无可使货物流转。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "商工过盛会夺农桑之本。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_jingeng:market_cities:bb11cc22"
            ],
            "philosophyLens": [
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004",
                  "ev:src_xunzi_wangzhi:wangzhi:market_tax_light:aa220008"
            ],
            "visualCue": "market"
      },
      {
            "chapterNumber": 4,
            "juan": "卷一",
            "title": "错币第四",
            "slug": "cuobi",
            "actKey": "act-statecraft",
            "issue": "currency",
            "conflict": "货币与物价应由国家调节，还是顺民间自通？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "轻重调剂可以平缓急。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "错币扰民会放大贫富不均。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_cuobi:chapter_conflict:71e30b87"
            ],
            "philosophyLens": [
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011",
                  "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017"
            ],
            "visualCue": "currency"
      },
      {
            "chapterNumber": 5,
            "juan": "卷一",
            "title": "禁耕第五",
            "slug": "jingeng",
            "actKey": "act-power",
            "issue": "power",
            "conflict": "国家垄断能防豪强，还是制造更大的官府强权？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "山海之利若归豪民，会成私强。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "权利深处未必在山海，也可能在朝廷。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_jingeng:state_control_prevents_cliques:1122aabb"
            ],
            "philosophyLens": [
                  "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "power"
      },
      {
            "chapterNumber": 6,
            "juan": "卷一",
            "title": "复古第六",
            "slug": "fugu",
            "actKey": "act-statecraft",
            "issue": "reform",
            "conflict": "制度弊病应修令，还是回到古法？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "盐铁令意在总一资源。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "古法之本在薄利安民。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan01_fugu:chapter_conflict:edd2cc73"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016"
            ],
            "visualCue": "reform"
      },
      {
            "chapterNumber": 7,
            "juan": "卷二",
            "title": "非鞅第七",
            "slug": "feiyang",
            "actKey": "act-yili",
            "issue": "legalism",
            "conflict": "商鞅式富强能否成为汉政范式？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "法度严明可富国强兵。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "以刑利成强，未必合乎王道。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_feiyang:chapter_conflict:4702f508"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ],
            "visualCue": "legalism"
      },
      {
            "chapterNumber": 8,
            "juan": "卷二",
            "title": "晁错第八",
            "slug": "chaocuo",
            "actKey": "act-power",
            "issue": "faction",
            "conflict": "削藩与忠谋为何会走向政治牺牲？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "为国深谋可制诸侯。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "权力局中，忠谋也可能成祸端。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_chaocuo:chapter_conflict:154f63e3"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002",
                  "ev:src_xunzi_wangzhi:wangzhi:boat_water:aa220007"
            ],
            "visualCue": "faction"
      },
      {
            "chapterNumber": 9,
            "juan": "卷二",
            "title": "刺权第九",
            "slug": "ciquan",
            "actKey": "act-power",
            "issue": "power",
            "conflict": "权利归上能强国，还是使朝廷失衡？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "统山海则国家不为豪强所分。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "权太集中会反噬公议。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_ciquan:chapter_conflict:d6d59555"
            ],
            "philosophyLens": [
                  "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "power"
      },
      {
            "chapterNumber": 10,
            "juan": "卷二",
            "title": "刺复第十",
            "slug": "cifu",
            "actKey": "act-power",
            "issue": "burden",
            "conflict": "在局者的财政忧惧能否压过旁观者的德义批评？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "当局者知负载之劳。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "忧国不能取消民间痛感。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_cifu:chapter_conflict:db419abd"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001",
                  "ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003"
            ],
            "visualCue": "burden"
      },
      {
            "chapterNumber": 11,
            "juan": "卷二",
            "title": "论儒第十一",
            "slug": "lunru",
            "actKey": "act-yili",
            "issue": "values",
            "conflict": "儒者能治世，还是只会称古？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "空言德义未必能救政务。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "德义教化正是治世根本。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_lunru:chapter_conflict:d3a320b3"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001",
                  "ev:src_mengzi_gaozishang:gaozi10:choose_righteousness:aa220005",
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013"
            ],
            "visualCue": "values"
      },
      {
            "chapterNumber": 12,
            "juan": "卷二",
            "title": "忧边第十二",
            "slug": "youbian",
            "actKey": "act-fiscal",
            "issue": "frontier",
            "conflict": "忧边应先筹兵食，还是先息民力？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "边患不除，国家不安。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "长久军费会困穷百姓。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan02_youbian:chapter_conflict:62cc2317"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "frontier"
      },
      {
            "chapterNumber": 13,
            "juan": "卷三",
            "title": "园池第十三",
            "slug": "yuanchi",
            "actKey": "act-fiscal",
            "issue": "resource",
            "conflict": "园池山海是公共财政，还是奢侈占夺？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "总山海可助贡赋。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "苑囿奢用会离民生越来越远。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan03_yuanchi:chapter_conflict:b271ef45"
            ],
            "philosophyLens": [
                  "ev:src_liji_wangzhi:wangzhi:labor_limit:aa220015",
                  "ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003"
            ],
            "visualCue": "resource"
      },
      {
            "chapterNumber": 14,
            "juan": "卷三",
            "title": "轻重第十四",
            "slug": "qingzhong",
            "actKey": "act-statecraft",
            "issue": "price",
            "conflict": "轻重之术能平物价，还是让官府入市逐利？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "轻重调节可通财货。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "官府逐利会改变政德。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan03_qingzhong:chapter_conflict:fa483d8c"
            ],
            "philosophyLens": [
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004",
                  "ev:src_xunzi_wangzhi:wangzhi:market_tax_light:aa220008"
            ],
            "visualCue": "price"
      },
      {
            "chapterNumber": 15,
            "juan": "卷三",
            "title": "未通第十五",
            "slug": "weitong",
            "actKey": "act-livelihood",
            "issue": "transport",
            "conflict": "交通未通造成贫苦，国家转运是否必要？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "转运能济区域不足。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "民间劳苦不应只被当成物流问题。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan03_weitong:chapter_conflict:0608353b"
            ],
            "philosophyLens": [
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004",
                  "ev:src_liji_wangzhi:wangzhi:labor_limit:aa220015"
            ],
            "visualCue": "transport"
      },
      {
            "chapterNumber": 16,
            "juan": "卷四",
            "title": "地广第十六",
            "slug": "diguang",
            "actKey": "act-fiscal",
            "issue": "frontier",
            "conflict": "天下地广，应调远近，还是减边地扰动？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "边地同为臣民，国家应调剂。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "远方寒苦不能被财政一笔抹平。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan04_diguang:chapter_conflict:88cc9d6d"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "frontier"
      },
      {
            "chapterNumber": 17,
            "juan": "卷四",
            "title": "贫富第十七",
            "slug": "pinfu",
            "actKey": "act-livelihood",
            "issue": "wealth",
            "conflict": "贫富来自勤俭，还是来自制度位置？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "俭节量入可保家。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "贫富差距不能只归因个人。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan04_pinfu:chapter_conflict:ace6a215"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003",
                  "ev:src_mengzi_tengwen:tengwen01:constant_livelihood:aa110009"
            ],
            "visualCue": "wealth"
      },
      {
            "chapterNumber": 18,
            "juan": "卷四",
            "title": "毁学第十八",
            "slug": "huixue",
            "actKey": "act-yili",
            "issue": "learning",
            "conflict": "学术批评是空谈，还是纠偏权力的必要声音？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "怀枉言正是士风之弊。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "无学术批评，权力更难自省。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan04_huixue:chapter_conflict:1e1fb1a6"
            ],
            "philosophyLens": [
                  "ev:src_guanzi_quanxiu:quanxiu:long_term_teaching:aa220010",
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013"
            ],
            "visualCue": "learning"
      },
      {
            "chapterNumber": 19,
            "juan": "卷四",
            "title": "褒贤第十九",
            "slug": "baoxian",
            "actKey": "act-yili",
            "issue": "merit",
            "conflict": "贤者应以功名衡量，还是以德义自守？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "纵横强国亦可建功。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "功名不能替代德义标准。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan04_baoxian:chapter_conflict:0d83a973"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ],
            "visualCue": "merit"
      },
      {
            "chapterNumber": 20,
            "juan": "卷五",
            "title": "相刺第二十",
            "slug": "xiangci",
            "actKey": "act-yili",
            "issue": "critique",
            "conflict": "儒生批政是离本，还是公共议论的开始？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "弃耕谈学未必有实功。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "议政本身也是士人的责任。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_xiangci:chapter_conflict:be9c4edf"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003",
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012"
            ],
            "visualCue": "critique"
      },
      {
            "chapterNumber": 21,
            "juan": "卷五",
            "title": "殊路第二十一",
            "slug": "shulu",
            "actKey": "act-yili",
            "issue": "paths",
            "conflict": "同出儒门为何走向不同政治道路？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "才具应落实在政事。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "道路不同不等于价值无用。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_shulu:chapter_conflict:fa045567"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001"
            ],
            "visualCue": "paths"
      },
      {
            "chapterNumber": 22,
            "juan": "卷五",
            "title": "讼贤第二十二",
            "slug": "songxian",
            "actKey": "act-yili",
            "issue": "virtue",
            "conflict": "贤能应刚强有为，还是守正不阿？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "矜己伐能会害事。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "折柔之间仍要守义。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_songxian:chapter_conflict:287558dd"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_gaozishang:gaozi10:choose_righteousness:aa220005",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "virtue"
      },
      {
            "chapterNumber": 23,
            "juan": "卷五",
            "title": "遵道第二十三",
            "slug": "zundao",
            "actKey": "act-statecraft",
            "issue": "dao",
            "conflict": "遵道是守古言，还是把道落到当世？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "政务不能止于高言。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "无道则现实只剩权术。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_zundao:chapter_conflict:317552c8"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008"
            ],
            "visualCue": "dao"
      },
      {
            "chapterNumber": 24,
            "juan": "卷五",
            "title": "论诽第二十四",
            "slug": "lunfei",
            "actKey": "act-power",
            "issue": "speech",
            "conflict": "批评当政是诽谤，还是议政权利？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "称古訾今会扰乱政令。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "不许论诽，朝廷更难听见疾苦。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_lunfei:chapter_conflict:38a9a473"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003",
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013"
            ],
            "visualCue": "speech"
      },
      {
            "chapterNumber": 25,
            "juan": "卷五",
            "title": "孝养第二十五",
            "slug": "xiaoyang",
            "actKey": "act-livelihood",
            "issue": "family",
            "conflict": "孝养重在物质供养，还是敬与礼？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "衣食供养不可缺。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "孝不止是资源问题。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_xiaoyang:chapter_conflict:cf8d3a59"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_lunyu_xueer:xueer01:govern_with_time:aa110007"
            ],
            "visualCue": "family"
      },
      {
            "chapterNumber": 26,
            "juan": "卷五",
            "title": "刺议第二十六",
            "slug": "ciyi",
            "actKey": "act-power",
            "issue": "deliberation",
            "conflict": "朝廷应纳众议，还是防止空言误政？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "多闻多见可广策。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "议论若不负责任也会误国。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_ciyi:chapter_conflict:d01622d1"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003",
                  "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017"
            ],
            "visualCue": "deliberation"
      },
      {
            "chapterNumber": 27,
            "juan": "卷五",
            "title": "利议第二十七",
            "slug": "liyi",
            "actKey": "act-power",
            "issue": "strategy",
            "conflict": "求奇计安边，是否会把议论拉回功利？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "边境未安，必须求可行策。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "只问利策会压扁德义问题。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_liyi:chapter_conflict:61fc0944"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "strategy"
      },
      {
            "chapterNumber": 28,
            "juan": "卷五",
            "title": "国疾第二十八",
            "slug": "guoji",
            "actKey": "act-yili",
            "issue": "illness",
            "conflict": "国家之疾在无贤，还是在制度不听贤？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "贤士不用是国家羞耻。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "贤言若不能落地也难救病。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan05_guoji:chapter_conflict:e989c27c"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_wangzhi:wangzhi:boat_water:aa220007",
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011"
            ],
            "visualCue": "illness"
      },
      {
            "chapterNumber": 29,
            "juan": "卷六",
            "title": "散不足第二十九",
            "slug": "sanbuzu",
            "actKey": "act-livelihood",
            "issue": "frugality",
            "conflict": "奢费不足应开财源，还是节上以足下？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "财用不足须筹措。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "上层奢费才是民困之源。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_sanbuzu:chapter_conflict:bfec3e04"
            ],
            "philosophyLens": [
                  "ev:src_mozi_feile:feile01:three_harms:aa220014",
                  "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016"
            ],
            "visualCue": "frugality"
      },
      {
            "chapterNumber": 30,
            "juan": "卷六",
            "title": "救匮第三十",
            "slug": "jiukui",
            "actKey": "act-livelihood",
            "issue": "relief",
            "conflict": "救匮应靠国家财力，还是公卿节俭示范？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "财政可以救困乏。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "节俭率下才能止匮。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_jiukui:chapter_conflict:be30f275"
            ],
            "philosophyLens": [
                  "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016",
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001"
            ],
            "visualCue": "relief"
      },
      {
            "chapterNumber": 31,
            "juan": "卷六",
            "title": "箴石第三十一",
            "slug": "zhenshi",
            "actKey": "act-power",
            "issue": "admonition",
            "conflict": "激烈批评是药石，还是伤害朝堂秩序？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "言行可则才能治政。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "刺痛权力的言论也可能是箴石。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_zhenshi:chapter_conflict:c5cdbdf6"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003",
                  "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017"
            ],
            "visualCue": "admonition"
      },
      {
            "chapterNumber": 32,
            "juan": "卷六",
            "title": "除狭第三十二",
            "slug": "chuxia",
            "actKey": "act-power",
            "issue": "local",
            "conflict": "地方治理靠长吏专制，还是制度监督？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "郡守握权才能处置千里。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "权专而无监督会狭隘侵民。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_chuxia:chapter_conflict:17fcc6d6"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "local"
      },
      {
            "chapterNumber": 33,
            "juan": "卷六",
            "title": "疾贪第三十三",
            "slug": "jitan",
            "actKey": "act-power",
            "issue": "corruption",
            "conflict": "吏治之病在贪，还是在求取机制？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "贪吏侵渔百姓应严治。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "只责小吏不能遮蔽制度诱因。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_jitan:chapter_conflict:30f9be49"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012",
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011"
            ],
            "visualCue": "corruption"
      },
      {
            "chapterNumber": 34,
            "juan": "卷六",
            "title": "后刑第三十四",
            "slug": "houxing",
            "actKey": "act-power",
            "issue": "punishment",
            "conflict": "刑罚是治恶必要，还是德治失败的补丁？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "刑一恶可悦万民。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "依赖刑罚会削弱教化。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_houxing:chapter_conflict:2620c13c"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012",
                  "ev:src_liji_liyun:liyun:public_order:aa110010"
            ],
            "visualCue": "punishment"
      },
      {
            "chapterNumber": 35,
            "juan": "卷六",
            "title": "授时第三十五",
            "slug": "shoushi",
            "actKey": "act-statecraft",
            "issue": "time",
            "conflict": "贫困应归咎惰奢，还是看时令与机会？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "勤俭守时可免贫。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "治理要给民以合时之生路。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_shoushi:chapter_conflict:9a50b48c"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_xueer:xueer01:govern_with_time:aa110007",
                  "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008"
            ],
            "visualCue": "time"
      },
      {
            "chapterNumber": 36,
            "juan": "卷六",
            "title": "水旱第三十六",
            "slug": "shuihan",
            "actKey": "act-statecraft",
            "issue": "disaster",
            "conflict": "水旱灾异是天道，还是政治责任？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "灾荒有自然之数。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "政治仍要承担备荒救民。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan06_shuihan:chapter_conflict:d03b9a50"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "disaster"
      },
      {
            "chapterNumber": 37,
            "juan": "卷七",
            "title": "崇礼第三十七",
            "slug": "chongli",
            "actKey": "act-yili",
            "issue": "ritual",
            "conflict": "礼乐仪物是秩序象征，还是奢侈负担？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "礼仪可示威德与秩序。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "崇礼若成炫耀，会离民甚远。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_chongli:chapter_conflict:e7b8e2ac"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_xunzi_xiushen:xiushen:ritual_corrects_body:aa220009"
            ],
            "visualCue": "ritual"
      },
      {
            "chapterNumber": 38,
            "juan": "卷七",
            "title": "备胡第三十八",
            "slug": "beihu",
            "actKey": "act-fiscal",
            "issue": "frontier",
            "conflict": "面对匈奴，备战是否压倒仁义怀远？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "不备则边境受害。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "备胡不能无限征敛。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_beihu:chapter_conflict:4c55b53d"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "frontier"
      },
      {
            "chapterNumber": 39,
            "juan": "卷七",
            "title": "执务第三十九",
            "slug": "zhiwu",
            "actKey": "act-statecraft",
            "issue": "practice",
            "conflict": "当世急务能否取代上古理想？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "政务必须可执行。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "急务不应抹掉道义方向。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_zhiwu:chapter_conflict:f9bc9127"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004"
            ],
            "visualCue": "practice"
      },
      {
            "chapterNumber": 40,
            "juan": "卷七",
            "title": "能言第四十",
            "slug": "nengyan",
            "actKey": "act-statecraft",
            "issue": "speech",
            "conflict": "能言治乱者，是否必须能亲自行之？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "坐言不行不足治国。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "言说也能揭示政治盲点。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_nengyan:chapter_conflict:3bd58d49"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003",
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013"
            ],
            "visualCue": "speech"
      },
      {
            "chapterNumber": 41,
            "juan": "卷七",
            "title": "取下第四十一",
            "slug": "quxia",
            "actKey": "act-power",
            "issue": "people",
            "conflict": "取利于下是亏主，还是还利于民？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "利归下则县官无可为。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "取下太重则民无可生。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_quxia:chapter_conflict:b3f59835"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_jinxinxia:jinxin14:people_first:aa220004",
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011"
            ],
            "visualCue": "people"
      },
      {
            "chapterNumber": 42,
            "juan": "卷七",
            "title": "击之第四十二",
            "slug": "jizhi",
            "actKey": "act-fiscal",
            "issue": "war",
            "conflict": "击匈奴是主动安边，还是把财政推向战争？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "击之可困敌安边。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "用兵会继续加重民力。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan07_jizhi:chapter_conflict:859e3660"
            ],
            "philosophyLens": [
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006",
                  "ev:src_mozi_feile:feile01:three_harms:aa220014"
            ],
            "visualCue": "war"
      },
      {
            "chapterNumber": 43,
            "juan": "卷八",
            "title": "结和第四十三",
            "slug": "jiehe",
            "actKey": "act-fiscal",
            "issue": "diplomacy",
            "conflict": "和亲厚赂为何未能换来稳定？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "厚赂不一定改敌节。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "武折之外仍要考量德怀。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_jiehe:chapter_conflict:f24f1d0f"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_jinxinxia:jinxin14:people_first:aa220004",
                  "ev:src_liji_liyun:liyun:public_order:aa110010"
            ],
            "visualCue": "diplomacy"
      },
      {
            "chapterNumber": 44,
            "juan": "卷八",
            "title": "诛秦第四十四",
            "slug": "zhuqin",
            "actKey": "act-yili",
            "issue": "qin",
            "conflict": "秦制之强可取，还是其亡足戒？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "强国之术能扩地立威。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "秦亡说明强制有极限。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_zhuqin:chapter_conflict:b8a1140b"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_xunzi_wangzhi:wangzhi:boat_water:aa220007"
            ],
            "visualCue": "qin"
      },
      {
            "chapterNumber": 45,
            "juan": "卷八",
            "title": "伐功第四十五",
            "slug": "fagong",
            "actKey": "act-fiscal",
            "issue": "merit",
            "conflict": "武功开边是功业，还是成本被遮蔽？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "伐功可显国家威力。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "功业背后有民力代价。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_fagong:chapter_conflict:e293d79c"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ],
            "visualCue": "merit"
      },
      {
            "chapterNumber": 46,
            "juan": "卷八",
            "title": "西域第四十六",
            "slug": "xiyu",
            "actKey": "act-fiscal",
            "issue": "xiyu",
            "conflict": "经营西域是战略纵深，还是远方财政负担？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "通西域可制匈奴。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "远略会拉长供给与役使。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_xiyu:chapter_conflict:1a2e4eba"
            ],
            "philosophyLens": [
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006",
                  "ev:src_liji_wangzhi:wangzhi:labor_limit:aa220015"
            ],
            "visualCue": "xiyu"
      },
      {
            "chapterNumber": 47,
            "juan": "卷八",
            "title": "世务第四十七",
            "slug": "shiwu",
            "actKey": "act-statecraft",
            "issue": "now",
            "conflict": "世务之急能否压倒椎车古语？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "当世病痛必须当世治理。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "急务若只重权利会失道。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_shiwu:chapter_conflict:b932a66f"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004"
            ],
            "visualCue": "now"
      },
      {
            "chapterNumber": 48,
            "juan": "卷八",
            "title": "和亲第四十八",
            "slug": "heqin",
            "actKey": "act-fiscal",
            "issue": "peace",
            "conflict": "和亲与备战，哪一种更接近仁政？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "仁义也要城守器备。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "备战不应吞没怀远之道。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan08_heqin:chapter_conflict:660b7116"
            ],
            "philosophyLens": [
                  "ev:src_mengzi_jinxinxia:jinxin14:people_first:aa220004",
                  "ev:src_liji_liyun:liyun:public_order:aa110010"
            ],
            "visualCue": "peace"
      },
      {
            "chapterNumber": 49,
            "juan": "卷九",
            "title": "繇役第四十九",
            "slug": "yaoyi",
            "actKey": "act-livelihood",
            "issue": "labor",
            "conflict": "征伐与徭役是否必然相连？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "征不从者需举兵。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "徭役过重会伤民本。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_yaoyi:chapter_conflict:9caab5c5"
            ],
            "philosophyLens": [
                  "ev:src_liji_wangzhi:wangzhi:labor_limit:aa220015",
                  "ev:src_mozi_feile:feile01:three_harms:aa220014"
            ],
            "visualCue": "labor"
      },
      {
            "chapterNumber": 50,
            "juan": "卷九",
            "title": "险固第五十",
            "slug": "xiangu",
            "actKey": "act-fiscal",
            "issue": "defense",
            "conflict": "险固器备是安全根本，还是财政吞口？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "有备则能制敌。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "险固之费仍出自百姓。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_xiangu:chapter_conflict:68de2221"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001",
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006"
            ],
            "visualCue": "defense"
      },
      {
            "chapterNumber": 51,
            "juan": "卷九",
            "title": "论勇第五十一",
            "slug": "lunyong",
            "actKey": "act-fiscal",
            "issue": "courage",
            "conflict": "勇力靠个人胆气，还是靠器械制度？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "武备器械成就勇功。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "勇功叙事会遮蔽民生。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_lunyong:chapter_conflict:5b45eb09"
            ],
            "philosophyLens": [
                  "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ],
            "visualCue": "courage"
      },
      {
            "chapterNumber": 52,
            "juan": "卷九",
            "title": "论功第五十二",
            "slug": "lungong",
            "actKey": "act-fiscal",
            "issue": "achievement",
            "conflict": "功业衡量应看战果，还是看礼义秩序？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "匈奴无礼法，故不足畏。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "以功论政可能轻忽德义。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_lungong:chapter_conflict:cfb1a7de"
            ],
            "philosophyLens": [
                  "ev:src_liji_liyun:liyun:public_order:aa110010",
                  "ev:src_mengzi_gaozishang:gaozi10:choose_righteousness:aa220005"
            ],
            "visualCue": "achievement"
      },
      {
            "chapterNumber": 53,
            "juan": "卷九",
            "title": "论邹第五十三",
            "slug": "lunzou",
            "actKey": "act-yili",
            "issue": "cosmos",
            "conflict": "阴阳大论能解释政治，还是远离现实？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "宏阔理论可喻王公。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "远言若不合近事便成空论。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_lunzou:chapter_conflict:c3d2b4c3"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008",
                  "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016"
            ],
            "visualCue": "cosmos"
      },
      {
            "chapterNumber": 54,
            "juan": "卷九",
            "title": "论菑第五十四",
            "slug": "lunzai",
            "actKey": "act-statecraft",
            "issue": "disaster",
            "conflict": "灾异应作政治警讯，还是不可逐语迷信？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "灾异可以提醒政失。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "信灾异不能替代近事治理。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan09_lunzai:chapter_conflict:6a3e947b"
            ],
            "philosophyLens": [
                  "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008",
                  "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002"
            ],
            "visualCue": "disaster"
      },
      {
            "chapterNumber": 55,
            "juan": "卷十",
            "title": "刑德第五十五",
            "slug": "xingde",
            "actKey": "act-yili",
            "issue": "law",
            "conflict": "刑与德谁是治民根本？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "法令督奸，刑罚禁恶。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "刑不能替代德教。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_xingde:chapter_conflict:c177a5c9"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012",
                  "ev:src_liji_liyun:liyun:public_order:aa110010"
            ],
            "visualCue": "law"
      },
      {
            "chapterNumber": 56,
            "juan": "卷十",
            "title": "申韩第五十六",
            "slug": "shenhan",
            "actKey": "act-yili",
            "issue": "legalism",
            "conflict": "申韩法术是补政缺，还是伤王道？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "小缺可用法令防。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "法术过盛会压低礼义。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_shenhan:chapter_conflict:851016ec"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005"
            ],
            "visualCue": "legalism"
      },
      {
            "chapterNumber": 57,
            "juan": "卷十",
            "title": "周秦第五十七",
            "slug": "zhouqin",
            "actKey": "act-yili",
            "issue": "history",
            "conflict": "周礼与秦法，何者能解释汉代困境？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "秦法强制有现实效力。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "周礼提供秩序理想。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_zhouqin:chapter_conflict:f2a74bce"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_liji_liyun:liyun:public_order:aa110010"
            ],
            "visualCue": "history"
      },
      {
            "chapterNumber": 58,
            "juan": "卷十",
            "title": "诏圣第五十八",
            "slug": "zhaosheng",
            "actKey": "act-statecraft",
            "issue": "reform",
            "conflict": "圣王之法应守成，还是随世更制？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "法弊则更制。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "更制不能背离德信。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_zhaosheng:chapter_conflict:2f682d00"
            ],
            "philosophyLens": [
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016"
            ],
            "visualCue": "reform"
      },
      {
            "chapterNumber": 59,
            "juan": "卷十",
            "title": "大论第五十九",
            "slug": "dalun",
            "actKey": "act-statecraft",
            "issue": "summary",
            "conflict": "大论应归于务实，还是保留价值审判？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "治民如匠，需有法度工具。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "工具理性仍须接受价值审判。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_dalun:chapter_conflict:638ed1b2"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001",
                  "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005",
                  "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011"
            ],
            "visualCue": "summary"
      },
      {
            "chapterNumber": 60,
            "juan": "卷十",
            "title": "杂论第六十",
            "slug": "zalun",
            "actKey": "act-yili",
            "issue": "closure",
            "conflict": "全书终局是各有所出，还是仍可判其义利？",
            "voices": [
                  {
                        "side": "大夫一方",
                        "text": "诸论各有所出，权利有其理由。"
                  },
                  {
                        "side": "贤良文学",
                        "text": "上仁义与务权利仍需辨别。"
                  }
            ],
            "historicalEvidence": [
                  "ev:src_yantielun:juan10_zalun:chapter_conflict:6f36a7cb"
            ],
            "philosophyLens": [
                  "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001",
                  "ev:src_mengzi_jinxinxia:jinxin14:people_first:aa220004",
                  "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012"
            ],
            "visualCue": "closure"
      }
];

    const philosophyLensMeta = {
      "ev:src_lunyu_liren:liren04:yi_li_lens:aa110001": {
            "label": "义利之辨",
            "family": "义利",
            "note": "用义与利的价值排序观看争论。"
      },
      "ev:src_lunyu_liren:liren04:profit_breeds_resentment:aa220000": {
            "label": "逐利生怨",
            "family": "义利",
            "note": "观察官府逐利如何累积民怨。"
      },
      "ev:src_mengzi_lianghuiwang:liang01:renyi_over_profit:aa110002": {
            "label": "仁义高于利",
            "family": "义利",
            "note": "把国家目标从收益转回仁义。"
      },
      "ev:src_mengzi_lianghuiwang:liang01:profit_endangers_state:aa220006": {
            "label": "交征利危",
            "family": "义利",
            "note": "追问上下逐利如何危及国家。"
      },
      "ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003": {
            "label": "节用裕民",
            "family": "富国",
            "note": "承认制度治理，同时要求富国不伤民。"
      },
      "ev:src_guanzi_mumin:mumin01:canglin_lijie:aa110004": {
            "label": "仓廪礼节",
            "family": "富国",
            "note": "从物质基础理解秩序何以可能。"
      },
      "ev:src_hanfeizi_wudu:wudu:adapt_law_to_age:aa110005": {
            "label": "因世变法",
            "family": "法术",
            "note": "把制度有效性放进时代变化中检验。"
      },
      "ev:src_shangjunshu_nongzhan:nongzhan:state_agriculture_war:aa110006": {
            "label": "农战国家",
            "family": "农战",
            "note": "用耕战动员观看边防财政。"
      },
      "ev:src_lunyu_xueer:xueer01:govern_with_time:aa110007": {
            "label": "使民以时",
            "family": "民生",
            "note": "用不误农时衡量动员边界。"
      },
      "ev:src_xunzi_tianlun:tianlun:nature_constant:aa110008": {
            "label": "天行有常",
            "family": "灾异",
            "note": "区分自然灾害与政治责任。"
      },
      "ev:src_mengzi_tengwen:tengwen01:constant_livelihood:aa110009": {
            "label": "恒产民生",
            "family": "民生",
            "note": "先看百姓是否有稳定生计。"
      },
      "ev:src_liji_liyun:liyun:public_order:aa110010": {
            "label": "礼运公序",
            "family": "礼法",
            "note": "用公共秩序理解礼与制度。"
      },
      "ev:src_lunyu_yanyuan:yanyuan07:food_army_trust:aa220001": {
            "label": "食兵民信",
            "family": "国家能力",
            "note": "同时衡量粮食、军备与民信。"
      },
      "ev:src_lunyu_yanyuan:yanyuan12:governance_rectification:aa220002": {
            "label": "政者正也",
            "family": "德治",
            "note": "追问权力自身是否正当。"
      },
      "ev:src_lunyu_yanyuan:yanyuan13:no_litigation:aa220003": {
            "label": "无讼追问",
            "family": "议政",
            "note": "从争论回看制度病根。"
      },
      "ev:src_mengzi_jinxinxia:jinxin14:people_first:aa220004": {
            "label": "民贵君轻",
            "family": "民本",
            "note": "把民生置于国家目标之前检验。"
      },
      "ev:src_mengzi_gaozishang:gaozi10:choose_righteousness:aa220005": {
            "label": "取义之择",
            "family": "义利",
            "note": "看哪些选择不能只按利益计算。"
      },
      "ev:src_xunzi_wangzhi:wangzhi:boat_water:aa220007": {
            "label": "舟水之喻",
            "family": "民本",
            "note": "观察国家权力对民众承载的依赖。"
      },
      "ev:src_xunzi_wangzhi:wangzhi:market_tax_light:aa220008": {
            "label": "关市轻征",
            "family": "市场",
            "note": "承认市场治理，但警惕官府重取。"
      },
      "ev:src_xunzi_xiushen:xiushen:ritual_corrects_body:aa220009": {
            "label": "礼以正身",
            "family": "礼法",
            "note": "把礼看成秩序技术而非装饰。"
      },
      "ev:src_guanzi_quanxiu:quanxiu:long_term_teaching:aa220010": {
            "label": "树人之计",
            "family": "教化",
            "note": "用长期教化衡量政治能力。"
      },
      "ev:src_guanzi_mumin:mumin01:follow_people_heart:aa220011": {
            "label": "顺民心",
            "family": "民本",
            "note": "富国术也要接受民心检验。"
      },
      "ev:src_hanfeizi_youdu:youdu:law_no_noble:aa220012": {
            "label": "法不阿贵",
            "family": "法术",
            "note": "用同一尺度约束贵势与私门。"
      },
      "ev:src_hanfeizi_xianxue:xianxue:scholars_disorder_law:aa220013": {
            "label": "文乱法",
            "family": "法术",
            "note": "理解法家对空言议政的警惕。"
      },
      "ev:src_mozi_feile:feile01:three_harms:aa220014": {
            "label": "饥寒劳苦",
            "family": "民生",
            "note": "把制度成本落实到百姓身体感受。"
      },
      "ev:src_liji_wangzhi:wangzhi:labor_limit:aa220015": {
            "label": "用民有限",
            "family": "徭役",
            "note": "国家动员必须有边界。"
      },
      "ev:src_liji_wangzhi:wangzhi:nine_year_storage:aa220016": {
            "label": "九年之蓄",
            "family": "财政",
            "note": "承认储备是国家安定的一部分。"
      },
      "ev:src_huainanzi_zhushu:zhushu:law_as_measure:aa220017": {
            "label": "法为准绳",
            "family": "权力边界",
            "note": "制度也应约束权力本身。"
      }
};

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
      renderChapterMap();
      await renderExperience();
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
      renderDramaOverlay(scene);
      renderMap(scene);
      renderCourt(scene);
      renderNetwork(scene);
      renderJudgmentBackdrop(scene);
    }

    function dramaPhaseFor(scene) {
      if (scene.visualMode === "background-map") return "map-pressure";
      if (scene.visualMode === "meeting-open") return "meeting-threshold";
      if (scene.visualMode === "fiscal-ascendant") return "fiscal-pressure";
      if (scene.visualMode === "livelihood-counter") return "livelihood-counter";
      if (scene.visualMode === "power-shadow") return "power-shadow";
      if (scene.key === "network") return "power-shadow";
      return "value-clash";
    }

    function renderDramaOverlay(scene) {
      const phase = dramaPhaseFor(scene);
      state.dramaPhase = phase;
      state.sceneProgress = scenes.length > 1 ? state.sceneIndex / (scenes.length - 1) : 0;
      const stage = document.querySelector(".stage");
      const world = document.querySelector(".scene-world");
      const opening = document.getElementById("courtPressureOpening");
      const isDirectorEntry = state.experiencePhase === "pressure_entry" || state.experiencePhase === "standpoint_choice";
      const isPrologueActive = isDirectorEntry || (state.sceneIndex === 0 && phase === "map-pressure");
      stage.classList.toggle("is-prologue-active", isPrologueActive);
      stage.dataset.prologue = isPrologueActive ? "active" : "complete";
      stage.dataset.experiencePhase = experienceDirector.phaseForScene(scene);
      world.dataset.dramaPhase = phase;
      opening.dataset.dramaPhase = phase;
      opening.dataset.visualMode = scene.visualMode || scene.key;
      opening.dataset.prologue = isPrologueActive ? "active" : "complete";
    }

    function supportMeta(value) {
      return {
        value,
        label: experienceDirector.supportLabel(value)
      };
    }

    function evidenceSupportFor(evidenceId) {
      if (philosophyLensMeta[evidenceId]) return supportMeta(65);
      if (/^ev:src_(yantielun|hanshu|shiji|zizhi)/.test(evidenceId)) return supportMeta(95);
      return supportMeta(80);
    }

    function sceneSupportFor(scene) {
      const hasLens = Array.isArray(scene.philosophyLens) && scene.philosophyLens.length > 0;
      const hasHistory = Array.isArray(scene.historicalEvidence) && scene.historicalEvidence.length > 0;
      if (hasHistory && hasLens) return supportMeta(80);
      if (hasHistory) return supportMeta(95);
      return supportMeta(65);
    }

    function supportMarkup(meta) {
      return `
        <div class="support-strength" title="证据支持强度，不是绝对真相概率">
          <span>证据支持强度</span>
          <div class="support-track"><i style="width: ${Number(meta.value)}%"></i></div>
          <em>${Number(meta.value)}</em>
        </div>
        <p class="support-note">${escapeHtml(meta.label)}。这是证据支持强度，不是绝对真相概率。</p>
      `;
    }

    function pressureRowsMarkup(pressure) {
      return Object.entries(experienceDirector.pressureLabels).map(([key, label]) => {
        const value = Number(pressure[key] || 0);
        return `
          <div class="pressure-row">
            <span>${escapeHtml(label)}</span>
            <div class="pressure-bar"><i style="width: ${value}%"></i></div>
            <em>${value}</em>
          </div>
        `;
      }).join("");
    }

    function pressureSceneFor(item) {
      return {
        key: "map",
        layer: "map",
        visualMode: "background-map",
        evidence: item.evidence,
        historicalEvidence: item.evidence,
        philosophyLens: []
      };
    }

    function renderPressurePanel(item) {
      const support = supportMeta(item.support);
      document.getElementById("pressureDirectorPanel").innerHTML = `
        <span class="pressure-time">${escapeHtml(item.time)}</span>
        <h2>${escapeHtml(item.title)}</h2>
        <p>${escapeHtml(item.narration)}</p>
        <div class="pressure-grid" aria-label="历史压力变化">
          ${pressureRowsMarkup(item.pressure)}
        </div>
        ${supportMarkup(support)}
      `;
    }

    function renderStandpointPanel() {
      document.getElementById("pressureDirectorPanel").innerHTML = `
        <span class="pressure-time">入朝之前</span>
        <h2>你先站在哪里？</h2>
        <p>不要先选择正确答案。先选择你愿意承受哪一种压力，再进入盐铁会议。</p>
        <div class="standpoint-grid" aria-label="初始身份选择">
          ${standpointRoles.map(role => `
            <button class="standpoint-card${state.userStandpoint === role.id ? " is-selected" : ""}" type="button" data-standpoint-id="${escapeHtml(role.id)}">
              <strong>${escapeHtml(role.label)}</strong>
              <span>${escapeHtml(role.pressureFocus)}压力 · 初始倾向 ${Number(role.initialLeaning)}/100</span>
              <span>${escapeHtml(role.innerVoice)}</span>
            </button>
          `).join("")}
        </div>
        <p class="support-note">这一选择不会改变历史事实，只会记录你的进入视角，并进入最终观点变化图。</p>
      `;
    }

    async function renderPressureEntry() {
      const item = pressureTimeline[state.pressureIndex];
      const scene = pressureSceneFor(item);
      renderRoundVisual(scene);
      renderDramaOverlay(scene);
      renderPressurePanel(item);
      document.getElementById("chapterKicker").textContent = "历史压力入场";
      document.getElementById("sceneTitle").textContent = item.title;
      document.getElementById("sceneCopy").textContent = item.narration;
      document.getElementById("sceneQuote").textContent = "背景不是说明文字；背景正在发生。";
      const advance = document.getElementById("advanceScene");
      advance.disabled = false;
      advance.textContent = state.pressureIndex === pressureTimeline.length - 1 ? "选择站位" : "继续经历";
      document.getElementById("rewindScene").style.visibility = state.pressureIndex === 0 ? "hidden" : "visible";
      document.querySelectorAll("[data-scene-layer]").forEach(layer => layer.classList.remove("is-active"));
      document.getElementById("mapScene").classList.add("is-active");
      document.getElementById("decisionDock").classList.add("is-empty");
      closeEvidence();
      pulseSound("map-pressure");
    }

    async function renderStandpointChoice() {
      const item = pressureTimeline[pressureTimeline.length - 1];
      const scene = pressureSceneFor(item);
      renderRoundVisual(scene);
      renderDramaOverlay(scene);
      renderStandpointPanel();
      document.getElementById("chapterKicker").textContent = "入朝之前 · 初始站队";
      document.getElementById("sceneTitle").textContent = "选择你带入朝堂的压力";
      document.getElementById("sceneCopy").textContent = "国家财政官、边疆将军、地方百姓、盐铁商人都没有说完整的谎；他们只是承担不同压力。";
      document.getElementById("sceneQuote").textContent = state.userStandpoint ? standpointRoles.find(role => role.id === state.userStandpoint).innerVoice : "先站队，再进入会议；之后你可以被证据改变。";
      const advance = document.getElementById("advanceScene");
      advance.disabled = !state.userStandpoint;
      advance.textContent = state.userStandpoint ? "带着立场入朝" : "先选择身份";
      document.getElementById("rewindScene").style.visibility = "visible";
      document.querySelectorAll("[data-scene-layer]").forEach(layer => layer.classList.remove("is-active"));
      document.getElementById("mapScene").classList.add("is-active");
      closeEvidence();
    }

    async function renderExperience() {
      if (state.experiencePhase === "pressure_entry") {
        await renderPressureEntry();
        return;
      }
      if (state.experiencePhase === "standpoint_choice") {
        await renderStandpointChoice();
        return;
      }
      await renderScene();
    }

    function lensMetaFor(evidenceId) {
      return philosophyLensMeta[evidenceId] || {
        label: "思想透镜",
        family: "解释",
        note: "这是一种解释角度，不作为会议事实。"
      };
    }

    function isPhilosophyLensEvidence(evidence) {
      return Array.isArray(evidence.value_tags) && evidence.value_tags.includes("philosophy_lens");
    }

    function sceneEvidenceButtons(scene) {
      const rawButtons = [
        ...(scene.historicalEvidence || []).map((id, index) => ({ id, label: `史证 ${index + 1}`, support: evidenceSupportFor(id) })),
        ...(scene.philosophyLens || []).map(id => ({ id, label: lensMetaFor(id).label, support: evidenceSupportFor(id) }))
      ];
      const seen = new Set();
      return rawButtons.filter(item => {
        if (seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      });
    }

    function renderSceneCaption(scene) {
      const support = sceneSupportFor(scene);
      document.getElementById("debateHud").innerHTML = `
        <div class="scene-caption" data-visual-mode="${escapeHtml(scene.visualMode)}">
          <div class="debate-meta">
            <span class="debate-speaker">${escapeHtml(scene.speaker)}</span>
            <span class="stance-chip">${escapeHtml(scene.stance)}</span>
            <span>${escapeHtml(scene.kicker)}</span>
          </div>
          <p class="debate-line">${escapeHtml(scene.line)}</p>
          ${supportMarkup(support)}
        </div>
      `;
    }

    function renderDecisionDock(scene) {
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
      const evidenceButtons = sceneEvidenceButtons(scene);
      const dock = document.getElementById("decisionDock");
      dock.classList.toggle("is-empty", false);
      dock.innerHTML = `
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
              <button class="evidence-seal" type="button" data-evidence-id="${escapeHtml(item.id)}">
                ${escapeHtml(item.label)}
                <em>证据支持强度 ${Number(item.support.value)}</em>
              </button>
            `).join("")}
          </div>
      `;
    }

    function mapPointForFeature(feature) {
      const restoredPoints = {
        feature_changan: [408, 314],
        feature_northern_frontier: [506, 132],
        feature_jincheng: [300, 242],
        feature_salt_iron_resources: [716, 424],
        feature_equal_transport_routes: [574, 356]
      };
      if (restoredPoints[feature.feature_id]) return restoredPoints[feature.feature_id];
      const [x, y] = feature.coordinates.length === 2 ? feature.coordinates : [50, 50];
      return [Math.max(120, Math.min(850, x * 8.6)), Math.max(112, Math.min(560, y * 7.2))];
    }

    function renderHanRestoredBasemap() {
      return `
        <g class="han-restored-basemap" data-testid="han-restored-basemap" data-gis-mode="open-source-compatible" aria-label="开源 GIS 兼容的汉昭帝时期复原叙事地图">
          <path class="gis-grid" d="M150 126 H860 M150 214 H860 M150 302 H860 M150 390 H860 M150 478 H860 M150 566 H860 M190 112 V588 M300 112 V588 M410 112 V588 M520 112 V588 M630 112 V588 M740 112 V588 M850 112 V588"
            fill="none" stroke="rgba(255,244,214,0.5)" stroke-width="1"/>
          <path class="region-fill" d="M126 338 C138 270 188 226 260 214 C310 166 390 146 474 156 C562 144 658 168 742 226 C830 286 872 354 854 430 C832 516 724 564 602 540 C508 594 380 592 274 534 C184 520 112 444 126 338 Z"
            fill="url(#hanLand)" stroke="#5d4327" stroke-width="7" opacity="0.94"/>
          <path class="region-fill" d="M182 214 C228 162 322 122 430 132 C498 134 562 150 626 180 C562 208 484 222 398 216 C314 210 246 226 182 214 Z"
            fill="rgba(87,111,107,0.28)" stroke="rgba(255,236,188,0.32)" stroke-width="3"/>
          <path class="region-fill" d="M252 264 C292 224 360 210 424 228 C456 270 444 326 398 356 C332 366 280 336 252 264 Z"
            fill="rgba(196,146,69,0.26)" stroke="rgba(255,236,188,0.46)" stroke-width="3"/>
          <path class="region-fill" d="M520 230 C626 212 744 250 820 340 C796 410 690 456 566 430 C534 368 516 300 520 230 Z"
            fill="rgba(174,134,70,0.2)" stroke="rgba(255,236,188,0.34)" stroke-width="3"/>
          <path class="region-fill" d="M442 440 C546 466 662 484 810 454 C762 526 652 568 528 542 C482 518 450 486 442 440 Z"
            fill="rgba(64,111,91,0.22)" stroke="rgba(255,236,188,0.3)" stroke-width="3"/>
          <path class="frontier-ridge" d="M174 194 C272 146 382 122 504 132 C638 142 744 184 824 246"/>
          <path class="region-boundary" d="M242 242 C342 224 444 238 526 206 C618 174 728 206 816 282" fill="none" stroke="rgba(255,236,188,0.34)" stroke-width="3"/>
          <path class="region-boundary" d="M354 184 C382 262 382 356 422 438 C452 496 506 520 574 536" fill="none" stroke="rgba(255,236,188,0.26)" stroke-width="3"/>
          <path class="region-boundary" d="M510 236 C606 274 674 342 802 368" fill="none" stroke="rgba(255,236,188,0.28)" stroke-width="3"/>
          <path class="han-river" d="M194 318 C300 300 386 314 474 288 C584 256 662 282 782 240"/>
          <path class="han-river" d="M420 462 C538 498 632 520 778 492" opacity="0.64"/>
          <path d="M186 224 C216 248 230 286 228 338" fill="none" stroke="rgba(255,244,214,0.22)" stroke-width="6" stroke-linecap="round"/>
          <path d="M304 190 C356 220 374 248 408 314" fill="none" stroke="rgba(255,244,214,0.22)" stroke-width="5" stroke-linecap="round"/>
          <text class="region-label" x="364" y="268" fill="rgba(255,244,214,0.8)" font-size="24" text-anchor="middle">关中</text>
          <text class="region-label" x="340" y="166" fill="rgba(255,244,214,0.58)" font-size="18" text-anchor="middle">河西 / 北边郡</text>
          <text class="region-label" x="666" y="308" fill="rgba(255,244,214,0.58)" font-size="19" text-anchor="middle">山东郡国</text>
          <text class="region-label" x="690" y="510" fill="rgba(255,244,214,0.5)" font-size="17" text-anchor="middle">江淮与山海资源</text>
          <text class="map-source-label" x="858" y="604" fill="rgba(255,244,214,0.54)" font-size="14" text-anchor="end">开源 GIS 方案兼容 · 本地简化矢量层</text>
          <text class="map-source-label" x="858" y="628" fill="rgba(255,244,214,0.42)" font-size="13" text-anchor="end">参考历史地理资料复原 · 非精确测绘边界</text>
        </g>`;
    }

    function renderMap(scene) {
      const svg = document.getElementById("hanMapScene");
      const features = state.mapLayers.flatMap(layer => layer.features.map(feature => ({ layer, feature })));
      const pressureOpacity = scene.visualMode === "fiscal-ascendant" ? 0.96 : scene.visualMode === "background-map" ? 0.9 : 0.52;
      const featureElements = features.map(({ layer, feature }) => {
        const [px, py] = mapPointForFeature(feature);
        const color = layer.layer_type === "capital" ? "#9a241c" : layer.layer_type === "military_frontier" ? "#36516c" : "#2c7a66";
        const labelX = feature.feature_id === "feature_changan" ? px + 24 : Math.min(px + 22, 840);
        const labelY = feature.feature_id === "feature_northern_frontier" ? py - 22 : py - 14;
        const markerSize = layer.layer_type === "capital" ? 20 : 14;
        return `<g class="map-feature-marker" filter="url(#softGlow)" data-feature="${escapeHtml(feature.feature_id)}">
          <circle cx="${px}" cy="${py}" r="${markerSize}" fill="${color}" stroke="#fff4d6" stroke-width="5"/>
          <text x="${labelX}" y="${labelY}" fill="#fff4d6" font-size="24">${escapeHtml(feature.title)}</text>
        </g>`;
      }).join("");

      svg.innerHTML = `
        <defs>
          <linearGradient id="hanLand" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#7c613e"/>
            <stop offset="0.42" stop-color="#c49a5f"/>
            <stop offset="0.72" stop-color="#e0bd78"/>
            <stop offset="1" stop-color="#8a673e"/>
          </linearGradient>
          <radialGradient id="capitalGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0" stop-color="rgba(255,244,214,0.36)"/>
            <stop offset="0.68" stop-color="rgba(243,196,109,0.12)"/>
            <stop offset="1" stop-color="rgba(243,196,109,0)"/>
          </radialGradient>
          <filter id="softGlow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <filter id="restoredPaper"><feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="81"/><feDisplacementMap in="SourceGraphic" scale="1.4"/></filter>
        </defs>
        <rect width="1000" height="680" fill="rgba(7,10,15,0.5)"/>
        ${renderHanRestoredBasemap()}
        <g data-testid="v3-map-pressure-routes" class="map-narrative-pressure" opacity="${pressureOpacity}">
          <path class="pressure-route" d="M506 132 C474 190 440 244 408 314" fill="none" stroke="#9a241c" stroke-width="8" stroke-linecap="round"/>
          <path class="pressure-route" d="M716 424 C642 392 546 350 408 314" fill="none" stroke="#2c7a66" stroke-width="7" stroke-linecap="round" opacity="0.74"/>
          <path class="pressure-route" d="M574 356 C518 336 462 326 408 314" fill="none" stroke="#f3c46d" stroke-width="6" stroke-linecap="round" opacity="0.78"/>
          <circle class="resource-pulse is-frontier" cx="506" cy="132" r="38" fill="rgba(154,36,28,0.2)" stroke="rgba(154,36,28,0.68)" stroke-width="3"/>
          <circle class="resource-pulse" cx="716" cy="424" r="36" fill="rgba(44,122,102,0.2)" stroke="rgba(44,122,102,0.68)" stroke-width="3"/>
          <circle class="resource-pulse is-transport" cx="574" cy="356" r="34" fill="rgba(243,196,109,0.16)" stroke="rgba(243,196,109,0.62)" stroke-width="3"/>
          <circle class="capital-pulse" cx="408" cy="314" r="64" fill="url(#capitalGlow)" stroke="rgba(255,244,214,0.62)" stroke-width="4"/>
          <text class="route-label" x="510" y="96" text-anchor="middle" fill="#ffe7b0" font-size="20">边费</text>
          <text class="route-label" x="748" y="456" text-anchor="middle" fill="#d8f4dc" font-size="18">盐铁山海</text>
          <text class="route-label" x="594" y="334" text-anchor="middle" fill="#fff4d6" font-size="17">均输</text>
        </g>
        ${featureElements}
        <rect class="court-threshold-wash" width="1000" height="680" fill="rgba(9,13,19,0.5)"/>
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
      const courtPressure = scene.visualMode === "fiscal-ascendant" || scene.visualMode === "livelihood-counter" || scene.visualMode === "power-shadow";
      const v3CourtPressureField = `
        <g data-testid="v3-court-pressure-field" opacity="${courtPressure || scene.visualMode === "meeting-open" ? 0.92 : 0.5}">
          <path d="M110 558 C268 426 350 336 500 210 C650 336 732 426 890 558"
            fill="none" stroke="rgba(255,236,188,0.18)" stroke-width="4"/>
          <path d="M500 136 C456 258 382 366 250 486 C420 426 578 426 750 486 C618 366 544 258 500 136 Z"
            fill="rgba(154,36,28,${scene.visualMode === "power-shadow" ? 0.38 : 0.12})"/>
          <path d="M246 474 C342 374 404 318 500 248" fill="none" stroke="rgba(54,81,108,0.46)" stroke-width="9" stroke-linecap="round"/>
          <path d="M754 474 C658 374 596 318 500 248" fill="none" stroke="rgba(44,122,102,0.46)" stroke-width="9" stroke-linecap="round"/>
          <path d="M500 148 C500 230 500 322 500 476" fill="none" stroke="rgba(154,36,28,0.42)" stroke-width="12" stroke-linecap="round"/>
          <text x="270" y="522" text-anchor="middle" fill="#cfe5ff" font-size="22">财政压力</text>
          <text x="730" y="522" text-anchor="middle" fill="#dcf7df" font-size="22">民生反问</text>
          <text x="500" y="314" text-anchor="middle" fill="#ffe7b0" font-size="24">权力边界</text>
        </g>
      `;
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
        ${v3CourtPressureField}
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
        <text x="500" y="650" text-anchor="middle" fill="rgba(255,244,214,0.66)" font-size="22">朝堂不是中立空间，发声始终处在压力之中。</text>
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


    function renderChapterMap() {
      const groups = chapterConflictMap.reduce((acc, chapter) => {
        if (!acc[chapter.juan]) acc[chapter.juan] = [];
        acc[chapter.juan].push(chapter);
        return acc;
      }, {});
      const active = chapterConflictMap[state.activeChapterIndex] || chapterConflictMap[0];
      document.getElementById("chapterMapPanel").innerHTML = `
        <div class="chapter-map-head">
          <h2 class="chapter-map-title">诸篇争锋 · ${chapterConflictMap.length} 篇</h2>
          <button class="chapter-map-close" type="button" data-close-chapter-map aria-label="关闭章节图谱" title="关闭章节图谱">×</button>
        </div>
        <div class="chapter-grid" aria-label="盐铁论六十篇章节冲突图谱">
          ${Object.entries(groups).map(([juan, chapters]) => `
            <section class="juan-band">
              <div class="juan-title">${escapeHtml(juan)}</div>
              <div class="chapter-node-grid">
                ${chapters.map(chapter => `
                  <button class="chapter-node ${chapter.chapterNumber === active.chapterNumber ? "is-active" : ""}" type="button" data-chapter-number="${chapter.chapterNumber}">
                    <strong>${chapter.chapterNumber}. ${escapeHtml(chapter.title)}</strong>
                    <span>${escapeHtml(chapter.conflict)}</span>
                  </button>
                `).join("")}
              </div>
            </section>
          `).join("")}
        </div>
        <aside class="chapter-detail" id="chapterDetail"></aside>
      `;
      renderChapterDetail(active);
    }

    function renderChapterDetail(chapter) {
      state.activeChapterIndex = chapter.chapterNumber - 1;
      state.visitedChapters.add(chapter.chapterNumber);
      const detail = document.getElementById("chapterDetail");
      if (!detail) return;
      const lensButtons = chapter.philosophyLens.map(id => {
        const meta = lensMetaFor(id);
        return `
          <button class="evidence-seal lens-seal" type="button" data-evidence-id="${escapeHtml(id)}">
            <strong>${escapeHtml(meta.label)}</strong>
            <span>${escapeHtml(meta.note)}</span>
          </button>
        `;
      }).join("");
      detail.innerHTML = `
        <p class="chapter-kicker">${escapeHtml(chapter.juan)} · 第 ${chapter.chapterNumber} 篇 · ${escapeHtml(chapter.actKey)}</p>
        <h3>${escapeHtml(chapter.title)}</h3>
        <p class="chapter-conflict">${escapeHtml(chapter.conflict)}</p>
        <div class="voice-pair" aria-label="本篇两股声音">
          ${chapter.voices.map(voice => `
            <div class="voice-chip">
              <strong>${escapeHtml(voice.side)}</strong>
              <span>${escapeHtml(voice.text)}</span>
            </div>
          `).join("")}
        </div>
        <div class="evidence-seals" aria-label="本篇史证">
          ${chapter.historicalEvidence.map((id, index) => `<button class="evidence-seal" type="button" data-evidence-id="${escapeHtml(id)}">史证 ${index + 1}</button>`).join("")}
        </div>
        <div class="lens-section" aria-label="本篇思想透镜">
          <p class="lens-section-title">用什么眼光看这场争论</p>
          <div class="lens-grid">${lensButtons}</div>
        </div>
      `;
      document.querySelectorAll(".chapter-node").forEach(node => {
        node.classList.toggle("is-active", Number(node.dataset.chapterNumber) === chapter.chapterNumber);
      });
    }

    function openChapterMap() {
      state.chapterMapOpen = true;
      renderChapterMap();
      document.getElementById("chapterMapPanel").classList.add("is-open");
      document.getElementById("chapterMapScrim").classList.add("is-open");
      pulseSound("evidence");
    }

    function closeChapterMap() {
      state.chapterMapOpen = false;
      document.getElementById("chapterMapPanel").classList.remove("is-open");
      document.getElementById("chapterMapScrim").classList.remove("is-open");
    }

    async function renderScene() {
      const scene = scenes[state.sceneIndex];
      renderRoundVisual(scene);
      renderSceneCaption(scene);
      renderDecisionDock(scene);
      document.getElementById("chapterKicker").textContent = scene.kicker;
      document.getElementById("sceneTitle").textContent = scene.title;
      document.getElementById("sceneCopy").textContent = scene.copy;
      document.getElementById("sceneQuote").textContent = scene.quote;
      const advanceButton = document.getElementById("advanceScene");
      advanceButton.disabled = false;
      advanceButton.textContent = state.sceneIndex === 0 ? "进入朝堂" : state.sceneIndex === scenes.length - 1 ? "停在案前" : "继续进入";
      document.getElementById("rewindScene").style.visibility = state.sceneIndex === 0 ? "hidden" : "visible";
      document.querySelectorAll("[data-scene-layer]").forEach(layer => layer.classList.remove("is-active"));
      const layerId = scene.key === "map" ? "mapScene" : scene.key === "court" ? "courtScene" : scene.key === "network" ? "networkScene" : "judgmentScene";
      document.getElementById(layerId).classList.add("is-active");
      if (scene.key === "judgment") renderStanceTrajectoryPanel();
      closeEvidence();
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
      evidenceItems.forEach(evidence => {
        if (isPhilosophyLensEvidence(evidence)) state.visitedLensIds.add(evidence.evidence_id);
      });
      const allLens = evidenceItems.length > 0 && evidenceItems.every(isPhilosophyLensEvidence);
      const ribbon = document.getElementById("evidenceRibbon");
      ribbon.innerHTML = `
        <div class="evidence-panel-head">
          <p class="evidence-panel-title">${allLens ? "思想透镜" : "史料浮现"}</p>
          <button class="evidence-close" type="button" data-close-evidence aria-label="关闭证据" title="关闭证据">×</button>
        </div>
        <div class="evidence-list">
          ${evidenceItems.map(evidence => {
            const isLens = isPhilosophyLensEvidence(evidence);
            const meta = isLens ? lensMetaFor(evidence.evidence_id) : null;
            return `
            <div class="evidence-item${isLens ? " is-lens" : ""}">
              ${isLens ? `<span class="evidence-boundary">${escapeHtml(meta.label)} · 思想透镜，不是会议事实</span>` : ""}
              <strong>${escapeHtml(evidence.excerpt_original || evidence.paraphrase_zh)}</strong>
              <span>${escapeHtml(evidence.paraphrase_zh)}</span>
              ${isLens ? `<span>${escapeHtml(meta.note)}</span>` : ""}
              <span>${escapeHtml(evidence.source_id)} · ${escapeHtml(evidence.canonical_location)}</span>
            </div>
          `}).join("")}
        </div>
      `;
      ribbon.classList.add("is-open");
      document.getElementById("evidenceScrim").classList.add("is-open");
      pulseSound("evidence");
    }

    function closeEvidence() {
      document.getElementById("evidenceRibbon").classList.remove("is-open");
      document.getElementById("evidenceScrim").classList.remove("is-open");
    }

    document.getElementById("advanceScene").addEventListener("click", async () => {
      if (state.experiencePhase === "pressure_entry") {
        if (state.pressureIndex < pressureTimeline.length - 1) {
          state.pressureIndex += 1;
        } else {
          state.experiencePhase = "standpoint_choice";
        }
        await renderExperience();
        return;
      }
      if (state.experiencePhase === "standpoint_choice") {
        if (!state.userStandpoint) return;
        state.experiencePhase = "court_debate";
        state.sceneIndex = 1;
        await renderExperience();
        return;
      }
      if (state.sceneIndex < scenes.length - 1) {
        state.sceneIndex += 1;
        state.experiencePhase = experienceDirector.phaseForScene(scenes[state.sceneIndex]);
        await renderScene();
      }
    });

    document.getElementById("rewindScene").addEventListener("click", async () => {
      if (state.experiencePhase === "pressure_entry") {
        if (state.pressureIndex > 0) state.pressureIndex -= 1;
        await renderExperience();
        return;
      }
      if (state.experiencePhase === "standpoint_choice") {
        state.experiencePhase = "pressure_entry";
        state.pressureIndex = pressureTimeline.length - 1;
        await renderExperience();
        return;
      }
      if (state.sceneIndex > 0) {
        state.sceneIndex -= 1;
        if (state.sceneIndex <= 0) {
          state.experiencePhase = "pressure_entry";
          state.pressureIndex = pressureTimeline.length - 1;
          await renderExperience();
        } else {
          state.experiencePhase = experienceDirector.phaseForScene(scenes[state.sceneIndex]);
          await renderScene();
        }
      }
    });

    document.getElementById("revealEvidence").addEventListener("click", () => openEvidence());

    document.getElementById("pressureDirectorPanel").addEventListener("click", async event => {
      const roleNode = event.target.closest("[data-standpoint-id]");
      if (!roleNode) return;
      const role = standpointRoles.find(item => item.id === roleNode.dataset.standpointId);
      if (!role) return;
      state.userStandpoint = role.id;
      experienceDirector.recordTrajectory({
        stage: "standpoint",
        label: role.label,
        value: role.initialLeaning,
        note: role.innerVoice
      });
      await renderStandpointChoice();
    });

    document.getElementById("chapterMapToggle").addEventListener("click", openChapterMap);

    document.getElementById("chapterMapScrim").addEventListener("click", closeChapterMap);

    document.getElementById("chapterMapPanel").addEventListener("click", event => {
      const chapterNode = event.target.closest("[data-chapter-number]");
      if (chapterNode) {
        const chapter = chapterConflictMap.find(item => item.chapterNumber === Number(chapterNode.dataset.chapterNumber));
        if (chapter) renderChapterDetail(chapter);
        return;
      }
      const evidenceTarget = event.target.closest("[data-evidence-id]");
      if (evidenceTarget) {
        openEvidence(evidenceTarget.dataset.evidenceId);
        return;
      }
      if (event.target.closest("[data-close-chapter-map]")) closeChapterMap();
    });

    document.getElementById("decisionDock").addEventListener("click", event => {
      const target = event.target.closest("[data-evidence-id]");
      if (!target) return;
      openEvidence(target.dataset.evidenceId);
    });

    document.getElementById("evidenceScrim").addEventListener("click", closeEvidence);

    document.getElementById("evidenceRibbon").addEventListener("click", event => {
      if (!event.target.closest("[data-close-evidence]")) return;
      closeEvidence();
    });

    document.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        closeEvidence();
        closeChapterMap();
      }
    });

    document.getElementById("decisionDock").addEventListener("input", event => {
      const target = event.target.closest("[data-act-key]");
      if (!target) return;
      state.userChoices[target.dataset.actKey] = Number(target.value);
      const act = conflictActs.find(item => item.key === target.dataset.actKey);
      if (act) {
        const leaning = leaningForAct(act);
        experienceDirector.recordTrajectory({
          stage: act.key,
          label: act.kicker,
          value: leaning.value,
          note: leaning.label
        });
      }
      if (scenes[state.sceneIndex]?.key === "judgment") renderStanceTrajectoryPanel();
    });

    document.getElementById("soundToggle").addEventListener("click", async () => {
      await ensureAudio();
      state.soundEnabled = !state.soundEnabled;
      document.getElementById("soundToggle").setAttribute("aria-pressed", String(state.soundEnabled));
      if (state.soundEnabled) pulseSound("open");
    });

    function buildChapterVisitSummary() {
      const visited = Array.from(state.visitedChapters).sort((a, b) => a - b);
      if (!visited.length) return "诸篇争锋：尚未打开具体章节。";
      return `诸篇争锋访问：${visited.map(number => chapterConflictMap[number - 1]?.title || `第${number}篇`).join("、")}`;
    }

    function buildLensVisitSummary() {
      const chapterLensIds = Array.from(state.visitedChapters).flatMap(number => {
        const chapter = chapterConflictMap[number - 1];
        return chapter ? chapter.philosophyLens : [];
      });
      const lensIds = [...Array.from(state.visitedLensIds), ...chapterLensIds]
        .filter((id, index, ids) => ids.indexOf(id) === index);
      if (!lensIds.length) return "思想透镜：尚未借用具体透镜。";
      const families = lensIds.map(id => lensMetaFor(id).family)
        .filter((family, index, values) => values.indexOf(family) === index);
      const labels = lensIds.map(id => lensMetaFor(id).label)
        .filter((label, index, values) => values.indexOf(label) === index);
      return `思想透镜：${families.join("、")}。具体视角：${labels.join("、")}`;
    }

    function buildChoiceSummary() {
      return conflictActs.map(act => {
        const value = Number(state.userChoices[act.key] ?? 50);
        const leaning = value < 40 ? act.choiceLeft : value > 60 ? act.choiceRight : "保留张力";
        return `${act.kicker}：${leaning}（${value}/100）`;
      }).join("\\n");
    }

    function selectedStandpointRole() {
      return standpointRoles.find(role => role.id === state.userStandpoint) || null;
    }

    function leaningForAct(act) {
      const value = Number(state.userChoices[act.key] ?? 50);
      return {
        value,
        label: value < 40 ? act.choiceLeft : value > 60 ? act.choiceRight : "保留张力"
      };
    }

    function buildStanceTrajectoryItems() {
      const role = selectedStandpointRole();
      const items = [];
      if (role) {
        items.push(`入场身份：${role.label}。初始压力：${role.pressureFocus}。内心判断：${role.innerVoice}`);
      } else {
        items.push("入场身份：尚未选择。");
      }
      conflictActs.forEach(act => {
        const leaning = leaningForAct(act);
        items.push(`${act.kicker}：${leaning.label}（${leaning.value}/100）`);
      });
      const finalAct = conflictActs[conflictActs.length - 1];
      const finalLeaning = leaningForAct(finalAct);
      items.push(`最终倾向：带着“${finalLeaning.label}”离开朝堂；这仍是个人判断，不是历史事实。`);
      return items;
    }

    function buildStanceTrajectorySummary() {
      return `观点变化图：\\n${buildStanceTrajectoryItems().join("\\n")}`;
    }

    function renderStanceTrajectoryPanel() {
      const panel = document.getElementById("stanceTrajectoryPanel");
      if (!panel) return;
      panel.innerHTML = `
        <strong>观点变化图</strong>
        <ol>
          ${buildStanceTrajectoryItems().map(item => `<li>${escapeHtml(item)}</li>`).join("")}
        </ol>
      `;
    }

    document.getElementById("judgmentForm").addEventListener("submit", async event => {
      event.preventDefault();
      const sceneEvidence = scenes.flatMap(scene => scene.evidence).filter((id, index, ids) => ids.indexOf(id) === index);
      const chapterEvidence = Array.from(state.visitedChapters).flatMap(number => {
        const chapter = chapterConflictMap[number - 1];
        return chapter ? [...chapter.historicalEvidence, ...chapter.philosophyLens] : [];
      });
      const selectedEvidence = [...sceneEvidence, ...chapterEvidence].filter((id, index, ids) => ids.indexOf(id) === index);
      const reflectionText = document.getElementById("reflectionInput").value || "";
      const trajectorySummary = buildStanceTrajectorySummary();
      const choiceSummary = `五幕显影选择：\\n${buildChoiceSummary()}`;
      const chapterSummary = buildChapterVisitSummary();
      const lensSummary = buildLensVisitSummary();
      const response = await fetch(apiBase + "/judgment-cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_claim_ids: ["claim_conflict_is_moral_and_fiscal", "claim_power_network_not_optional"],
          selected_evidence_ids: selectedEvidence,
          personal_reflection: [trajectorySummary, choiceSummary, chapterSummary, lensSummary, reflectionText].filter(Boolean).join("\\n\\n") || null,
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
        "map-pressure": 82,
        "meeting-threshold": 112,
        "fiscal-pressure": 76,
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
      osc.type = kind === "power-shadow" || kind === "network" || kind === "fiscal-pressure" ? "sawtooth" : "sine";
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(kind === "evidence" ? 0.09 : kind === "power-shadow" ? 0.065 : 0.055, now + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + (kind === "power-shadow" ? 1.1 : 0.72));
      osc.connect(gain);
      gain.connect(master);
      osc.start(now);
      osc.stop(now + (kind === "power-shadow" ? 1.16 : 0.78));
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
        const phase = state.dramaPhase || "map-pressure";
        const phaseColors = {
          "map-pressure": ["#101820", "#172438", "#070a0f"],
          "meeting-threshold": ["#14171f", "#2a1f19", "#090d13"],
          "fiscal-pressure": ["#121926", "#27131a", "#070a0f"],
          "livelihood-counter": ["#0f1f21", "#123326", "#070a0f"],
          "power-shadow": ["#090d13", "#18080b", "#03060a"],
          "value-clash": ["#111927", "#1f1828", "#070a0f"]
        };
        const colors = phaseColors[phase] || phaseColors["map-pressure"];
        const gradient = context.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, colors[0]);
        gradient.addColorStop(0.52, colors[1]);
        gradient.addColorStop(1, colors[2]);
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
        context.globalAlpha = (phase === "power-shadow" ? 0.28 : 0.18) + Math.sin(state.animationTick * 4) * 0.04;
        context.fillStyle = phase === "livelihood-counter" ? "#2c7a66" : phase === "power-shadow" ? "#9a241c" : "#c49245";
        context.beginPath();
        context.arc(width * 0.74, height * 0.22, Math.min(width, height) * 0.18, 0, Math.PI * 2);
        context.fill();
        context.restore();

        context.save();
        context.globalAlpha = phase === "power-shadow" ? 0.3 : 0.2;
        context.strokeStyle = phase === "livelihood-counter" ? "#8ee0a8" : "#f3c46d";
        context.lineWidth = phase === "fiscal-pressure" ? 2 : 1;
        for (let i = 0; i < 9; i += 1) {
          const offset = (state.animationTick * 120 + i * 66) % (width + 160) - 80;
          const y = height * (0.18 + (i % 5) * 0.12);
          context.beginPath();
          context.moveTo(offset - 100, y + Math.sin(state.animationTick * 6 + i) * 22);
          context.lineTo(width * 0.52, height * 0.46);
          context.stroke();
        }
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
