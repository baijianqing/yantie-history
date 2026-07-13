#!/usr/bin/env node

import { createServer } from "node:http";
import { mkdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);

const scenarios = [
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
];

const viewports = [
  { name: "desktop", width: 1440, height: 960, reducedMotion: "no-preference" },
  { name: "mobile", width: 390, height: 844, reducedMotion: "no-preference" },
  { name: "reduced-motion", width: 390, height: 844, reducedMotion: "reduce" },
];

const mimeTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".mp3", "audio/mpeg"],
  [".png", "image/png"],
  [".svg", "image/svg+xml; charset=utf-8"],
]);

function parseArgs(argv) {
  const options = {
    baseUrl: "",
    root: "docs/yantie",
    port: 8765,
    headed: false,
    screenshotDir: "",
    screenshots: "",
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    const [name, inlineValue] = raw.split("=", 2);
    const value = inlineValue ?? argv[index + 1];
    const consumesValue = inlineValue == null && !["--headed", "--json"].includes(name);

    if (name === "--base-url") options.baseUrl = value;
    else if (name === "--root") options.root = value;
    else if (name === "--port") options.port = Number(value);
    else if (name === "--headed") options.headed = true;
    else if (name === "--screenshot-dir") options.screenshotDir = value;
    else if (name === "--screenshots") options.screenshots = value;
    else if (name === "--json") options.json = true;
    else if (name === "--help" || name === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${raw}`);
    }

    if (consumesValue) index += 1;
  }

  if (options.screenshotDir && !options.screenshots) options.screenshots = "all";
  if (!options.screenshots) options.screenshots = "none";
  if (!["none", "failures", "all"].includes(options.screenshots)) {
    throw new Error("--screenshots must be one of: none, failures, all");
  }
  return options;
}

function printHelp() {
  console.log(`Usage: node scripts/check-yantie-acceptance.mjs [options]

Options:
  --root <path>             Static yantie root. Default: docs/yantie
  --base-url <url>          Reuse an existing server instead of starting one.
  --port <number>           Local static server port. Default: 8765
  --headed                  Run Chromium headed.
  --screenshot-dir <path>   Save screenshots to this directory.
  --screenshots <mode>      none | failures | all. Defaults to all when --screenshot-dir is set.
  --json                    Emit a JSON report only.
`);
}

async function importPlaywright() {
  try {
    return require("playwright");
  } catch (error) {
    console.error("Playwright is required for yantie acceptance checks.");
    console.error("Install it in your Node environment, or run with the bundled workspace Node dependencies.");
    console.error(`Original error: ${error.message}`);
    process.exit(2);
  }
}

function startStaticServer(root, port) {
  const rootPath = path.resolve(root);
  const server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url || "/", `http://127.0.0.1:${port}`);
      let relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, "");
      if (!relativePath || relativePath.endsWith("/")) relativePath = path.join(relativePath, "index.html");
      const filePath = path.resolve(rootPath, relativePath);
      if (filePath !== rootPath && !filePath.startsWith(`${rootPath}${path.sep}`)) {
        response.writeHead(403);
        response.end("Forbidden");
        return;
      }
      const body = await readFile(filePath);
      response.writeHead(200, {
        "Content-Type": mimeTypes.get(path.extname(filePath).toLowerCase()) || "application/octet-stream",
      });
      response.end(body);
    } catch {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
    }
  });

  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      resolve({
        baseUrl: `http://127.0.0.1:${server.address().port}/`,
        close: () => new Promise(closeResolve => server.close(closeResolve)),
      });
    });
  });
}

function screenshotPath(options, viewport, scenario) {
  if (!options.screenshotDir) return "";
  mkdirSync(options.screenshotDir, { recursive: true });
  return path.join(options.screenshotDir, `${viewport.name}-${scenario}.png`);
}

function pageScenarioFor(scenario) {
  if (scenario === "material-guide" || scenario === "philosophy-lens") return "post-court-explorer";
  return scenario;
}

async function inspectScenario(page, scenario, viewport) {
  const pageScenario = pageScenarioFor(scenario);
  await page.goto(`${page.baseAcceptanceUrl}?acceptance=${pageScenario}`, { waitUntil: "load" });
  await page.waitForFunction(
    scenarioId => document.querySelector(".stage")?.dataset.acceptanceScenario === scenarioId,
    pageScenario,
    { timeout: 10000 },
  );
  if (
    scenario === "retirement-dossier" ||
    scenario === "post-court-explorer" ||
    scenario === "material-guide" ||
    scenario === "philosophy-lens"
  ) {
    await page.waitForFunction(
      () => Number(window.getComputedStyle(document.querySelector(".judgment-form")).opacity || "0") > 0.98,
      null,
      { timeout: 10000 },
    );
  }
  if (scenario === "material-guide") {
    await page.locator('[data-post-court-action="material-guide"]').click();
    await page.waitForFunction(
      () => {
        const panel = document.querySelector("#materialGuidePanel");
        if (!panel || panel.hidden) return false;
        const style = window.getComputedStyle(panel);
        const rect = panel.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      },
      null,
      { timeout: 10000 },
    );
  }
  if (scenario === "philosophy-lens") {
    await page.locator('[data-post-court-action="philosophy-lens"]').click();
    await page.waitForFunction(
      () => {
        const panel = document.querySelector("#philosophyLensPanel");
        if (!panel || panel.hidden) return false;
        const style = window.getComputedStyle(panel);
        const rect = panel.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      },
      null,
      { timeout: 10000 },
    );
  }

  return page.evaluate(({ scenario: scenarioId, pageScenario: pageScenarioId, viewport: viewportSpec }) => {
    function metrics(selector) {
      const node = document.querySelector(selector);
      if (!node) return { exists: false, visible: false, rect: null };
      const style = window.getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return {
        exists: true,
        visible: style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0,
        rect: {
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        },
      };
    }

    function overlaps(a, b) {
      if (!a || !b) return false;
      return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
    }

    const stage = document.querySelector(".stage");
    const advance = metrics("#advanceScene");
    const evidence = metrics("#evidenceRibbon");
    const dossier = metrics(".judgment-form");
    const debateHud = metrics("#debateHud");
    const judgmentBackdrop = metrics("#judgmentSvg");
    const judgmentBackdropOpacity = Number(
      window.getComputedStyle(document.querySelector("#judgmentSvg") || document.body).opacity || "1",
    );
    const postCourt = metrics("#postCourtExplorer");
    const materialGuide = metrics("#materialGuidePanel");
    const philosophyLens = metrics("#philosophyLensPanel");
    const details = document.querySelector("#postCourtExplorer details");
    const materialGuidePanel = document.querySelector("#materialGuidePanel");
    const materialCards = document.querySelectorAll("[data-material-guide-id]");
    const philosophyLensPanel = document.querySelector("#philosophyLensPanel");
    const lensTabs = document.querySelectorAll("[data-lens-group]");
    const lensButtons = document.querySelectorAll("[data-lens-evidence-id]");
    const failures = [];

    if (stage?.dataset.acceptanceScenario !== pageScenarioId) failures.push("wrong acceptance scenario");
    if (!(document.querySelector("#sceneTitle")?.textContent || "").trim()) failures.push("empty scene title");
    if (!advance.visible) failures.push("primary action hidden");

    if (scenarioId === "key-evidence") {
      if (!document.querySelector("#evidenceRibbon")?.classList.contains("is-open")) {
        failures.push("key evidence is not open");
      }
      if (!evidence.visible) failures.push("evidence drawer hidden");
    }

    if (scenarioId === "retirement-dossier" || scenarioId === "post-court-explorer") {
      if (!dossier.visible) failures.push("judgment form hidden");
      if (debateHud.visible) failures.push("debate HUD visible during judgment");
      if (overlaps(dossier.rect, debateHud.rect)) failures.push("dossier overlaps debate HUD");
      if (judgmentBackdrop.visible && judgmentBackdropOpacity > 0.45) {
        failures.push("judgment backdrop too prominent");
      }
    }

    if (scenarioId === "post-court-explorer" || scenarioId === "material-guide" || scenarioId === "philosophy-lens") {
      if (!postCourt.visible) failures.push("post-court explorer hidden");
      if (!details?.open) failures.push("post-court details not expanded");
    }

    if (scenarioId === "material-guide") {
      if (!materialGuide.visible) failures.push("material guide hidden");
      if (materialGuidePanel?.dataset.materialBoundary !== "post_court_only") {
        failures.push("material guide boundary missing");
      }
      if (materialCards.length < 1) failures.push("material guide has no cards");
    }

    if (scenarioId === "philosophy-lens") {
      if (!philosophyLens.visible) failures.push("philosophy lens panel hidden");
      if (philosophyLensPanel?.dataset.lensBoundary !== "philosophy_lens") {
        failures.push("philosophy lens boundary missing");
      }
      if (lensTabs.length < 4) failures.push("philosophy lens groups missing");
      if (!document.querySelector('[data-lens-group="huang_lao"]')) failures.push("huang lao lens group missing");
      if (!document.querySelector('[data-lens-group="classics_context"]')) {
        failures.push("classics context lens group missing");
      }
      if (lensButtons.length < 1) failures.push("philosophy lens has no evidence buttons");
    }

    return {
      viewport: viewportSpec.name,
      scenario: scenarioId,
      phase: stage?.dataset.experiencePhase || "",
      title: (document.querySelector("#sceneTitle")?.textContent || "").trim(),
      evidenceOpen: document.querySelector("#evidenceRibbon")?.classList.contains("is-open") || false,
      dossierVisible: dossier.visible,
      postCourtVisible: postCourt.visible,
      materialGuideVisible: materialGuide.visible,
      philosophyLensVisible: philosophyLens.visible,
      manualReview: scenarioId === "power-silence",
      failures,
    };
  }, { scenario, pageScenario, viewport });
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const { chromium } = await importPlaywright();
  const server = options.baseUrl ? null : await startStaticServer(options.root, options.port);
  const baseUrl = options.baseUrl || server.baseUrl;
  const browser = await chromium.launch({ headless: !options.headed });
  const results = [];
  const errors = [];

  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        reducedMotion: viewport.reducedMotion,
      });
      const page = await context.newPage();
      page.baseAcceptanceUrl = baseUrl;
      page.on("pageerror", error => errors.push(`${viewport.name}: ${error.message}`));
      page.on("console", message => {
        if (message.type() === "error") errors.push(`${viewport.name}: ${message.text()}`);
      });

      for (const scenario of scenarios) {
        const result = await inspectScenario(page, scenario, viewport);
        const shouldSave =
          options.screenshots === "all" ||
          (options.screenshots === "failures" && result.failures.length > 0);
        if (shouldSave) {
          result.screenshot = screenshotPath(options, viewport, scenario);
          await page.screenshot({ path: result.screenshot, fullPage: false });
        }
        results.push(result);
      }
      await context.close();
    }
  } finally {
    await browser.close();
    if (server) await server.close();
  }

  const failed = results.filter(result => result.failures.length > 0);
  const report = {
    total: results.length,
    passed: results.length - failed.length,
    failed,
    errors,
    manualReview: results.filter(result => result.manualReview).map(result => `${result.viewport}/${result.scenario}`),
  };

  if (options.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(`Yantie acceptance: ${report.passed}/${report.total} checks passed.`);
    if (report.manualReview.length) {
      console.log(`Manual review recommended: ${report.manualReview.join(", ")}`);
    }
    if (failed.length || errors.length) {
      console.error(JSON.stringify({ failed, errors }, null, 2));
    }
  }

  if (failed.length || errors.length) process.exit(1);
}

run().catch(error => {
  console.error(error);
  process.exit(1);
});
