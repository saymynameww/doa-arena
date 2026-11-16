import React, { useState } from 'react';
import { Card, Button, Space, Switch, Input, Tag, Tooltip } from 'antd';
import {
  DeleteOutlined,
  CopyOutlined,
  DownOutlined,
  UpOutlined,
} from '@ant-design/icons';
import SchemaForm from './SchemaForm';
import type { Algorithm, AlgorithmInstance } from '@/types';

interface AlgorithmCardProps {
  algorithm: Algorithm;
  instance: AlgorithmInstance;
  index: number;
  style?: React.CSSProperties;
  onLabelChange?: (index: number, label: string) => void;
  onParamsChange?: (index: number, params: Record<string, any>) => void;
  onRemove?: (index: number) => void;
  onCopy?: (index: number) => void;
  onToggle?: (index: number, enabled: boolean) => void;
}

/**
 * 算法卡片组件
 *
 * 支持：
 * - 样式色块（根据算法类型）
 * - 可编辑的显示名
 * - 参数展开/收起
 * - 参数摘要（显示非默认值）
 * - 复制、移除、启用/禁用
 */
const AlgorithmCard: React.FC<AlgorithmCardProps> = ({
  algorithm,
  instance,
  index,
  style = {},
  onLabelChange,
  onParamsChange,
  onRemove,
  onCopy,
  onToggle,
}) => {
  const [expanded, setExpanded] = useState(false);
  const enabled = instance.enabled !== false;

  // 算法类型对应的颜色
  const getAlgorithmColor = (type: string) => {
    const colors: Record<string, string> = {
      spectral: '#1890ff', // 蓝色
      subspace: '#52c41a', // 绿色
      learning: '#722ed1', // 紫色
      external: '#fa8c16', // 橙色
    };
    return colors[type] || '#8c8c8c';
  };

  // 算法类型对应的符号
  const getAlgorithmSymbol = (type: string) => {
    const symbols: Record<string, string> = {
      spectral: '●',
      subspace: '■',
      learning: '▲',
      external: '◆',
    };
    return symbols[type] || '○';
  };

  // 获取参数摘要（只显示非默认值的参数）
  const getParamsSummary = () => {
    const params = instance.params || {};
    const nonDefaultParams: string[] = [];

    Object.entries(params).forEach(([key, value]) => {
      const schema = algorithm.params[key];
      if (schema && value !== schema.default) {
        nonDefaultParams.push(`${key}: ${value}`);
      }
    });

    if (nonDefaultParams.length === 0) {
      return <span style={{ color: '#8c8c8c' }}>默认参数</span>;
    }

    return nonDefaultParams.join('，');
  };

  const handleToggle = (checked: boolean) => {
    onToggle?.(index, checked);
  };

  const color = getAlgorithmColor(algorithm.type);
  const symbol = getAlgorithmSymbol(algorithm.type);

  return (
    <Card
      size="small"
      style={{
        borderLeft: `4px solid ${color}`,
        opacity: enabled ? 1 : 0.6,
        ...style,
      }}
      bodyStyle={{ padding: '12px' }}
    >
      {/* 第一行：样式色块、显示名、操作按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <span
          style={{
            fontSize: 20,
            color,
            marginRight: 8,
            fontWeight: 'bold',
          }}
        >
          {symbol}
        </span>

        <Input
          value={instance.label ?? instance.id}
          onChange={(e) => onLabelChange?.(index, e.target.value)}
          bordered={false}
          style={{
            flex: 1,
            fontWeight: 'bold',
            fontSize: 14,
          }}
        />

        <Space>
          <Tooltip title="复制算法">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => onCopy?.(index)}
            />
          </Tooltip>

          <Tooltip title="移除算法">
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => onRemove?.(index)}
            />
          </Tooltip>

          <Switch
            size="small"
            checked={enabled}
            onChange={handleToggle}
          />

          <Button
            type="text"
            size="small"
            icon={expanded ? <UpOutlined /> : <DownOutlined />}
            onClick={() => setExpanded(!expanded)}
          />
        </Space>
      </div>

      {/* 第二行：参数摘要 */}
      <div
        style={{
          fontSize: 12,
          color: '#8c8c8c',
          marginLeft: 28,
        }}
      >
        {getParamsSummary()}
      </div>

      {/* 展开区域：参数表单 */}
      {expanded && (
        <div
          style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: '1px solid #f0f0f0',
          }}
        >
          {/* 算法信息 */}
          <div style={{ marginBottom: 12, fontSize: 12, color: '#8c8c8c' }}>
            <Space split="|">
              <span>ID: {algorithm.id}</span>
              <span>类型: {algorithm.type}</span>
              <Tag color="blue">内置</Tag>
            </Space>
          </div>

          {/* 参数表单 */}
          {Object.keys(algorithm.params).length > 0 ? (
            <SchemaForm
              schema={algorithm.params}
              values={instance.params || {}}
              onChange={(values) => onParamsChange?.(index, values)}
            />
          ) : (
            <div style={{ color: '#8c8c8c', textAlign: 'center', padding: 20 }}>
              该算法无可配置参数
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

export default AlgorithmCard;
