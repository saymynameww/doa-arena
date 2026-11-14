import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Space, Spin, message, Descriptions } from 'antd';
import { getAlgorithms } from '@/services/api';
import type { Algorithm } from '@/types';

const AlgorithmsPage: React.FC = () => {
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAlgorithms();
  }, []);

  const loadAlgorithms = async () => {
    try {
      setLoading(true);
      const data = await getAlgorithms();
      setAlgorithms(data);
    } catch (error) {
      message.error('加载算法列表失败');
    } finally {
      setLoading(false);
    }
  };

  const renderParams = (params: Record<string, any>) => {
    return Object.entries(params).map(([key, schema]) => (
      <Descriptions.Item key={key} label={key}>
        <Space>
          <Tag>{schema.type}</Tag>
          {schema.default !== undefined && (
            <span>默认值: {String(schema.default)}</span>
          )}
          {schema.description && (
            <span style={{ color: '#8c8c8c' }}>({schema.description})</span>
          )}
        </Space>
      </Descriptions.Item>
    ));
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <Card title="算法库" extra={<Tag color="blue">{algorithms.length} 个算法</Tag>}>
      <List
        itemLayout="vertical"
        dataSource={algorithms}
        renderItem={(algo) => (
          <Card
            type="inner"
            title={
              <Space>
                <span>{algo.name}</span>
                <Tag color="blue">{algo.type}</Tag>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <strong>描述：</strong>
                {algo.description}
              </div>
              <div>
                <strong>ID：</strong>
                <Tag>{algo.id}</Tag>
              </div>
              {Object.keys(algo.params).length > 0 && (
                <div>
                  <strong>参数：</strong>
                  <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
                    {renderParams(algo.params)}
                  </Descriptions>
                </div>
              )}
            </Space>
          </Card>
        )}
      />
    </Card>
  );
};

export default AlgorithmsPage;
