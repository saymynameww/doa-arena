import {
  Card,
  Collapse,
  Descriptions,
  Table,
  Tag,
  Progress,
  Select,
  Space,
  Button,
  message,
} from "antd";
import type { ResultDetails } from "@/types/generated";
import AlgorithmSwatch from "./AlgorithmSwatch";

export default function ResultTable({
  data,
  point,
  onPoint,
}: {
  data: ResultDetails;
  point?: number;
  onPoint: (point: number) => void;
}) {
  const meta = data.metadata as Record<string, any>;
  const points = Array.from(
    new Map(data.rows.map((r) => [Number(r.point), r.x])),
  );
  const selected = point ?? points[0]?.[0];
  const rows = data.rows.filter((r) => r.point === selected) as Array<
    Record<string, any>
  >;
  const single = rows.some((r) => r.angles);
  const number = (v: unknown) =>
    typeof v === "number" ? v.toPrecision(5) : "—";
  const visibleColumns = data.columns.filter(
    (c) => !single || ["time", "success_rate"].includes(c.key),
  );
  const copyRows = [
    [
      "算法",
      ...(single ? ["估计角度 (°)", "最大误差 (°)"] : []),
      ...visibleColumns.map((c) => c.label),
    ].join("\t"),
    ...rows.map((r) =>
      [
        r.algorithm,
        ...(single
          ? [(r.angles || []).map(number).join(", "), number(r.max_error)]
          : []),
        ...visibleColumns.map((c) => number(r.metrics[c.key])),
      ].join("\t"),
    ),
  ].join("\n");
  return (
    <>
      <Card
        title={single ? "估计结果" : "结果表"}
        extra={
          <Space>
            <Button
              onClick={() =>
                void navigator.clipboard
                  .writeText(copyRows)
                  .then(() => message.success("表格已复制"))
              }
            >
              复制表格
            </Button>
            {points.length > 1 && (
              <>
                <Button
                  disabled={selected === points[0]?.[0]}
                  onClick={() => onPoint(selected! - 1)}
                >
                  ‹
                </Button>
                <Button
                  disabled={selected === points[points.length - 1]?.[0]}
                  onClick={() => onPoint(selected! + 1)}
                >
                  ›
                </Button>
                扫描点
                <Select
                  aria-label="结果表扫描点"
                  value={selected}
                  onChange={onPoint}
                  options={points.map(([value, x]) => ({
                    value,
                    label: `${value + 1} · ${x ?? "单场景"}`,
                  }))}
                  style={{ minWidth: 160 }}
                />
              </>
            )}
          </Space>
        }
      >
        <Table
          size="small"
          rowKey="algorithm"
          scroll={{ x: single ? 600 : 900 }}
          pagination={false}
          dataSource={rows}
          columns={[
            { title: "算法", dataIndex: "algorithm", render: (v, r) => <><AlgorithmSwatch visual={r.style} /> {v}</> },
            ...(rows.some((r) => r.angles)
              ? [
                  {
                    title: "估计角度 (°)",
                    dataIndex: "angles",
                    render: (v: number[]) => v?.map(number).join(", "),
                  },
                  {
                    title: "最大误差 (°)",
                    dataIndex: "max_error",
                    render: number,
                  },
                ]
              : []),
            ...visibleColumns.map((c) => ({
              title: `${c.label}${c.unit ? ` (${c.unit})` : ""}`,
              sorter: (a: Record<string, any>, b: Record<string, any>) =>
                (a.metrics[c.key] ?? Infinity) - (b.metrics[c.key] ?? Infinity),
              render: (_: unknown, r: Record<string, any>) => (
                <span
                  style={{ fontWeight: r.best?.includes(c.key) ? 700 : 400 }}
                >
                  {number(r.metrics[c.key])}
                </span>
              ),
            })),
            ...(!single
              ? [
                  { title: "√CRB (°)", dataIndex: "crb", render: number },
                  {
                    title: "RMSE / √CRB",
                    dataIndex: "efficiency",
                    render: number,
                  },
                  {
                    title: "有效次数",
                    render: (_: unknown, r: Record<string, any>) => (
                      <div style={{ minWidth: 110 }}>
                        {r.n_used ?? "—"} / {r.n_total}
                        <Progress
                          percent={
                            r.n_total ? (100 * (r.n_used || 0)) / r.n_total : 0
                          }
                          showInfo={false}
                          strokeColor={
                            r.n_used < 0.8 * r.n_total ? "#faad14" : undefined
                          }
                        />
                      </div>
                    ),
                  },
                ]
              : []),
            {
              title: "错误",
              render: (_: unknown, r: Record<string, any>) =>
                r.errors.length ? (
                  <details>
                    <summary>
                      <Tag color="error">{r.errors.length} 次</Tag>
                    </summary>
                    {Array.from(new Set(r.errors)).map((e, i) => (
                      <div key={i}>{String(e)}</div>
                    ))}
                  </details>
                ) : (
                  <Tag color="success">无</Tag>
                ),
            },
          ]}
        />
      </Card>
      <Collapse
        style={{ marginTop: 16 }}
        items={[
          {
            key: "provenance",
            label: "版本与复现信息",
            children: (
              <>
                <Descriptions size="small" column={3}>
                  {Object.entries({
                    ...meta.versions,
                    ...meta.environment,
                    mode: meta.mode,
                    config_hash: meta.config_hash,
                  }).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>
                      {String(v ?? "未记录")}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
                <pre
                  style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                >
                  {JSON.stringify(meta.plugins, null, 2)}
                </pre>
              </>
            ),
          },
        ]}
      />
    </>
  );
}
