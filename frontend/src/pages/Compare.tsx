import React, { useState } from 'react';
import { Card, Select, Button, Space, Row, Col, Empty, Tabs } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import Plot from 'react-plotly.js';

const { Option } = Select;

interface CompareExperiment {
  id: string;
  name: string;
  date: string;
}

/**
 * 多实验对比页
 *
 * 允许选择多个实验结果进行对比分析
 */
const ComparePage: React.FC = () => {
  const [selectedExperiments, setSelectedExperiments] = useState<string[]>([]);
  const [availableExperiments] = useState<CompareExperiment[]>([
    { id: '1', name: 'MUSIC vs ESPRIT 对比', date: '2026-11-15' },
    { id: '2', name: 'SNR 扫描实验', date: '2026-11-14' },
    { id: '3', name: '相干信源测试', date: '2026-11-13' },
  ]);

  const handleAddExperiment = (id: string) => {
    if (!selectedExperiments.includes(id)) {
      setSelectedExperiments([...selectedExperiments, id]);
    }
  };

  const handleRemoveExperiment = (id: string) => {
    setSelectedExperiments(selectedExperiments.filter((expId) => expId !== id));
  };

  // 模拟对比数据
  const generateCompareChart = () => {
    const colors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1'];

    const data = selectedExperiments.map((expId, index) => {
      const exp = availableExperiments.find((e) => e.id === expId);
      return {
        x: [0, 5, 10, 15, 20],
        y: [
          2.5 - index * 0.3,
          1.8 - index * 0.2,
          1.2 - index * 0.15,
          0.8 - index * 0.1,
          0.5 - index * 0.05,
        ],
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: exp?.name || `实验 ${expId}`,
        line: { color: colors[index % colors.length] },
      };
    });

    return {
      data,
      layout: {
        title: 'RMSE 对比',
        xaxis: { title: 'SNR (dB)' },
        yaxis: { title: 'RMSE (°)', type: 'log' as const },
        hovermode: 'closest' as const,
        height: 500,
      },
    };
  };

  const renderCompareView = () => {
    if (selectedExperiments.length === 0) {
      return (
        <Empty
          description="请至少选择一个实验进行对比"
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
            data={chart.data}
            layout={chart.layout}
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
        children: (
          <div style={{ textAlign: 'center', padding: 100, color: '#8c8c8c' }}>
            成功率对比图表（待实现）
          </div>
        ),
      },
      {
        key: 'time',
        label: '运行时间',
        children: (
          <div style={{ textAlign: 'center', padding: 100, color: '#8c8c8c' }}>
            运行时间对比图表（待实现）
          </div>
        ),
      },
    ];

    return <Tabs items={tabs} />;
  };

  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card title="选择实验" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Select
              placeholder="添加实验"
              style={{ width: '100%' }}
              onSelect={handleAddExperiment}
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
