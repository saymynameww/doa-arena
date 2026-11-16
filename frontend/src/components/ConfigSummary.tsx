import React from 'react';
import { Card, Descriptions, Space, Tag } from 'antd';

interface ConfigSummaryProps {
  config?: {
    experimentType?: string;
    trials?: number;
    arraySize?: number;
    sourceCount?: number;
    snr?: number;
    algorithms?: string[];
    seed?: number;
  };
}

/**
 * 配置摘要组件
 *
 * 显示实验配置的关键信息摘要
 */
const ConfigSummary: React.FC<ConfigSummaryProps> = ({ config }) => {
  if (!config) {
    return (
      <Card title="配置摘要" size="small">
        <div style={{ color: '#8c8c8c', textAlign: 'center', padding: 20 }}>
          配置实验参数以查看摘要
        </div>
      </Card>
    );
  }

  const getExperimentTypeLabel = (type?: string) => {
    const types: Record<string, { label: string; color: string }> = {
      single: { label: '单次实验', color: 'blue' },
      monte_carlo: { label: '蒙特卡洛', color: 'green' },
      sweep: { label: '参数扫描', color: 'orange' },
    };
    return types[type || 'monte_carlo'] || types.monte_carlo;
  };

  const typeInfo = getExperimentTypeLabel(config.experimentType);

  return (
    <Card title="配置摘要" size="small">
      <Descriptions column={1} size="small">
        <Descriptions.Item label="实验方式">
          <Tag color={typeInfo.color}>{typeInfo.label}</Tag>
        </Descriptions.Item>

        {config.trials && (
          <Descriptions.Item label="试验次数">
            {config.trials}
          </Descriptions.Item>
        )}

        <Descriptions.Item label="阵列">
          ULA {config.arraySize || 16} 阵元
        </Descriptions.Item>

        <Descriptions.Item label="信源">
          {config.sourceCount || 2} 个信源
          {config.snr !== undefined && `, SNR = ${config.snr} dB`}
        </Descriptions.Item>

        <Descriptions.Item label="算法">
          {config.algorithms && config.algorithms.length > 0 ? (
            <Space direction="vertical" size={0}>
              {config.algorithms.map((algo, index) => (
                <Tag key={index}>{algo}</Tag>
              ))}
            </Space>
          ) : (
            <span style={{ color: '#8c8c8c' }}>未选择</span>
          )}
        </Descriptions.Item>

        {config.seed !== undefined && (
          <Descriptions.Item label="随机种子">
            {config.seed}
          </Descriptions.Item>
        )}
      </Descriptions>

      {/* 预估信息 */}
      {config.trials && config.algorithms && config.algorithms.length > 0 && (
        <div
          style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: '1px solid #f0f0f0',
            fontSize: 12,
            color: '#8c8c8c',
          }}
        >
          预计执行：
          {config.trials} 次试验 × {config.algorithms.length} 个算法 =
          {config.trials * config.algorithms.length} 次估计
        </div>
      )}
    </Card>
  );
};

export default ConfigSummary;
