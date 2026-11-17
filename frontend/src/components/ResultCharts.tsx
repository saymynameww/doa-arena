/* eslint-disable react-hooks/exhaustive-deps -- callbacks are local UI actions and dependencies are keyed by task id. */
import React, { useState, useEffect } from "react";
import {
  Card,
  Tabs,
  Spin,
  Empty,
  Button,
  Space,
  Dropdown,
  message,
  Alert,
  Checkbox,
  Select,
  Collapse,
  Input,
  InputNumber,
} from "antd";
import { DownloadOutlined, FullscreenOutlined } from "@ant-design/icons";
import Plot from "react-plotly.js";
import {
  downloadTaskExport,
  getTaskCharts,
  getResultDetails,
} from "@/services/api";
import type { ChartData } from "@/types";
import RecomputeMetrics from "./RecomputeMetrics";
import ResultTable from "./ResultTable";

interface ResultChartsProps {
  taskId: string;
  resultPath?: string;
  refreshKey?: string;
  canRecompute?: boolean;
}

/**
 * 结果图表组件
 *
 * 显示实验结果的交互式图表
 */
const ResultCharts: React.FC<ResultChartsProps> = ({
  taskId,
  resultPath,
  refreshKey,
  canRecompute = true,
}) => {
  const [loading, setLoading] = useState(false);
  const [charts, setCharts] = useState<ChartData[]>([]);
  const [point, setPoint] = useState<number>();
  const [details, setDetails] =
    useState<import("@/types/generated").ResultDetails>();
  const [logScale, setLogScale] = useState(false);
  const [style, setStyle] = useState("web");
  const [styleOptions, setStyleOptions] = useState<Record<string, any>>({});
  useEffect(() => {
    try { setStyleOptions(JSON.parse(localStorage.getItem(`arena.chartStyle.${taskId}`) || "{}")); } catch { setStyleOptions({}); }
  }, [taskId]);
  const updateStyle = (next: Record<string, any>) => {
    setStyleOptions(next);
    localStorage.setItem(`arena.chartStyle.${taskId}`, JSON.stringify(next));
  };

  useEffect(() => {
    if (resultPath) {
      loadCharts();
    }
  }, [resultPath, refreshKey]);

  const loadCharts = async () => {
    setLoading(true);
    try {
      const [charts, details] = await Promise.all([
        getTaskCharts(taskId),
        getResultDetails(taskId),
      ]);
      setCharts(charts);
      setDetails(details);
    } catch (error) {
      console.error("加载图表失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (
    format: string,
    title: string,
    metric?: string,
  ) => {
    const blob = await downloadTaskExport(taskId, format, {
      chart: title,
      metric,
      style,
      log: logScale,
      style_options: JSON.stringify(styleOptions),
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `experiment_${taskId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: "center", padding: "100px 0" }}>
          <Spin size="large" tip="加载图表中..." />
        </div>
      </Card>
    );
  }

  if (charts.length === 0) {
    return (
      <Card>
        <Empty description="暂无图表数据" />
      </Card>
    );
  }

  const single = details?.rows.some((r) => Array.isArray(r.angles));
  const tabs = charts
    .filter((chart) => !single || !chart.layout.meta)
    .map((chart, index) => ({
      key: String(index),
      label: chart.title,
      children: (
        <div>
          <div style={{ marginBottom: 16, textAlign: "right" }}>
            <Space>
              {!single && (
                <Checkbox
                  style={{ whiteSpace: "nowrap" }}
                  checked={logScale}
                  onChange={(e) => setLogScale(e.target.checked)}
                >
                  对数纵轴
                </Checkbox>
              )}
              <Select
                aria-label="图表样式"
                value={style}
                onChange={setStyle}
                options={[
                  { value: "web", label: "网页" },
                  { value: "single", label: "论文单栏" },
                  { value: "double", label: "论文双栏" },
                ]}
              />
              <Dropdown
                menu={{
                  items: [
                    "html",
                    "png",
                    "svg",
                    "pdf",
                    ...(chart.layout.meta ? ["csv", "tex"] : []),
                  ].map((format) => ({
                    key: format,
                    label: format.toUpperCase(),
                    onClick: () =>
                      void handleDownload(
                        format,
                        chart.title,
                        (chart.layout.meta as { metric?: string } | undefined)
                          ?.metric,
                      ).catch(() => message.error("图表导出失败")),
                  })),
                }}
              >
                <Button icon={<DownloadOutlined />}>导出图表</Button>
              </Dropdown>
              <Button
                icon={<FullscreenOutlined />}
                onClick={() =>
                  void document.documentElement.requestFullscreen?.()
                }
              >
                全屏
              </Button>
            </Space>
          </div>
          <Plot
            data={chart.data.map((trace: any) => {
              const custom = styleOptions.algorithms?.[trace.legendgroup || trace.name];
              if (!custom) return trace;
              const previous = trace.marker?.symbol;
              const symbol = custom.symbol;
              return { ...trace, line: { ...trace.line, ...(custom.color ? { color: custom.color } : {}), ...(custom.dash ? { dash: custom.dash } : {}) }, marker: { ...trace.marker, ...(custom.color ? { color: custom.color } : {}), ...(symbol ? { symbol: Array.isArray(previous) ? previous.map((s: string) => s.endsWith("-open") ? `${symbol}-open` : symbol) : symbol } : {}) } };
            }) as never}
            layout={
              {
                ...(chart.layout as Record<string, unknown>),
                autosize: true,
                height: style === "single" ? 360 : 500,
                font: { size: styleOptions.font_size || (style === "web" ? 12 : 16) },
                yaxis: {
                  ...(chart.layout.yaxis as object),
                  type: logScale ? "log" : "linear",
                },
              } as never
            }
            config={{
              displayModeBar: true,
              displaylogo: false,
              modeBarButtonsToRemove: ["lasso2d", "select2d"],
            }}
            style={{ width: "100%" }}
            useResizeHandler
            onClick={(event) => {
              if (!single)
                setPoint(
                  details?.rows.find((r) => r.x === event.points[0]?.x)
                    ?.point as number | undefined,
                );
            }}
          />
        </div>
      ),
    }));

  return (
    <>
      {!!details?.error_groups?.length && (
        <Card title="运行错误与完整堆栈" style={{ marginBottom: 16 }}>
          <p>失败试验会降低成功率；RMSE 是否纳入取决于配置中的失败处理口径。</p>
          <Collapse items={details.error_groups.flatMap((group: any, gi: number) =>
            group.errors.map((error: any, ei: number) => ({
              key: `${gi}-${ei}`,
              label: `${group.label} · ${error.type} · ${error.count} 次：${error.message}`,
              children: <><p>阶段：{group.stage}；首次出现在第 {Number(error.first_at.point) + 1} 个扫描点、第 {Number(error.first_at.trial) + 1} 次试验。</p>
                <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{error.traceback || "此错误由输出校验产生，无异常堆栈。"}</pre></>,
            })))}/>
        </Card>
      )}
      {(
        (details?.metadata.warnings || []) as Array<Record<string, unknown>>
      ).map((w, i) => (
        <Alert
          key={i}
          type="warning"
          showIcon
          message={`${w.algorithm || ""}：${w.message}`}
          style={{ marginBottom: 8 }}
        />
      ))}
      {details?.rows
        .filter((r) => (r.errors as string[])?.length)
        .map((r, i) => (
          <Alert
            key={`error-${i}`}
            type="error"
            showIcon
            message={`${r.algorithm} · 第 ${Number(r.point) + 1} 点：${(r.errors as string[]).length} 次失败，查看结果表错误列`}
            style={{ marginBottom: 8 }}
          />
        ))}
      <Card
        title="实验结果图表"
        extra={
          canRecompute && (
            <RecomputeMetrics
              taskId={taskId}
              onComplete={() => void loadCharts()}
            />
          )
        }
      >
        <Collapse style={{ marginBottom: 12 }} items={[{ key: "style", label: "自定义线型、标记、配色与字号", children: <Space direction="vertical" style={{ width: "100%" }}>
          <Space>字号 <InputNumber aria-label="图表字号" min={8} max={32} value={styleOptions.font_size || (style === "web" ? 12 : 16)} onChange={(v) => updateStyle({ ...styleOptions, font_size: v })} /><Button onClick={() => updateStyle({})}>恢复默认样式</Button></Space>
          {Array.from(new Map((details?.rows || []).map((r: any) => [r.algorithm, r])).values()).map((row: any) => {
            const value = { ...row.style, ...styleOptions.algorithms?.[row.algorithm] };
            const edit = (key: string, v: any) => updateStyle({ ...styleOptions, algorithms: { ...styleOptions.algorithms, [row.algorithm]: { ...styleOptions.algorithms?.[row.algorithm], [key]: v } } });
            return <Space wrap key={row.algorithm}><span>{row.algorithm}</span>
              <Input type="color" aria-label={`${row.algorithm}颜色`} style={{ width: 60 }} value={value.color} onChange={(e) => edit("color", e.target.value)} />
              <Select aria-label={`${row.algorithm}线型`} value={value.dash} onChange={(v) => edit("dash", v)} options={["solid", "dash", "dot", "dashdot"].map((v, i) => ({ value: v, label: ["实线", "虚线", "点线", "点划线"][i] }))} />
              <Select aria-label={`${row.algorithm}标记`} value={value.symbol} onChange={(v) => edit("symbol", v)} options={["circle", "square", "diamond", "triangle-up", "cross", "x"].map((v, i) => ({ value: v, label: ["圆", "方", "菱形", "三角", "十字", "叉"][i] }))} />
            </Space>;
          })}
        </Space> }]} />
        <Tabs items={tabs} />
      </Card>
      {details && (
        <ResultTable data={{ ...details, rows: details.rows.map((r: any) => ({ ...r, style: { ...r.style, ...styleOptions.algorithms?.[r.algorithm] } })) }} point={point} onPoint={setPoint} />
      )}
    </>
  );
};

export default ResultCharts;
