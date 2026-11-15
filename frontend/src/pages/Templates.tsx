import React, { useState } from 'react';
import { Card, List, Button, Space, Tag, Empty, Modal, message } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CopyOutlined,
} from '@ant-design/icons';

interface Template {
  id: string;
  name: string;
  description: string;
  type: string;
  algorithms: string[];
  createdAt: string;
}

const TemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([
    {
      id: '1',
      name: '标准 DOA 对比',
      description: 'MUSIC、ESPRIT、Root-MUSIC 三算法对比',
      type: 'monte_carlo',
      algorithms: ['MUSIC', 'ESPRIT', 'Root-MUSIC'],
      createdAt: '2026-11-10',
    },
    {
      id: '2',
      name: 'SNR 扫描实验',
      description: '扫描 SNR -10 到 20 dB，步长 5 dB',
      type: 'sweep',
      algorithms: ['MUSIC', 'ESPRIT'],
      createdAt: '2026-11-12',
    },
  ]);

  const handleUseTemplate = (templateId: string) => {
    message.success('模板已加载到实验配置页');
    // TODO: 导航到配置页并加载模板
  };

  const handleDeleteTemplate = (templateId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后模板将移入 .trash/ 目录，可以手动恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        setTemplates(templates.filter((t) => t.id !== templateId));
        message.success('模板已删除');
      },
    });
  };

  const getTypeTag = (type: string) => {
    const types: Record<string, { label: string; color: string }> = {
      single: { label: '单次', color: 'blue' },
      monte_carlo: { label: '蒙特卡洛', color: 'green' },
      sweep: { label: '参数扫描', color: 'orange' },
    };
    const config = types[type] || types.monte_carlo;
    return <Tag color={config.color}>{config.label}</Tag>;
  };

  return (
    <Card
      title="实验模板"
      extra={
        <Button type="primary" icon={<PlusOutlined />}>
          新建模板
        </Button>
      }
    >
      {templates.length === 0 ? (
        <Empty description="暂无模板，从实验配置页保存模板" />
      ) : (
        <List
          itemLayout="vertical"
          dataSource={templates}
          renderItem={(template) => (
            <Card
              type="inner"
              title={
                <Space>
                  <span>{template.name}</span>
                  {getTypeTag(template.type)}
                </Space>
              }
              extra={
                <Space>
                  <Button
                    type="text"
                    icon={<CopyOutlined />}
                    onClick={() => handleUseTemplate(template.id)}
                  >
                    使用
                  </Button>
                  <Button type="text" icon={<EditOutlined />}>
                    编辑
                  </Button>
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteTemplate(template.id)}
                  >
                    删除
                  </Button>
                </Space>
              }
              style={{ marginBottom: 16 }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>{template.description}</div>
                <div>
                  <strong>算法：</strong>
                  {template.algorithms.map((algo, index) => (
                    <Tag key={index}>{algo}</Tag>
                  ))}
                </div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                  创建时间：{template.createdAt}
                </div>
              </Space>
            </Card>
          )}
        />
      )}
    </Card>
  );
};

export default TemplatesPage;
