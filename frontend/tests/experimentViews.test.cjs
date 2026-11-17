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
