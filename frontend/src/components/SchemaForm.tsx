import React from 'react';
import { Form, Input, InputNumber, Select, Switch, Row, Col, Collapse, Typography } from 'antd';
import type { ParamSchema } from '@/types';

const { Option } = Select;
const { Text } = Typography;

interface SchemaFormProps {
  schema: Record<string, ParamSchema>;
  values?: Record<string, any>;
  onChange?: (values: Record<string, any>) => void;
  showAdvanced?: boolean; // 是否支持高级参数折叠
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
  showAdvanced = true,
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
              min={paramSchema.min ?? undefined}
              max={paramSchema.max ?? undefined}
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

  // 区分基本参数和高级参数（通过 x-advanced 字段标记）
  const basicFields = fields.filter(([_key, paramSchema]) => !(paramSchema as any)['x-advanced']);
  const advancedFields = fields.filter(([_key, paramSchema]) => (paramSchema as any)['x-advanced']);

  // 分为两列显示
  const renderFieldsInColumns = (fieldsToRender: [string, ParamSchema][]) => {
    const leftFields = fieldsToRender.filter((_, index) => index % 2 === 0);
    const rightFields = fieldsToRender.filter((_, index) => index % 2 === 1);

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

  return (
    <>
      {/* 基本参数 */}
      {basicFields.length > 0 && renderFieldsInColumns(basicFields)}

      {/* 高级参数（折叠） */}
      {showAdvanced && advancedFields.length > 0 && (
        <Collapse
          ghost
          bordered={false}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'advanced',
              label: <Text type="secondary">高级参数</Text>,
              children: renderFieldsInColumns(advancedFields),
            },
          ]}
        />
      )}
    </>
  );
};

export default SchemaForm;
