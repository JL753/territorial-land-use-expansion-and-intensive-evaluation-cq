const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const fs = require("node:fs");
const source = fs.readFileSync("web/analysis.js", "utf8");
const context = vm.createContext({});
vm.runInContext(source, context);
const records = JSON.parse(fs.readFileSync("results/socioeconomic/four-year-exploratory/dashboard.json"));

test("interactive TOPSIS reproduces the published four-year scores", () => {
  const result = context.evaluateRows(records);
  for (const row of result.rows) {
    assert.ok(Math.abs(row.score - row.intensive_score) < 1e-7);
    assert.equal(row.scenarioRank, row.rank);
  }
  assert.throws(() => context.evaluateRows(records, "custom", [0,0,0]));
});

test("native-grid transitions reproduce measured gains and losses", () => {
  for (const row of records.filter(r => r.interval_start)) {
    const matrix = row.transition_km2;
    const added = matrix.reduce((sum, from, i) => i === 7 ? sum : sum + from[7], 0);
    const lost = matrix[7].reduce((sum, to, i) => i === 7 ? sum : sum + to, 0);
    assert.ok(Math.abs(added - row.added_km2) < 1e-7);
    assert.ok(Math.abs(lost - row.lost_km2) < 1e-7);
  }
});

test("district comparisons and missing periods are explicit", () => {
  const answer = context.researchAnswer("2022年渝中区和涪陵区的单位用地GDP相差多少", records, 2010, "", "built_km2");
  assert.match(answer, /2022 年/);
  assert.match(answer, /差额/);
  assert.match(answer, /万元\/km²/);
  assert.match(context.researchAnswer("2024年谁最高", records, 2022, "", "built_km2"), /覆盖/);
});

test("derived indicators use the active denominator and preserve missing observations", () => {
  const enriched=context.enrichObservations(records);
  const row=enriched.find(r=>r.code==="500112"&&r.year===2022);
  assert.ok(Math.abs(row.built_person_m2-row.built_km2*1e6/row.population)<1e-9);
  assert.ok(Math.abs(row.expansion_cropland_share_pct-row.transition_km2[0][7]/row.added_km2*100)<1e-9);
  assert.ok(Math.abs(row.coverage_gap_pct-row.nodata_area_km2/(row.valid_area_km2+row.nodata_area_km2)*100)<1e-9);
  assert.equal(enriched.find(r=>r.year===2010).expansion_cropland_share_pct,null);
});
