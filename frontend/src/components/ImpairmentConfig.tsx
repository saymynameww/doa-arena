import React from 'react';
import { Collapse, Checkbox, Select, InputNumber, Space, Typography, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

const { Panel } = Collapse;
const { Text } = Typography;

interface ImpairmentParam {
  key: string;
  label: string;
  type: 'number';
  default: number;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  help?: string;
}

interface ImpairmentType {
  id: string;
  name: string;
  description: string;
  params: ImpairmentParam[];
  realizationModes: Array<{ value: string; label: string }>;
}

const IMPAIRMENT_TYPES: ImpairmentType[] = [
  {
    id: 'gain_phase',
    name: '幅相误差',
    description: '各通道增益和相位不一致',
    realizationModes: [
      { value: 'fixed', label: '固定' },
      { value: 'random', label: '每次随机' },
    ],
    params: [
      {
        key: 'sigma_g',
        label: '幅度误差标准差 σ_g',
        type: 'number',
        default: 0.05,
        unit: '线性值',
        min: 0,
        max: 0.5,
        step: 0.01,
        help: '增益误差的标准差（线性值）',
      },
      {
        key: 'sigma_phi_deg',
        label: '相位误差标准差 σ_φ',
        type: 'number',
        default: 5,
        unit: '°',
        min: 0,
        max: 45,
        step: 1,
        help: '相位误差的标准差（度）',
      },
    ],
  },
  {
    id: 'position',
    name: '位置误差',
    description: '阵元实际位置偏离标称位置',
    realizationModes: [
      { value: 'fixed', label: '固定' },
      { value: 'random', label: '每次随机' },
    ],
    params: [
      {
        key: 'sigma_p',
        label: '位置误差标准差 σ_p',
        type: 'number',
        default: 0.02,
        unit: 'λ',
        min: 0,
        max: 0.2,
        step: 0.01,
        help: '阵元位置偏移的标准差（波长的倍数）',
      },
    ],
  },
  {
    id: 'mutual_coupling',
    name: '互耦',
    description: '相邻阵元之间的信号耦合',
    realizationModes: [
      { value: 'fixed', label: '固定' },
    ],
    params: [
      {
        key: 'c1_mag',
        label: '一阶耦合系数幅度 c₁',
        type: 'number',
        default: 0.3,
        min: 0,
        max: 1,
        step: 0.05,
        help: '相邻阵元间的耦合系数幅度',
      },
      {
        key: 'c1_phase_deg',
        label: '一阶耦合系数相位',
        type: 'number',
        default: 60,
        unit: '°',
        min: -180,
        max: 180,
        step: 5,
      },
      {
        key: 'scale',
        label: '强度倍数',
        type: 'number',
        default: 1,
        min: 0,
        max: 2,
        step: 0.1,
        help: '整体缩放因子',
      },
    ],
  },
  {
    id: 'element_failure',
    name: '阵元故障',
    description: '部分阵元没有输出',
    realizationModes: [
      { value: 'fixed', label: '固定' },
      { value: 'random', label: '每次随机' },
    ],
    params: [
      {
        key: 'count',
        label: '故障阵元数',
        type: 'number',
        default: 1,
        min: 0,
        max: 8,
        step: 1,
      },
    ],
  },
];

interface ImpairmentValue {
  enabled: boolean;
  realization: string;
  params: Record<string, number>;
}

interface ImpairmentConfigProps {
  value?: Record<string, ImpairmentValue>;
  onChange?: (value: Record<string, ImpairmentValue>) => void;
}

export const ImpairmentConfig: React.FC<ImpairmentConfigProps> = ({ value = {}, onChange }) => {
  const handleToggle = (id: string, enabled: boolean) => {
    const newValue = { ...value };
    if (!newValue[id]) {
      const impType = IMPAIRMENT_TYPES.find(t => t.id === id)!;
      newValue[id] = {
        enabled,
        realization: impType.realizationModes[0].value,
        params: Object.fromEntries(impType.params.map(p => [p.key, p.default])),
      };
    } else {
      newValue[id] = { ...newValue[id], enabled };
    }
    onChange?.(newValue);
  };

  const handleRealizationChange = (id: string, realization: string) => {
    const newValue = { ...value };
    if (newValue[id]) {
      newValue[id] = { ...newValue[id], realization };
      onChange?.(newValue);
    }
  };

  const handleParamChange = (id: string, paramKey: string, paramValue: number) => {
    const newValue = { ...value };
    if (newValue[id]) {
      newValue[id] = {
        ...newValue[id],
        params: { ...newValue[id].params, [paramKey]: paramValue },
      };
      onChange?.(newValue);
    }
  };

  return (
    <div style={{ marginTop: 8 }}>
      {IMPAIRMENT_TYPES.map(impType => {
        const impValue = value[impType.id] || {
          enabled: false,
          realization: impType.realizationModes[0].value,
          params: Object.fromEntries(impType.params.map(p => [p.key, p.default])),
        };

        return (
          <div
            key={impType.id}
            style={{
              border: '1px dashed #e8e8e8',
              borderRadius: 6,
              padding: '12px 14px',
              marginBottom: 10,
              backgroundColor: impValue.enabled ? '#fafafa' : '#fff',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: impValue.enabled ? 10 : 0 }}>
              <Checkbox
                checked={impValue.enabled}
                onChange={e => handleToggle(impType.id, e.target.checked)}
              >
                <Text strong>{impType.name}</Text>
              </Checkbox>
              <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
                {impType.description}
              </Text>
              {impValue.enabled && (
                <Select
                  value={impValue.realization}
                  onChange={v => handleRealizationChange(impType.id, v)}
                  style={{ width: 120 }}
                  size="small"
                  options={impType.realizationModes}
                />
              )}
            </div>

            {impValue.enabled && (
              <div style={{ paddingLeft: 28, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {impType.params.map(param => (
                  <Space key={param.key} align="center">
                    <Text style={{ width: 180, fontSize: 13 }}>
                      {param.label}
                      {param.help && (
                        <Tooltip title={param.help}>
                          <InfoCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
                        </Tooltip>
                      )}
                    </Text>
                    <InputNumber
                      value={impValue.params[param.key] ?? param.default}
                      onChange={v => handleParamChange(impType.id, param.key, v ?? param.default)}
                      min={param.min}
                      max={param.max}
                      step={param.step}
                      style={{ width: 100 }}
                      size="small"
                    />
                    {param.unit && <Text type="secondary">{param.unit}</Text>}
                  </Space>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

