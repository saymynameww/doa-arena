import React, { useState } from 'react';
import { Space, Button, InputNumber, Input, Typography, Tooltip } from 'antd';
import { SwapOutlined, CloseOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface SweepableFieldProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onEnableSweep?: (sweepConfig: { start: number; stop: number; step: number }) => void;
  isSweeping?: boolean;
  sweepConfig?: { start: number; stop: number; step: number };
}

/**
 * 可扫描字段组件
 *
 * 支持单值和扫描范围切换
 */
export const SweepableField: React.FC<SweepableFieldProps> = ({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  onEnableSweep,
  isSweeping = false,
  sweepConfig,
}) => {
  const [showSweep, setShowSweep] = useState(isSweeping);
  const [sweepValues, setSweepValues] = useState(
    sweepConfig || { start: value, stop: value + step * 4, step }
  );

  const handleEnableSweep = () => {
    if (!showSweep) {
      // 切换到扫描模式
      setShowSweep(true);
      onEnableSweep?.(sweepValues);
    } else {
      // 取消扫描，回到单值
      setShowSweep(false);
      onEnableSweep?.(undefined as any);
    }
  };

  const handleSweepChange = (field: 'start' | 'stop' | 'step', val: number | null) => {
    if (val === null) return;
    const newSweep = { ...sweepValues, [field]: val };
    setSweepValues(newSweep);
    onEnableSweep?.(newSweep);
  };

  const calculatePointCount = () => {
    const { start, stop, step: sweepStep } = sweepValues;
    if (sweepStep <= 0) return 0;
    return Math.floor((stop - start) / sweepStep) + 1;
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <Space align="start" size="small" style={{ width: '100%' }}>
        <div style={{ minWidth: 120 }}>
          <Text strong>{label}</Text>
        </div>

        {!showSweep ? (
          // 单值模式
          <>
            <InputNumber
              value={value}
              onChange={(val) => onChange(val ?? value)}
              min={min}
              max={max}
              step={step}
              style={{ width: 120 }}
            />
            {unit && <Text type="secondary">{unit}</Text>}
            <Tooltip title="扫描此参数">
              <Button
                type="dashed"
                size="small"
                icon={<SwapOutlined />}
                onClick={handleEnableSweep}
              >
                扫描
              </Button>
            </Tooltip>
          </>
        ) : (
          // 扫描模式
          <div style={{ flex: 1 }}>
            <Space size="small" wrap>
              <Input.Group compact>
                <InputNumber
                  value={sweepValues.start}
                  onChange={(val) => handleSweepChange('start', val)}
                  placeholder="起"
                  style={{ width: 80 }}
                  size="small"
                  min={min}
                  max={max}
                />
                <Input
                  style={{ width: 30, borderLeft: 0, pointerEvents: 'none' }}
                  placeholder=":"
                  disabled
                  size="small"
                />
                <InputNumber
                  value={sweepValues.step}
                  onChange={(val) => handleSweepChange('step', val)}
                  placeholder="步长"
                  style={{ width: 60, borderLeft: 0 }}
                  size="small"
                  min={step}
                />
                <Input
                  style={{ width: 30, borderLeft: 0, pointerEvents: 'none' }}
                  placeholder=":"
                  disabled
                  size="small"
                />
                <InputNumber
                  value={sweepValues.stop}
                  onChange={(val) => handleSweepChange('stop', val)}
                  placeholder="止"
                  style={{ width: 80, borderLeft: 0 }}
                  size="small"
                  min={min}
                  max={max}
                />
              </Input.Group>
              {unit && <Text type="secondary">{unit}</Text>}
              <Text type="success" style={{ fontSize: 12 }}>
                {calculatePointCount()} 个取值
              </Text>
              <Button
                type="text"
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={handleEnableSweep}
              >
                取消扫描
              </Button>
            </Space>
          </div>
        )}
      </Space>
    </div>
  );
};
