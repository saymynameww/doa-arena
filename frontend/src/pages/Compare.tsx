import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Select, Button, Space, Row, Col, Empty, Tabs, Table } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import Plot from 'react-plotly.js';
import { getTaskCharts, getTasks } from '@/services/api';
import type { ChartData } from '@/types';

const { Option } = Select;

interface CompareExperiment {
  id: string;
  name: string;
  date: string;
  config?: Record<string, any>;
}

/**
 * 多实验对比页
 *
 * 允许选择多个实验结果进行对比分析
 */
const ComparePage: React.FC = () => {
  const [selectedExperiments, setSelectedExperiments] = useState<string[]>([]);
  const [availableExperiments, setAvailableExperiments] = useState<CompareExperiment[]>([]);
  const [chartsByExperiment, setChartsByExperiment] = useState<Record<string, ChartData[]>>({});
  const [searchParams] = useSearchParams();

  useEffect(() => {
    void getTasks()
      .then((tasks) => {
        setAvailableExperiments(
          tasks
            .filter((task) => task.status === 'completed')
            .map((task) => ({
              id: task.task_id,
              name: task.name || `实验 ${task.task_id}`,
              date: new Date(task.created_at * 1000).toLocaleString('zh-CN'),
              config: task.config,
            }))
        );
      })
      .catch(() => setAvailableExperiments([]));
  }, []);

  useEffect(() => {
    const ids = (searchParams.get('ids') || '').split(',').filter(Boolean);
    if (ids.length > 0) setSelectedExperiments(ids.slice(0, 4));
  }, [searchParams]);

  useEffect(() => {
    void Promise.all(selectedExperiments.map(async (id) => [id, await getTaskCharts(id)] as const))
      .then((entries) => setChartsByExperiment(Object.fromEntries(entries)))
      .catch(() => setChartsByExperiment({}));
  }, [selectedExperiments]);

  const handleAddExperiment = (id: string | undefined) => {
    if (!id) return;
    if (!selectedExperiments.includes(id)) {
      setSelectedExperiments([...selectedExperiments, id]);
    }
  };

  const handleRemoveExperiment = (id: string) => {
    setSelectedExperiments(selectedExperiments.filter((expId) => expId !== id));
  };

  const generateCompareChart = () => {
    const data = selectedExperiments.flatMap((expId) => {
      const exp = availableExperiments.find((e) => e.id === expId);
      const chart = chartsByExperiment[expId]?.[0];
      return (chart?.data || []).map((trace) => ({ ...trace, name: `${exp?.name || expId} / ${trace.name || ''}` }));
    });

    return {
      data,
      layout: {
        title: { text: 'RMSE 对比' },
        xaxis: { title: 'SNR (dB)' },
        yaxis: { title: 'RMSE (°)', type: 'log' as const },
        hovermode: 'closest' as const,
        height: 500,
      },
    };
  };

  const renderCompareView = () => {
    if (selectedExperiments.length < 2) {
      return (
        <Empty
          description="请从历史实验页选择至少两个参数扫描实验进行对比"
          style={{ marginTop: 100 }}
        />
      );
    }

    const chart = generateCompareChart();

    const tabs = [
      {
        key: 'rmse',
        label: 'RMSE',
        children: (
          <Plot
            data={chart.data as never}
            layout={chart.layout as never}
            config={{
              displayModeBar: true,
              displaylogo: false,
            }}
            style={{ width: '100%' }}
          />
        ),
      },
      {
        key: 'success',
        label: '成功率',
        children: <Plot data={selectedExperiments.flatMap((id) => (chartsByExperiment[id]?.[1]?.data || [])) as never} layout={{ title: { text: '成功率对比' }, height: 500 } as never} />,
      },
      {
        key: 'time',
        label: '运行时间',
        children: <Plot data={selectedExperiments.flatMap((id) => (chartsByExperiment[id]?.[2]?.data || [])) as never} layout={{ title: { text: '运行时间对比' }, height: 500 } as never} />,
      },
    ];

    const selected = selectedExperiments.map((id) => availableExperiments.find((item) => item.id === id)).filter(Boolean) as CompareExperiment[];
    const keys = Array.from(new Set(selected.flatMap((item) => Object.keys(item.config || {}))));
    const settings = keys.map((key) => ({ key, field: key, ...Object.fromEntries(selected.map((item, index) => [`exp${index}`, JSON.stringify(item.config?.[key] ?? '')])) }));
    return <Tabs items={[...tabs, { key: 'settings', label: '设置差异', children: <Table size="small" pagination={false} dataSource={settings} columns={[{ title: '字段', dataIndex: 'field' }, ...selected.map((item, index) => ({ title: item.name, dataIndex: `exp${index}` }))]} /> }]} />;
  };

  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card title="选择实验" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Select
              placeholder="添加实验"
              style={{ width: '100%' }}
            onSelect={(id: string | undefined) => handleAddExperiment(id)}
              value={undefined}
            >
              {availableExperiments
                .filter((exp) => !selectedExperiments.includes(exp.id))
                .map((exp) => (
                  <Option key={exp.id} value={exp.id}>
                    <div>
                      <div>{exp.name}</div>
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                        {exp.date}
                      </div>
                    </div>
                  </Option>
                ))}
            </Select>

            <div style={{ marginTop: 16 }}>
              <div
                style={{
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 8,
                }}
              >
                已选实验（{selectedExperiments.length}）
              </div>
              <Space direction="vertical" style={{ width: '100%' }}>
                {selectedExperiments.map((expId) => {
                  const exp = availableExperiments.find((e) => e.id === expId);
                  return (
                    <Card
                      key={expId}
                      size="small"
                      bodyStyle={{ padding: 8 }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 12 }}>{exp?.name}</div>
                          <div
                            style={{ fontSize: 11, color: '#8c8c8c' }}
                          >
                            {exp?.date}
                          </div>
                        </div>
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveExperiment(expId)}
                        />
                      </div>
                    </Card>
                  );
                })}
              </Space>
            </div>
          </Space>
        </Card>
      </Col>

      <Col span={18}>
        <Card title="对比分析">{renderCompareView()}</Card>
      </Col>
    </Row>
  );
};

export default ComparePage;
