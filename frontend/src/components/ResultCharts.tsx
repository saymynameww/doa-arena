import React, { useState, useEffect } from 'react';
import { Card, Tabs, Spin, Empty, Button, Space } from 'antd';
import { DownloadOutlined, FullscreenOutlined } from '@ant-design/icons';
import Plot from 'react-plotly.js';

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
  const [charts, setCharts] = useState<any[]>([]);

  useEffect(() => {
    if (resultPath) {
      loadCharts();
    }
  }, [resultPath]);

  const loadCharts = async () => {
    setLoading(true);
    try {
      // TODO: 从后端加载图表数据
      // 这里使用模拟数据
      const mockCharts = [
        {
          title: 'RMSE vs SNR',
          data: [
            {
              x: [0, 5, 10, 15, 20],
              y: [2.5, 1.8, 1.2, 0.8, 0.5],
              type: 'scatter',
              mode: 'lines+markers',
              name: 'MUSIC',
              line: { color: '#1890ff' },
            },
            {
              x: [0, 5, 10, 15, 20],
              y: [2.8, 2.0, 1.4, 0.9, 0.6],
              type: 'scatter',
              mode: 'lines+markers',
              name: 'ESPRIT',
              line: { color: '#52c41a' },
            },
            {
              x: [0, 5, 10, 15, 20],
              y: [1.5, 1.0, 0.7, 0.5, 0.3],
              type: 'scatter',
              mode: 'lines',
              name: 'CRB',
              line: { color: '#000', dash: 'dash' },
            },
          ],
          layout: {
            title: 'RMSE vs SNR',
            xaxis: { title: 'SNR (dB)' },
            yaxis: { title: 'RMSE (°)', type: 'log' },
            hovermode: 'closest',
          },
        },
        {
          title: '成功率 vs SNR',
          data: [
            {
              x: [0, 5, 10, 15, 20],
              y: [0.3, 0.5, 0.7, 0.9, 0.95],
              type: 'scatter',
              mode: 'lines+markers',
              name: 'MUSIC',
              line: { color: '#1890ff' },
            },
            {
              x: [0, 5, 10, 15, 20],
              y: [0.2, 0.4, 0.6, 0.85, 0.92],
              type: 'scatter',
              mode: 'lines+markers',
              name: 'ESPRIT',
              line: { color: '#52c41a' },
            },
          ],
          layout: {
            title: '成功率 vs SNR',
            xaxis: { title: 'SNR (dB)' },
            yaxis: { title: '成功率', range: [0, 1] },
            hovermode: 'closest',
          },
        },
        {
          title: '运行时间 vs SNR',
          data: [
            {
              x: [0, 5, 10, 15, 20],
              y: [12, 13, 14, 15, 16],
              type: 'bar',
              name: 'MUSIC',
              marker: { color: '#1890ff' },
            },
            {
              x: [0, 5, 10, 15, 20],
              y: [8, 9, 9, 10, 11],
              type: 'bar',
              name: 'ESPRIT',
              marker: { color: '#52c41a' },
            },
          ],
          layout: {
            title: '运行时间 vs SNR',
            xaxis: { title: 'SNR (dB)' },
            yaxis: { title: '时间 (ms)' },
            barmode: 'group',
          },
        },
      ];

      setCharts(mockCharts);
    } catch (error) {
      console.error('加载图表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (chart: any) => {
    // TODO: 实现图表下载
    console.log('下载图表:', chart.title);
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
            <Button
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(chart)}
            >
              下载
            </Button>
            <Button icon={<FullscreenOutlined />}>全屏</Button>
          </Space>
        </div>
        <Plot
          data={chart.data}
          layout={{
            ...chart.layout,
            autosize: true,
            height: 500,
          }}
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
    <Card title="实验结果图表">
      <Tabs items={tabs} />
    </Card>
  );
};

export default ResultCharts;
