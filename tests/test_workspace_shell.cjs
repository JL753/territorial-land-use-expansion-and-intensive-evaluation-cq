"use strict";
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

const root = path.resolve(__dirname, "..");
const pages = [
  "index.html",
  "dashboard3d.html",
  "city.html",
  "district.html",
  "data-center.html",
  "guide.html",
  "desktop.html",
  "mobile.html"
];

test("every web entry point loads the shared workspace assets", () => {
  for (const page of pages) {
    const html = fs.readFileSync(path.join(root, "web", page), "utf8");
    assert.match(html, /href="\/workspace\.css"/, page + " must load workspace.css");
    assert.match(html, /src="\/workspace\.js"/, page + " must load workspace.js");
  }
});

test("the home research tabs remain compatible with the existing app controller", () => {
  const shell = fs.readFileSync(path.join(root, "web", "workspace.js"), "utf8");
  const app = fs.readFileSync(path.join(root, "web", "app.js"), "utf8");
  assert.match(shell, /nav\[aria-label="主导航"\]/);
  assert.match(shell, /workspace-module-nav/);
  assert.match(app, /document\.querySelectorAll\("nav button"\)/);
  for (const key of ["overview", "lab", "relations", "analytics", "library", "assistant", "report"]) {
    assert.ok(shell.includes('data-page="' + key + '"') || app.includes('"' + key + '"'), "missing module " + key);
  }
});

test("the service worker precaches the shared shell and invalidates the previous cache", () => {
  const sw = fs.readFileSync(path.join(root, "web", "sw.js"), "utf8");
  assert.match(sw, /cq-land-study-v16/);
  assert.match(sw, /"\/workspace\.js"/);
  assert.match(sw, /"\/workspace\.css"/);
});

test("desktop and mobile clients retain their dedicated navigation layouts", () => {
  const shell = fs.readFileSync(path.join(root, "web", "workspace.js"), "utf8");
  const mobile = fs.readFileSync(path.join(root, "web", "mobile.html"), "utf8");
  const desktop = fs.readFileSync(path.join(root, "web", "desktop.html"), "utf8");
  assert.match(shell, /setupMobile/);
  assert.match(shell, /setupDesktop/);
  assert.match(mobile, /手机导航/);
  assert.match(desktop, /data-view="data"/);
});
