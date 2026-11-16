import React, { useState, useEffect } from 'react';
import { Alert, Button, Card, List, Tag, Space, Spin, message, Descriptions } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { getAlgorithms, refreshAlgorithms } from '@/services/api';
import type { Algorithm } from '@/types';
import ModelsPanel from '@/components/ModelsPanel';

const AlgorithmsPage: React.FC = () => {
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [loading, setLoading] = useState(false);
  const [failures, setFailures] = useState<any[]>([]);

  useEffect(() => {
    loadAlgorithms();
  }, []);

  const loadAlgorithms = async () => {
    try {
      setLoading(true);
      const data = await getAlgorithms();
      console.log('Loaded algorithms:', data);
      setAlgorithms(data);
    } catch (error: any) {
      console.error('Failed to load algorithms:', error);
      message.error('加载算法列表失败: ' + (error.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const data = await refreshAlgorithms();
      setAlgorithms(data.algorithms);
      setFailures(data.failures || []);
      message.success('算法库已刷新');
    } catch {
      message.error('刷新算法库失败');
    } finally {
      setLoading(false);
    }
  };

  const renderParams = (params: Record<string, any>) => {
    if (!params || Object.keys(params).length === 0) {
      return <span style={{ color: '#8c8c8c' }}>无参数</span>;
    }
    return Object.entries(params).map(([key, schema]) => (
      <Descriptions.Item key={key} label={key}>
        <Space>
          <Tag>{schema.type}</Tag>
          {schema.default !== undefined && schema.default !== null && (
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
    <>
    <Card title="算法库" extra={<Space><Tag color="blue">{algorithms.length} 个算法</Tag><Button icon={<ReloadOutlined />} onClick={() => void handleRefresh()}>刷新</Button></Space>}>
      {failures.length > 0 && <Alert type="warning" showIcon message="部分算法来源加载失败" description={failures.map((failure) => failure.message || String(failure)).join('；')} style={{ marginBottom: 16 }} />}
      {algorithms.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#8c8c8c' }}>
          暂无算法数据
        </div>
      ) : (
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
                  {algo.description || '暂无描述'}
                </div>
                <div>
                  <strong>ID：</strong>
                  <Tag>{algo.id}</Tag>
                </div>
                {algo.params && Object.keys(algo.params).length > 0 && (
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
      )}
    </Card>
    <ModelsPanel />
    </>
  );
};

export default AlgorithmsPage;
