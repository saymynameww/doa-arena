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
            data={chart.data as never}
            layout={
              {
                ...(chart.layout as Record<string, unknown>),
                autosize: true,
                height: style === "single" ? 360 : 500,
                font: { size: style === "web" ? 12 : 16 },
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
        <Tabs items={tabs} />
      </Card>
      {details && (
        <ResultTable data={details} point={point} onPoint={setPoint} />
      )}
    </>
  );
};

export default ResultCharts;
