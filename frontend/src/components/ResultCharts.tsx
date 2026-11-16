/* eslint-disable react-hooks/exhaustive-deps -- callbacks are local UI actions and dependencies are keyed by task id. */
import React, { useState, useEffect } from 'react';
import { Card, Tabs, Spin, Empty, Button, Space, Dropdown, message } from 'antd';
import { DownloadOutlined, FullscreenOutlined } from '@ant-design/icons';
import Plot from 'react-plotly.js';
import { downloadTaskExport, getTaskCharts } from '@/services/api';
import type { ChartData } from '@/types';
import RecomputeMetrics from './RecomputeMetrics';

interface ResultChartsProps {
  taskId: string;
  resultPath?: string;
}

/**
 * 结果图表组件
 *
 * 显示实验结果的交互式图表
 */
const ResultCharts: React.FC<ResultChartsProps> = ({ taskId, resultPath }) => {
  const [loading, setLoading] = useState(false);
  const [charts, setCharts] = useState<ChartData[]>([]);

  useEffect(() => {
    if (resultPath) {
      loadCharts();
    }
  }, [resultPath]);

  const loadCharts = async () => {
    setLoading(true);
    try {
      setCharts(await getTaskCharts(taskId));
    } catch (error) {
      console.error('加载图表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (format: string) => {
    const blob = await downloadTaskExport(taskId, format);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `experiment_${taskId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
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

  const tabs = charts.map((chart, index) => ({
    key: String(index),
    label: chart.title,
    children: (
      <div>
        <div style={{ marginBottom: 16, textAlign: 'right' }}>
          <Space>
            <Dropdown
              menu={{
                items: ['html', 'png', 'svg', 'pdf'].map((format) => ({
                  key: format,
                  label: format.toUpperCase(),
                  onClick: () =>
                    void handleDownload(format).catch(() => message.error('图表导出失败')),
                })),
              }}
            >
              <Button icon={<DownloadOutlined />}>导出图表</Button>
            </Dropdown>
            <Button
              icon={<FullscreenOutlined />}
              onClick={() => void document.documentElement.requestFullscreen?.()}
            >
              全屏
            </Button>
          </Space>
        </div>
        <Plot
          data={chart.data as never}
          layout={{
            ...(chart.layout as Record<string, unknown>),
            autosize: true,
            height: 500,
          } as never}
          config={{
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          }}
          style={{ width: '100%' }}
        />
      </div>
    ),
  }));

  return (
    <Card title="实验结果图表" extra={<RecomputeMetrics taskId={taskId} onComplete={() => void loadCharts()} />}>
      <Tabs items={tabs} />
    </Card>
  );
};

export default ResultCharts;
