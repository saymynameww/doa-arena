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

const draftExports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync("src/utils/draftRecovery.ts", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports: draftExports });
const { restoreExperimentDraft } = draftExports;
test("恢复扫描草稿：空 values 使用单独保存的 range，且不修改原草稿", async () => {
  const draft = { type: "sweep", sweep: { path: "scenario.sources.snr_db", values: [] } };
  let received;
  const result = await restoreExperimentDraft(draft, "-10:5:20", async (value) => {
    received = value; return value;
  });
  assert.equal(JSON.stringify(received.sweep.values), "[-10,-5,0,5,10,15,20]");
  assert.equal(draft.sweep.values.length, 0);
  assert.equal(result.issues.length, 0);
});
test("无效扫描输入恢复后仍可编辑，原始草稿和输入不丢失", async () => {
  const draft = { type: "sweep", sweep: { path: "scenario.sources.snr_db", values: [] } };
  const result = await restoreExperimentDraft(draft, "-10:0:20", async () => { throw Error("不应调用"); });
  assert.equal(result.draft, draft);
  assert.match(result.issues[0].message, /sweep.values/);
});
test("字段校验失败保留原值，显示具体字段；修正后可恢复", async () => {
  const draft = { type: "single", scenario: { snapshots: 0 }, algorithms: [{ params: { refine: true } }], schema_version: 1 };
  const normalize = async value => {
    if (!value.scenario.snapshots) throw { response: { data: { detail: { errors: [
      { path: "scenario.snapshots", message: "必须大于等于 1" },
    ] } } } };
    return value;
  };
  const result = await restoreExperimentDraft(draft, "", normalize);
  assert.equal(result.draft, draft);
  assert.equal(result.draft.algorithms[0].params.refine, true);
  assert.match(result.issues[0].message, /scenario.snapshots/);
  const fixed = await restoreExperimentDraft({ ...draft, scenario: { snapshots: 200 } }, "", normalize);
  assert.equal(fixed.issues.length, 0);
});
test("规范化服务断开也不丢弃草稿", async () => {
  const draft = { type: "single", name: "未完成实验" };
  const result = await restoreExperimentDraft(draft, "", async () => { throw Error("Network Error"); });
  assert.equal(result.draft, draft);
  assert.match(result.issues[0].message, /Network Error/);
});

const sweepExports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync("src/utils/sweepState.ts", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports: sweepExports });
const { selectSweepRange, restoreSweepRanges, removeAlgorithmRanges, sweepAvailable, activeSweepInfo } = sweepExports;
test("扫描切换使用各自预设，往返及取消重选保留用户输入", () => {
  const ranges = { snr: "-3:3:9" };
  assert.equal(selectSweepRange(ranges, "snapshots", {category:"scenario",default:"10,20,50"}), "10,20,50");
  ranges.snapshots = "32,64,128";
  assert.equal(selectSweepRange(ranges, "snr", {category:"scenario",default:"-10:5:20"}), "-3:3:9");
  assert.equal(selectSweepRange(ranges, "snapshots", {category:"scenario"}), "32,64,128");
  assert.equal(selectSweepRange({}, "plugin", {category:"algorithm"}), "");
  assert.equal(selectSweepRange({snr:""}, "snr", {category:"scenario",default:"-10:5:20"}), "");
});
test("多字段范围刷新恢复，兼容旧草稿且保留无效文本", async () => {
  const draft = {type:"sweep",sweep:{path:"snr",values:[]}};
  const ranges = restoreSweepRanges({range:"-10:0:20",sweepRanges:{snapshots:"20,40"}},draft);
  assert.equal(ranges.snapshots,"20,40"); assert.equal(ranges.snr,"-10:0:20");
  const restored = await restoreExperimentDraft(draft,ranges.snr,async value=>value);
  assert.equal(restored.draft,draft); assert.ok(restored.issues.length);
  const legacy = restoreSweepRanges({range:"-5:5:15"},draft);
  assert.equal(legacy.snr,"-5:5:15");
  const imported = restoreSweepRanges({range:"bad",sweepRanges:{snr:"bad"}},
    {sweep:{path:"snr",values:[0,5,10]}},false);
  assert.equal(imported.snr,"0, 5, 10");
});
test("扫描默认拒绝未声明字段，并遵守算法参数生效条件", () => {
  assert.equal(sweepAvailable(undefined,{}),false);
  const spec={category:"algorithm",when:{smoothing:["forward","fb"]}};
  assert.equal(sweepAvailable(spec,{smoothing:"none"}),false);
  assert.equal(sweepAvailable(spec,{smoothing:"fb"}),true);
});
test("删除算法后范围索引迁移，不串到另一个算法实例", () => {
  const result=removeAlgorithmRanges({"algorithms[0].params.grid_step":"0.1,1",
    "algorithms[1].params.grid_step":"0.2,0.5","scenario.snapshots":"10,20"},0);
  assert.equal(result["algorithms[0].params.grid_step"],"0.2,0.5");
  assert.equal(result["algorithms[1].params.grid_step"],undefined);
  assert.equal(result["scenario.snapshots"],"10,20");
});
test("活动扫描解析使用插件 Schema，关闭平滑后判定不生效", () => {
  const spec={category:"algorithm",when:{smoothing:["fb"]}};
  const schema={"x-algorithms":[{id:"test",schema:{properties:{subarray:{"x-sweep":spec}}}}]};
  const draft={sweep:{path:"algorithms[0].params.subarray"},algorithms:[{id:"test",params:{smoothing:"none"}}]};
  const info=activeSweepInfo(schema,draft);
  assert.equal(sweepAvailable(info.spec,info.values),false);
});


const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const previewModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync("src/components/ScenePreview.tsx", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
}).outputText, {
  exports: previewModule.exports,
  require: (name) => name === "antd" ? { Card: ({ children }) => React.createElement("div", null, children) } : require(name),
});
const renderPreview = (props) => renderToStaticMarkup(React.createElement(previewModule.exports.default, props));
test("场景预览显示搜索扇区，范围外信源保留并提示，边界属于范围内", () => {
  const html = renderPreview({ searchRange: { min: -10, max: 20 }, sourceAngles: [-30, -10, 20] });
  assert.match(html, /data-search-range/);
  assert.match(html, /统一搜索范围：-10°～20°/);
  assert.match(html, /范围外信源：-30°/);
  assert.doesNotMatch(html, /范围外信源：-30°、-10°/);
  assert.match(html, /黑线是信源方向：-30°、-10°、20°/);
});
test("随机角度范围无固定角度时也显示，并提示范围超出", () => {
  const html = renderPreview({ searchRange: { min: -10, max: 10 }, sourceAngles: [], sourceRanges: [{min: -30, max: 30}] });
  assert.match(html, /data-source-range/);
  assert.match(html, /随机角度范围超出统一搜索范围/);
});
test("完整范围无越界提示，无效搜索范围不绘制误导扇区", () => {
  const full = renderPreview({ searchRange: { min: -90, max: 90 }, sourceAngles: [-90, 90] });
  assert.doesNotMatch(full, /范围外信源/);
  for (const range of [{min: null,max: 90}, {min: 20,max: -20}, {min: -100,max: 20}]) {
    const html = renderPreview({ searchRange: range });
    assert.doesNotMatch(html, /data-search-range/);
    assert.match(html, /搜索范围无效/);
    assert.doesNotMatch(html, /NaN/);
  }
});
