import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Card,
  Select,
  Button,
  Space,
  Empty,
  Tabs,
  Table,
  Alert,
  Checkbox,
  Tag,
  Dropdown,
  message,
} from "antd";
import Plot from "react-plotly.js";
import { getTaskCharts, getTasks, downloadComparison } from "@/services/api";
import type { ChartData, Task } from "@/types";
import { compareReason, flattenConfig } from "@/utils/experimentViews";

const colors = [
  "#1677ff",
  "#fa8c16",
  "#13a86b",
  "#8b5cf6",
  "#e34b72",
  "#0891b2",
];
const dashes = ["solid", "dash", "dot", "dashdot"];
const symbols = ["circle", "square", "diamond", "triangle-up"];
const metricId = (c: ChartData) =>
  (c.layout.meta as { metric?: string })?.metric;
const ComparePage: React.FC = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [ids, setIds] = useState<string[]>(() =>
    (params.get("ids") || "").split(",").filter(Boolean),
  );
  const [charts, setCharts] = useState<Record<string, ChartData[]>>({});
  const [error, setError] = useState("");
  const [onlyDiff, setOnlyDiff] = useState(true);
  const [activeTab, setActiveTab] = useState<string>();
  const [log, setLog] = useState(false);
  const [point, setPoint] = useState<number | string>();
  useEffect(() => {
    void getTasks()
      .then(setTasks)
      .catch(() => setError("读取实验失败，请刷新重试"));
  }, []);
  const selected = ids
    .map((id) => tasks.find((t) => t.task_id === id))
    .filter(Boolean) as Task[];
  const reason = compareReason(selected);
  useEffect(() => {
    let current = true;
    setCharts({});
    setPoint(undefined);
    if (!reason)
      void Promise.all(
        ids.map(async (id) => [id, await getTaskCharts(id)] as const),
      )
        .then((entries) => {
          if (current) setCharts(Object.fromEntries(entries));
        })
        .catch(() => {
          if (current) setError("读取图表失败，请检查结果文件后刷新");
        });
    return () => {
      current = false;
    };
  }, [ids, reason]);
  const metrics = Array.from(
    new Map(
      Object.values(charts).flatMap((cs) =>
        cs.filter(metricId).map((c) => [metricId(c)!, c.title]),
      ),
    ),
  );
  const algorithms = Array.from(
    new Set(
      Object.values(charts).flatMap((cs) =>
        cs.flatMap((c) =>
          c.data
            .filter((t) => !String(t.name).startsWith("CRB"))
            .map((t) => String(t.name)),
        ),
      ),
    ),
  );
  const configs = selected.map((t) => flattenConfig(t.config));
  const rows = Array.from(new Set(configs.flatMap(Object.keys)))
    .map((field) => ({
      field,
      ...Object.fromEntries(configs.map((c, i) => [`e${i}`, c[field] || "—"])),
    }))
    .filter(
      (row) => !onlyDiff || new Set(configs.map((c) => c[row.field])).size > 1,
    );
  const tabs = metrics.map(([metric, title]) => {
    const base = Object.values(charts)
      .flat()
      .find((c) => metricId(c) === metric)!;
    const data = selected.flatMap((t, i) =>
      (charts[t.task_id]?.find((c) => metricId(c) === metric)?.data || []).map(
        (trace) => {
          const name = String(trace.name);
          const isCrb = name.startsWith("CRB");
          return {
            ...trace,
            x: trace.x,
            y: trace.y,
            name: `${name} · ${t.name || t.task_id}`,
            legendgroup: name,
            line: {
              ...(trace.line as object),
              color: isCrb
                ? "#334155"
                : colors[algorithms.indexOf(name) % colors.length],
              dash: dashes[i],
            },
            marker: { ...(trace.marker as object), symbol: symbols[i] },
            meta: { algorithm: name, experiment: t.task_id },
          };
        },
      ),
    );
    const x = point ?? (data[0]?.x as Array<number | string> | undefined)?.[0];
    const labels = Array.from(new Set(data.map((t) => t.meta.algorithm)));
    const table = labels.map((algorithm) => ({
      algorithm,
      ...Object.fromEntries(
        selected.map((t, i) => {
          const trace = data.find(
            (d) =>
              d.meta.algorithm === algorithm && d.meta.experiment === t.task_id,
          );
          const index = (trace?.x as unknown[] | undefined)?.indexOf(x) ?? -1;
          const value = (trace?.y as unknown[] | undefined)?.[index];
          return [
            `e${i}`,
            value == null
              ? "—"
              : typeof value === "number"
                ? value.toPrecision(5)
                : String(value),
          ];
        }),
      ),
    }));
    return {
      key: metric,
      label: title,
      children: (
        <>
          <Plot
            data={data as never}
            layout={
              {
                ...base.layout,
                autosize: true,
                height: 440,
                yaxis: {
                  ...(base.layout.yaxis as object),
                  type: log ? "log" : "linear",
                },
                margin: { b: 130 },
                legend: { orientation: "h", y: -0.3 },
              } as never
            }
            config={{ displaylogo: false, responsive: true }}
            useResizeHandler
            style={{ width: "100%" }}
            onClick={(e) => {
              const x = e.points[0]?.x;
              if (typeof x === "number" || typeof x === "string") setPoint(x);
            }}
          />
          <div>点击曲线查看该扫描点：{String(x ?? "—")}</div>
          <Table
            size="small"
            pagination={false}
            rowKey="algorithm"
            dataSource={table}
            columns={[
              { title: "算法 / 参考线", dataIndex: "algorithm" },
              ...selected.map((t, i) => ({
                title: t.name || t.task_id,
                dataIndex: `e${i}`,
              })),
            ]}
          />
        </>
      ),
    };
  });
  const differenceView = (
    <>
      <Checkbox
        checked={onlyDiff}
        onChange={(e) => setOnlyDiff(e.target.checked)}
      >
        只看差异
      </Checkbox>
      <Table
        style={{ marginTop: 12 }}
        rowKey="field"
        size="small"
        scroll={{ x: 900 }}
        pagination={false}
        dataSource={rows}
        columns={[
          { title: "配置字段", dataIndex: "field" },
          ...selected.map((t, i) => ({
            title: t.name || t.task_id,
            dataIndex: `e${i}`,
          })),
        ]}
      />
    </>
  );
  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Space>
        <Button onClick={() => navigate("/history")}>返回历史实验</Button>
        <h2 style={{ margin: 0 }}>多实验对比</h2>
      </Space>
      <Card title="选择实验（2–4 个，扫描变量一致）">
        <Space wrap>
          {selected.map((t, i) => (
            <Tag
              key={t.task_id}
              closable
              onClose={() => setIds(ids.filter((id) => id !== t.task_id))}
            >
              {["●", "■", "◆", "▲"][i]} · {t.name || t.task_id}
            </Tag>
          ))}
          <Select
            style={{ width: 320 }}
            placeholder="添加实验"
            value={undefined}
            disabled={ids.length >= 4}
            onChange={(id: string) => {
              setIds([...ids, id]);
              setError("");
            }}
            options={tasks
              .filter((t) => !ids.includes(t.task_id))
              .map((t) => {
                const why =
                  t.type !== "sweep"
                    ? "非参数扫描"
                    : !t.has_results
                      ? "暂无结果"
                      : selected.length &&
                          t.config.sweep?.path !==
                            selected[0].config.sweep?.path
                        ? "扫描变量不同"
                        : "";
                return {
                  value: t.task_id,
                  label: `${t.name || t.task_id}${why ? `（${why}）` : ""}`,
                  disabled: !!why,
                };
              })}
          />
        </Space>
        {reason && (
          <Alert style={{ marginTop: 12 }} type="info" message={reason} />
        )}
        {error && <Alert type="error" message={error} />}
      </Card>
      {!reason && <Card title="设置差异">{differenceView}</Card>}
      <Card
        title="对比结果"
        extra={
          <Space>
            <Checkbox checked={log} onChange={(e) => setLog(e.target.checked)}>
              对数纵轴
            </Checkbox>
            <Dropdown
              menu={{
                items: ["png", "svg", "pdf", "html"].map((format) => ({
                  key: format,
                  label: format.toUpperCase(),
                  onClick: () =>
                    void downloadComparison(
                      ids,
                      activeTab || metrics[0]?.[0] || "rmse",
                      format,
                      log,
                    )
                      .then((blob) => {
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `comparison.${format}`;
                        a.click();
                        URL.revokeObjectURL(url);
                      })
                      .catch(() =>
                        message.error("导出失败，请选择指标并检查结果文件"),
                      ),
                })),
              }}
            >
              <Button disabled={!!reason || activeTab === "settings"}>
                导出对比图
              </Button>
            </Dropdown>
          </Space>
        }
      >
        {reason ? (
          <Empty description={reason} />
        ) : (
          <>
            <Space wrap>
              <span>算法颜色：</span>
              {algorithms.map((a, i) => (
                <Tag key={a} color={colors[i % colors.length]}>
                  {a}
                </Tag>
              ))}
            </Space>
            <div style={{ margin: "12px 0" }}>
              实验线型：
              {selected.map((t, i) => (
                <span key={t.task_id} style={{ marginRight: 20 }}>
                  {["━ ●", "┄ ■", "┈ ◆", "┅ ▲"][i]} {t.name || t.task_id}
                </span>
              ))}
            </div>
            <Tabs
              activeKey={activeTab || metrics[0]?.[0] || "settings"}
              onChange={setActiveTab}
              items={tabs}
            />
          </>
        )}
      </Card>
    </Space>
  );
};
export default ComparePage;
