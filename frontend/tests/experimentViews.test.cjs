const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const ts = require("typescript");
const vm = require("node:vm");
const source = fs.readFileSync("src/utils/experimentViews.ts", "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const exportsObject = {};
vm.runInNewContext(compiled, { exports: exportsObject });
const { compareReason, flattenConfig } = exportsObject;
const sweep = (path = "scenario.snapshots") => ({
  type: "sweep",
  has_results: true,
  config: { sweep: { path } },
});
test("比较限制：2–4 个、有结果、同一扫描变量", () => {
  assert.equal(compareReason([sweep(), sweep()]), "");
  assert.ok(compareReason([sweep()]));
  assert.ok(compareReason(Array.from({ length: 5 }, () => sweep())));
  assert.ok(compareReason([sweep(), sweep("other")]));
  assert.ok(compareReason([sweep(), { ...sweep(), has_results: false }]));
  assert.ok(compareReason([sweep(), { ...sweep(), type: "single" }]));
});
test("配置差异保留 0、false 和嵌套路径", () => {
  const flat = flattenConfig({
    scene: { seed: 0, flag: false, angles: [-10, 10] },
    trials: 500,
  });
  assert.equal(flat["scene.seed"], "0");
  assert.equal(flat["scene.flag"], "false");
  assert.equal(flat["scene.angles"], "[-10,10]");
});

test("策略摘要使用 Schema 标签，显式显示默认策略并隐藏内部兼容字段", () => {
  const schema = { properties: {
    strategy: { label: "寻峰策略", default: "none", "x-summary": true,
      "x-enum-labels": { none: "固定网格（无细化）", dense: "局部加密" } },
    spacing: { label: "局部步长", default: 0.0001, "x-summary": true,
      "x-visible-when": { strategy: "dense" } },
    internal: { "x-hidden": true, default: false },
  } };
  const summary = exportsObject.parameterSummary(schema, {strategy:"none",internal:true});
  assert.equal(summary, "寻峰策略: 固定网格（无细化）");
  assert.match(exportsObject.parameterSummary(schema, {strategy:"dense",spacing:0.0001}), /局部步长: 0.0001/);
});

test("对象数组按字段比较，代码补丁不吞没整组算法参数", () => {
  const flat = flattenConfig({ algorithms: [{ id: "a", params: { step: 1 }, origin: { patch: "diff" } }] });
  assert.equal(flat["algorithms.0.params.step"], "1");
  assert.equal(flat["algorithms.0.origin.patch"], '"diff"');
  assert.equal(flat.algorithms, undefined);
});

test("当前任务优先运行中；排队的同参数场景不能重复补跑", () => {
  const { currentTask, activeBenchmarkScene } = exportsObject;
  const queued = { task_id: "q", status: "queued" };
  const running = { task_id: "r", status: "running" };
  assert.equal(currentTask([queued, running]), running);
  const algorithm = { id: "a", params: { x: 1, y: 2 } };
  const record = { run_id: "new", algorithms: [algorithm], states: { failure: { status: "queued", experiment_id: "q" } } };
  assert.equal(activeBenchmarkScene([record], {id:"a",params:{y:2,x:1}}, "failure").experiment_id, "q");
  assert.equal(activeBenchmarkScene([record], {id:"a",params:{x:2}}, "failure"), undefined);
  assert.equal(activeBenchmarkScene([record], algorithm, "failure", "old"), undefined);
  record.states.failure.status = "completed";
  assert.equal(activeBenchmarkScene([record], algorithm, "failure"), undefined);
});
