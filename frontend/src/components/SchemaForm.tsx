import React from 'react';
import { Form, Input, InputNumber, Select, Switch, Row, Col } from 'antd';
import type { ParamSchema } from '@/types';

const { Option } = Select;

interface SchemaFormProps {
  schema: Record<string, ParamSchema>;
  values?: Record<string, any>;
  onChange?: (values: Record<string, any>) => void;
  prefix?: string;
}

/**
 * 动态参数表单组件
 *
 * 根据后端返回的 JSON Schema 自动生成表单
 */
const SchemaForm: React.FC<SchemaFormProps> = ({
  schema,
  values = {},
  onChange,
  prefix = '',
}) => {
  const handleValueChange = (key: string, value: any) => {
    const newValues = { ...values, [key]: value };
    onChange?.(newValues);
  };

  const renderField = (key: string, paramSchema: ParamSchema) => {
    const value = values[key] ?? paramSchema.default;
    const label = paramSchema.description || key;

    // 根据参数类型渲染不同的输入组件
    switch (paramSchema.type) {
      case 'boolean':
        return (
          <Form.Item
            key={key}
            label={label}
            tooltip={paramSchema.description}
          >
            <Switch
              checked={value}
              onChange={(checked) => handleValueChange(key, checked)}
            />
          </Form.Item>
        );

      case 'integer':
      case 'number':
        return (
          <Form.Item
            key={key}
            label={label}
            tooltip={paramSchema.description}
          >
            <InputNumber
              value={value}
              min={paramSchema.min}
              max={paramSchema.max}
              step={paramSchema.type === 'integer' ? 1 : 0.1}
              style={{ width: '100%' }}
              onChange={(val) => handleValueChange(key, val)}
            />
          </Form.Item>
        );

      case 'string':
        if (paramSchema.enum) {
          // 枚举类型
          return (
            <Form.Item
              key={key}
              label={label}
              tooltip={paramSchema.description}
            >
              <Select
                value={value}
                onChange={(val) => handleValueChange(key, val)}
              >
                {paramSchema.enum.map((option) => (
                  <Option key={option} value={option}>
                    {option}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          );
        } else {
          // 普通字符串
          return (
            <Form.Item
              key={key}
              label={label}
              tooltip={paramSchema.description}
            >
              <Input
                value={value}
                onChange={(e) => handleValueChange(key, e.target.value)}
              />
            </Form.Item>
          );
        }

      default:
        return null;
    }
  };

  const fields = Object.entries(schema);

  // 分为两列显示
  const leftFields = fields.filter((_, index) => index % 2 === 0);
  const rightFields = fields.filter((_, index) => index % 2 === 1);

  return (
    <Row gutter={16}>
      <Col span={12}>
        {leftFields.map(([key, paramSchema]) => renderField(key, paramSchema))}
      </Col>
      <Col span={12}>
        {rightFields.map(([key, paramSchema]) => renderField(key, paramSchema))}
      </Col>
    </Row>
  );
};

export default SchemaForm;
