import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Dropdown,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Typography,
  message,
} from "antd";
import {
  createTemplate,
  getExperimentSchema,
  getScenarioPreview,
  getTemplates,
  runExperiment,
  validateExperiment,
} from "@/services/api";
import ConfigFields, {
  schemaDefault,
  type JsonSchema,
} from "@/components/ConfigFields";
import ScenePreview from "@/components/ScenePreview";

function mergeDefaults(defaults: any, value: any): any {
  if (value === undefined) return structuredClone(defaults);
  if (value === null || Array.isArray(value) || typeof value !== "object")
    return structuredClone(value);
  return Object.fromEntries(
    Object.keys({ ...defaults, ...value }).map((key) => [
      key,
      mergeDefaults(defaults?.[key], value[key]),
    ]),
  );
}

function parseRange(text: string): number[] {
  const parts = text.trim().split(":").map(Number);
  if (parts.length === 3) {
    const [start, step, stop] = parts;
    if (
      !parts.every(Number.isFinite) ||
      step === 0 ||
      (stop - start) / step < 0 ||
      Math.abs((stop - start) / step) > 10000
    )
      throw Error("扫描范围应为起点:步长:终点，步长须指向终点且最多 10001 点");
    return Array.from(
      { length: Math.floor((stop - start) / step + 1e-9) + 1 },
      (_, i) => Number((start + i * step).toPrecision(12)),
    );
  }
  const values = text
    .split(/[,，\s]+/)
    .filter(Boolean)
    .map(Number);
  if (values.length < 2 || !values.every(Number.isFinite))
    throw Error("请填写至少两个有限数值，或使用起点:步长:终点");
  return values;
}
const modes = [
  [
    "single",
    "单次实验",
    "生成一组数据，每个算法运行一次。看空间谱和估计角度。",
    "∿",
  ],
  [
    "monte_carlo",
    "蒙特卡罗",
    "场景固定，重复多次独立试验。看统计指标和估计值分布。",
    "⁙",
  ],
  [
    "sweep",
    "参数扫描",
    "让一个参数取多个值，每个值做一次蒙特卡罗。看指标变化曲线。",
    "↘",
  ],
];
export default function ExperimentConfigPage() {
  const [schema, setSchema] = useState<JsonSchema>();
  const [draft, setDraft] = useState<any>();
  const [templates, setTemplates] = useState<any[]>([]);
  const [range, setRange] = useState("-10:5:20");
  const [preview, setPreview] =
    useState<import("@/types/generated").ScenarioPreview>();
  const [busy, setBusy] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [templateKind, setTemplateKind] = useState<"scenario" | "experiment">(
    "experiment",
  );
  const [error, setError] = useState("");
  const [issues, setIssues] = useState<
    Array<{ level: string; message: string; algorithm?: string | null }>
  >([]);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  useEffect(() => {
    void Promise.all([getExperimentSchema(), getTemplates()])
      .then(([raw, list]) => {
        const data = raw as JsonSchema;
        setSchema(data);
        setTemplates(list);
        const template = list.find((t) => t.id === params.get("template"));
        let saved: any;
        try {
          saved = JSON.parse(
            sessionStorage.getItem("arena.experimentDraft") || "null",
          );
        } catch {
          saved = null;
        }
        const next =
          template?.kind === "scenario"
            ? {
                ...mergeDefaults(data["x-default"], saved?.draft),
                scenario: template.config?.scenario,
              }
            : mergeDefaults(
                data["x-default"],
                template?.config || saved?.draft,
              );
        if (
          template &&
          template.kind !== "scenario" &&
          !template.config?.algorithms?.length
        )
          next.algorithms = (template.algorithms || []).map((id: string) => {
            const plugin = data["x-algorithms"].find((a: any) => a.id === id);
            return {
              id,
              label: plugin?.name || id,
              enabled: true,
              params: plugin ? schemaDefault(plugin.schema, plugin.schema) : {},
            };
          });
        if (
          template &&
          template.kind !== "scenario" &&
          next.name === data["x-default"].name
        )
          next.name = template.name;
        next.metrics ||= data["x-default"].metrics;
        if (next.sweep && !next.sweep.label) {
          const spec = data["x-sweep-paths"].find(
            (s: any) => s.path === next.sweep.path,
          );
          next.sweep.label = spec?.label || next.sweep.path;
          next.sweep.unit = next.sweep.unit || spec?.unit || "";
        }
        const addition = sessionStorage.getItem("arena.addAlgorithm");
        const added = data["x-algorithms"].find((a: any) => a.id === addition);
        if (added) {
          next.algorithms.push({
            id: added.id,
            label: `${added.name} ${next.algorithms.length + 1}`,
            enabled: true,
            params: schemaDefault(added.schema, added.schema),
          });
          sessionStorage.removeItem("arena.addAlgorithm");
        }
        if (params.get("saveTemplate")) {
          setTemplateName(next.name);
          setTemplateOpen(true);
        }
        if (next.sweep) setRange(next.sweep.values.join(", "));
        if (!template && saved?.range) setRange(saved.range);
        setDraft(next);
      })
      .catch(() => setError("读取配置失败，请检查后端服务并刷新"));
  }, [params]);
  useEffect(() => {
    if (draft)
      sessionStorage.setItem(
        "arena.experimentDraft",
        JSON.stringify({ draft, range }),
      );
  }, [draft, range]);
  useEffect(() => {
    let current = true;
    setIssues([]);
    if (!draft?.algorithms?.some((a: any) => a.enabled !== false)) return;
    const timer = window.setTimeout(() => {
      try {
        if (draft.type === "sweep" && !draft.sweep?.path) return;
        const config = {
          ...draft,
          trials: draft.type === "single" ? 1 : draft.trials,
          sweep:
            draft.type === "sweep"
              ? { ...draft.sweep, values: parseRange(range) }
              : null,
        };
        void validateExperiment(config)
          .then((result) => {
            if (current) setIssues(result.issues);
          })
          .catch(() => {
            if (current)
              setIssues([
                {
                  level: "warning",
                  message: "暂时无法预检查配置，运行时会再次校验",
                },
              ]);
          });
      } catch {
        /* 范围编辑期间使用字段自身提示。 */
      }
    }, 500);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [draft, range]);
  useEffect(() => {
    let current = true;
    if (!draft?.scenario) return;
    const timer = window.setTimeout(() => {
      void getScenarioPreview(draft.scenario)
        .then((value) => {
          if (current) setPreview(value);
        })
        .catch(() => {
          if (current) setPreview(undefined);
        });
    }, 350);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [draft?.scenario]);
  if (!schema || !draft)
    return (
      <Alert
        type={error ? "error" : "info"}
        message={error || "读取配置 Schema…"}
      />
    );
  const update = (key: string, value: any) =>
    setDraft((d: any) => ({ ...d, [key]: value }));
  const scenario = draft.scenario;
  const setScenario = (key: string, value: any) =>
    update("scenario", { ...scenario, [key]: value });
  const active = draft.algorithms.filter((a: any) => a.enabled !== false);
  const arrays = schema["x-arrays"];
  const array = arrays.find((a: any) => a.id === scenario.array.type);
  const sweep = draft.type === "sweep" ? draft.sweep?.path : undefined;
  let values: number[] = [];
  let rangeError = "";
  if (draft.type === "sweep") {
    try {
      values = parseRange(range);
    } catch (e) {
      rangeError = (e as Error).message;
    }
  }
  const errors = [
    !active.length ? "至少启用一个算法" : "",
    draft.type === "sweep" && !sweep ? "请在数值字段旁选择扫描变量" : "",
    rangeError,
    ...issues
      .filter((issue) => issue.level === "error")
      .map((issue) => issue.message),
  ].filter(Boolean);
  const toggleSweep = (path: string, label: string) =>
    update(
      "sweep",
      sweep === path ? null : { path, label, unit: "", values: [] },
    );
  const fieldProps = {
    root: schema,
    sweep,
    sweepRange: range,
    onRange: setRange,
    onSweep: draft.type === "sweep" ? toggleSweep : undefined,
  };
  const build = () => ({
    ...draft,
    trials: draft.type === "single" ? 1 : draft.trials,
    sweep:
      draft.type === "sweep"
        ? { ...draft.sweep, values: parseRange(range) }
        : null,
  });
  const act = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e: any) {
      setError(
        typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : e.message || "操作失败",
      );
    } finally {
      setBusy(false);
    }
  };
  const exportConfig = (format: string) => {
    try {
      const json = JSON.stringify(build(), null, 2);
      const content =
        format === "json"
          ? json
          : `import json\nimport arena\nconfig = json.loads(${JSON.stringify(json)})\nif __name__ == "__main__":\n    result = arena.run(config)\n`;
      const url = URL.createObjectURL(
        new Blob([content], { type: "text/plain;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `experiment.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const editAlgorithm = (index: number, change: any) =>
    update(
      "algorithms",
      draft.algorithms.map((a: any, i: number) =>
        i === index ? { ...a, ...change } : a,
      ),
    );
  const sceneGroups = [
    {
      key: "array",
      label: "阵列",
      children: (
        <>
          <div className="schema-field">
            <label>阵列类型</label>
            <Select
              style={{ width: 200, maxWidth: "100%" }}
              value={scenario.array.type}
              options={arrays.map((a: any) => ({ value: a.id, label: a.name }))}
              onChange={(id) =>
                setScenario("array", {
                  type: id,
                  params: structuredClone(
                    arrays.find((a: any) => a.id === id).defaults,
                  ),
                })
              }
            />
          </div>
          <ConfigFields
            {...fieldProps}
            root={array.schema}
            schema={array.schema}
            value={scenario.array.params}
            path="scenario.array.params"
            onChange={(v) =>
              setScenario("array", { ...scenario.array, params: v })
            }
          />
          <ConfigFields
            root={schema}
            schema={{
              properties: {
                carrier_hz: schema.$defs.ArrayConfig.properties.carrier_hz,
              },
            }}
            value={scenario.array}
            path="scenario.array"
            onChange={(v) => setScenario("array", v)}
          />
          <Typography.Text className="physical-spacing-note" type="secondary">
            只用来显示物理间距
            {preview?.physical_spacing_cm != null
              ? `（当前 ${preview.physical_spacing_cm.toFixed(1)} cm）`
              : ""}
            ，不影响仿真
          </Typography.Text>
        </>
      ),
    },
    {
      key: "sources",
      label: "信源",
      children: (
        <>
          <ConfigFields
            {...fieldProps}
            schema={schema.$defs.SourcesConfig}
            value={scenario.sources}
            path="scenario.sources"
            onChange={(v) => setScenario("sources", v)}
          />
          <ConfigFields
            {...fieldProps}
            schema={{
              properties: {
                snapshots: schema.$defs.ScenarioConfig.properties.snapshots,
              },
            }}
            value={scenario}
            path="scenario"
            onChange={(v) => update("scenario", v)}
          />
        </>
      ),
    },
    {
      key: "impairments",
      label: "阵列误差",
      children: schema["x-impairments"].map((plugin: any) => {
        const index = scenario.impairments.findIndex(
          (x: any) => x.type === plugin.id,
        );
        const imp = scenario.impairments[index];
        return (
          <section className="impairment-section" key={plugin.id}>
            <Space>
              <Switch
                checked={!!imp?.enabled}
                onChange={(enabled) => {
                  const list = [...scenario.impairments];
                  if (index < 0)
                    list.push({
                      type: plugin.id,
                      enabled,
                      realization: "fixed",
                      params: structuredClone(plugin.defaults),
                    });
                  else list[index] = { ...imp, enabled };
                  setScenario("impairments", list);
                  if (
                    !enabled &&
                    sweep?.startsWith(`scenario.impairments[${index}]`)
                  )
                    update("sweep", null);
                }}
              />
              <strong>{plugin.name}</strong>
            </Space>
            {imp?.enabled && (
              <>
                <Select
                  aria-label={`${plugin.name}实现方式`}
                  value={imp.realization}
                  options={[
                    { value: "fixed", label: "固定" },
                    { value: "per_trial", label: "每次随机" },
                  ]}
                  onChange={(v) =>
                    setScenario(
                      "impairments",
                      scenario.impairments.map((x: any, i: number) =>
                        i === index ? { ...x, realization: v } : x,
                      ),
                    )
                  }
                />
                <ConfigFields
                  {...fieldProps}
                  root={plugin.schema}
                  schema={plugin.schema}
                  value={imp.params}
                  path={`scenario.impairments[${index}].params`}
                  onChange={(v) =>
                    setScenario(
                      "impairments",
                      scenario.impairments.map((x: any, i: number) =>
                        i === index ? { ...x, params: v } : x,
                      ),
                    )
                  }
                />
              </>
            )}
          </section>
        );
      }),
    },
    {
      key: "advanced",
      label: `高级 · 种子 ${scenario.seed}`,
      children: (
        <>
          <ConfigFields
            {...fieldProps}
            schema={{
              properties: {
                seed: schema.$defs.ScenarioConfig.properties.seed,
                noise_power: schema.$defs.ScenarioConfig.properties.noise_power,
              },
            }}
            value={scenario}
            path="scenario"
            onChange={(v) => update("scenario", v)}
          />
          <ConfigFields
            root={schema}
            schema={schema.$defs.ExperimentOptions}
            value={draft.options}
            path="options"
            onChange={(v) => update("options", v)}
          />
        </>
      ),
    },
  ];
  return (
    <div className="experiment-workbench">
      <header className="experiment-heading">
        <div className="experiment-heading-name">
          <Typography.Title level={3}>新建实验</Typography.Title>
          <Input
            aria-label="实验名称"
            value={draft.name}
            onChange={(e) => update("name", e.target.value)}
          />
        </div>
        <Space wrap>
          <Dropdown
            menu={{
              items: templates.map((t) => ({
                key: t.id,
                label: t.name,
                onClick: () =>
                  navigate(`/?template=${encodeURIComponent(t.id)}`),
              })),
            }}
          >
            <Button>从模板加载</Button>
          </Dropdown>
          <Button
            onClick={() => {
              setTemplateName(draft.name);
              setTemplateOpen(true);
            }}
          >
            保存为模板
          </Button>
          <Modal
            title="保存为模板"
            open={templateOpen}
            onCancel={() => setTemplateOpen(false)}
            okText="保存"
            cancelText="取消"
            onOk={() =>
              void act(async () => {
                if (!templateName.trim()) throw Error("请输入模板名称");
                await createTemplate({
                  name: templateName,
                  kind: templateKind,
                  type: draft.type,
                  algorithms: active.map((a: any) => a.id),
                  config: build(),
                });
                setTemplates(await getTemplates());
                setTemplateOpen(false);
                message.success("模板已保存");
              })
            }
          >
            <Space direction="vertical" style={{ width: "100%" }}>
              <Input
                aria-label="模板名称"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
              />
              <Select
                aria-label="模板类型"
                value={templateKind}
                onChange={setTemplateKind}
                style={{ width: "100%" }}
                options={[
                  {
                    value: "experiment",
                    label: "完整实验：场景、算法和运行设置",
                  },
                  {
                    value: "scenario",
                    label: "场景模板：加载时保留算法和运行设置",
                  },
                ]}
              />
            </Space>
          </Modal>
          <Dropdown
            menu={{
              items: ["json", "py"].map((format) => ({
                key: format,
                label: format.toUpperCase(),
                onClick: () => exportConfig(format),
              })),
            }}
          >
            <Button>导出 JSON / 脚本</Button>
          </Dropdown>
        </Space>
      </header>
      <Card className="experiment-mode-panel">
        <div
          className="experiment-modes"
          role="radiogroup"
          aria-label="实验方式"
        >
          {modes.map(([id, label, description]) => (
            <button
              key={id}
              type="button"
              className="mode-choice"
              role="radio"
              aria-checked={draft.type === id}
              onClick={() => update("type", id)}
            >
              <svg className="mode-icon" viewBox="0 0 48 40" aria-hidden="true">
                <path
                  d="M3 3 V35 H46"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                {id === "single" ? (
                  <path
                    d="M4 33 C18 33 17 7 23 7 C29 7 28 33 45 33"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                ) : id === "sweep" ? (
                  <path
                    d="M5 10 L16 17 L26 26 L35 30 L45 32"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                  />
                ) : (
                  <g fill="currentColor">
                    {[
                      [12, 30],
                      [20, 30],
                      [28, 30],
                      [36, 30],
                      [16, 23],
                      [24, 23],
                      [32, 23],
                      [20, 16],
                      [28, 16],
                      [24, 9],
                    ].map(([x, y]) => (
                      <circle key={`${x}-${y}`} cx={x} cy={y} r="2.5" />
                    ))}
                  </g>
                )}
              </svg>
              <strong>{label}</strong>
              <span>{description}</span>
            </button>
          ))}
        </div>
        <div className="experiment-settings">
          {draft.type === "sweep" && (
            <>
              <span>扫描变量</span>
              <Button
                type="link"
                onClick={() =>
                  document
                    .querySelector(`[aria-label="${sweep}"]`)
                    ?.scrollIntoView({ block: "center", behavior: "smooth" })
                }
              >
                {draft.sweep?.label || "在字段旁点扫描"}
              </Button>
              <Input
                aria-label="扫描取值"
                value={range}
                onChange={(e) => setRange(e.target.value)}
                placeholder="起:步长:止"
              />
              <span>{values.length} 个取值</span>
            </>
          )}
          {draft.type !== "single" && (
            <>
              <span>
                {draft.type === "sweep" ? "每点试验次数" : "试验次数"}
              </span>
              <InputNumber
                aria-label="试验次数"
                min={1}
                max={1000000}
                value={draft.trials}
                onChange={(v) => update("trials", v)}
              />
              <span>指标</span>
              {schema["x-metrics"].map((m: any) => (
                <Checkbox
                  key={m.id}
                  checked={draft.metrics.include.includes(m.id)}
                  onChange={(e) =>
                    update("metrics", {
                      ...draft.metrics,
                      include: e.target.checked
                        ? [...draft.metrics.include, m.id]
                        : draft.metrics.include.filter(
                            (id: string) => id !== m.id,
                          ),
                    })
                  }
                >
                  {m.name}
                </Checkbox>
              ))}
              <Space>
                <span>成功门限</span>
                <InputNumber
                  aria-label="成功门限"
                  min={0.001}
                  value={draft.metrics.params.success_rate.threshold_deg}
                  onChange={(v) =>
                    update("metrics", {
                      ...draft.metrics,
                      params: {
                        ...draft.metrics.params,
                        success_rate: { threshold_deg: v },
                      },
                    })
                  }
                />
                <span>°</span>
              </Space>
            </>
          )}
        </div>
      </Card>
      <div className="experiment-columns">
        <Card title="场景" className="experiment-scene">
          <Collapse
            ghost
            defaultActiveKey={["array", "sources", "impairments"]}
            items={sceneGroups}
          />
        </Card>
        <Card
          className="experiment-algorithms"
          title={
            <Space>
              算法{" "}
              <Typography.Text type="secondary">
                {active.length} 个参与
              </Typography.Text>
            </Space>
          }
          extra={
            <Select
              placeholder="+ 添加算法"
              value={undefined}
              style={{ width: 150 }}
              options={schema["x-algorithms"].map((a: any) => ({
                value: a.id,
                label: a.name,
              }))}
              onChange={(id) => {
                const a = schema["x-algorithms"].find((x: any) => x.id === id);
                update("algorithms", [
                  ...draft.algorithms,
                  {
                    id,
                    label: `${a.name}${draft.algorithms.some((x: any) => x.id === id) ? ` ${draft.algorithms.length + 1}` : ""}`,
                    enabled: true,
                    params: schemaDefault(a.schema, a.schema),
                  },
                ]);
              }}
            />
          }
        >
          {draft.algorithms.map((a: any, i: number) => {
            const plugin = schema["x-algorithms"].find(
              (x: any) => x.id === a.id,
            );
            return (
              <div
                className="algorithm-instance"
                key={i}
                style={{ opacity: a.enabled === false ? 0.5 : 1 }}
              >
                <div className="algorithm-toolbar">
                  <span
                    className="algorithm-swatch"
                    style={{
                      color: ["#1677ff", "#fa6432", "#00ad7c", "#e5a000"][
                        i % 4
                      ],
                    }}
                  >
                    ━●━
                  </span>
                  <Input
                    aria-label="算法显示名"
                    value={a.label}
                    onChange={(e) =>
                      editAlgorithm(i, { label: e.target.value })
                    }
                  />
                  <Button
                    aria-label="复制算法"
                    onClick={() =>
                      update("algorithms", [
                        ...draft.algorithms,
                        {
                          ...structuredClone(a),
                          label: `${a.label} 副本 ${draft.algorithms.length}`,
                        },
                      ])
                    }
                  >
                    复制
                  </Button>
                  <Button
                    aria-label="移除算法"
                    onClick={() => {
                      update(
                        "algorithms",
                        draft.algorithms.filter((_: any, j: number) => j !== i),
                      );
                      if (sweep?.startsWith("algorithms["))
                        update("sweep", null);
                    }}
                  >
                    ×
                  </Button>
                  <Switch
                    aria-label="参与本次实验"
                    checked={a.enabled !== false}
                    onChange={(v) => editAlgorithm(i, { enabled: v })}
                  />
                </div>
                {issues
                  .filter((issue) => issue.algorithm === a.label)
                  .map((issue, index) => (
                    <Alert
                      key={index}
                      type={issue.level === "error" ? "error" : "warning"}
                      showIcon
                      message={issue.message}
                    />
                  ))}
                <Collapse
                  ghost
                  items={[
                    {
                      key: "params",
                      label: Object.entries(a.params).some(
                        ([k, v]) =>
                          JSON.stringify(v) !==
                          JSON.stringify(
                            plugin?.schema?.properties?.[k]?.default,
                          ),
                      )
                        ? Object.entries(a.params)
                            .filter(
                              ([k, v]) =>
                                JSON.stringify(v) !==
                                JSON.stringify(
                                  plugin?.schema?.properties?.[k]?.default,
                                ),
                            )
                            .map(
                              ([k, v]) =>
                                `${plugin?.schema?.properties?.[k]?.label || plugin?.schema?.properties?.[k]?.title || k}: ${v === null ? "自动" : String(v)}`,
                            )
                            .join("，")
                        : "默认参数",
                      children: (
                        <ConfigFields
                          {...fieldProps}
                          root={plugin?.schema || schema}
                          schema={
                            plugin?.schema || {
                              properties: plugin?.params || {},
                            }
                          }
                          value={a.params}
                          path={`algorithms[${i}].params`}
                          onChange={(v) => editAlgorithm(i, { params: v })}
                        />
                      ),
                    },
                  ]}
                />
              </div>
            );
          })}
          <Typography.Text type="secondary">
            点卡片展开参数。比较同一算法的不同参数，可复制一份。
          </Typography.Text>
        </Card>
        <aside className="experiment-rail">
          <ScenePreview
            arraySize={preview?.elements || 0}
            sourceAngles={preview?.angles || []}
            sourceRanges={(preview?.ranges || []).map((r) => ({
              min: r.min,
              max: r.max,
            }))}
            faultyElements={preview?.faulty_elements || []}
            positions={preview?.positions || []}
          />
          <Card title="配置摘要" size="small">
            <dl className="summary-list">
              <dt>实验方式</dt>
              <dd>
                {modes.find((m) => m[0] === draft.type)?.[1]}
                {sweep && `：${draft.sweep.label}，${values.length} 个点`}
              </dd>
              <dt>阵列</dt>
              <dd>
                {array.name} ·{" "}
                {Object.entries(scenario.array.params)
                  .map(([k, v]) => `${k}=${v}`)
                  .join("，")}
              </dd>
              <dt>信源</dt>
              <dd>
                {typeof scenario.sources.K === "number"
                  ? scenario.sources.K
                  : `随机 ${scenario.sources.K.values.join("/")}`}{" "}
                个 ·{" "}
                {scenario.sources.angles.mode === "fixed"
                  ? `${scenario.sources.angles.values?.join("°、") || "默认"}°`
                  : schema.$defs.AnglesConfig.properties.mode["x-enum-labels"][
                      scenario.sources.angles.mode
                    ]}{" "}
                · 快拍数 {scenario.snapshots}
              </dd>
              <dt>阵列误差</dt>
              <dd>
                {scenario.impairments
                  .filter((x: any) => x.enabled)
                  .map(
                    (x: any) =>
                      schema["x-impairments"].find((p: any) => p.id === x.type)
                        ?.name,
                  )
                  .join("、") || "无"}
              </dd>
              <dt>算法</dt>
              <dd>{active.map((a: any) => a.label).join("、") || "未选择"}</dd>
              <dt>随机种子</dt>
              <dd>{scenario.seed}</dd>
            </dl>
          </Card>
        </aside>
      </div>
      {error && <Alert type="error" showIcon message={error} />}
      <div className="experiment-runbar">
        <div>
          {draft.type === "sweep" ? `${values.length} 个扫描点 × ` : ""}
          {draft.type === "single" ? 1 : draft.trials} 次试验 × {active.length}{" "}
          个算法，共{" "}
          {(draft.type === "sweep" ? values.length : 1) *
            (draft.type === "single" ? 1 : draft.trials) *
            active.length}{" "}
          次估计
          {errors.length > 0 && (
            <Typography.Text type="danger">
              {" "}
              · {errors.join("；")}
            </Typography.Text>
          )}
        </div>
        <Button
          type="primary"
          disabled={!!errors.length}
          loading={busy}
          onClick={() =>
            void act(async () => {
              const result = await runExperiment(build());
              navigate(`/runs/${result.task_id}`);
            })
          }
        >
          运行实验
        </Button>
      </div>
    </div>
  );
}
