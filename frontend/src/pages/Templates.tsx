import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, List, Button, Space, Tag, Empty, Modal, message } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { createTemplate, deleteTemplate, getTemplates, updateTemplate } from '@/services/api';
import type { Template } from '@/types';

const TemplatesPage: React.FC = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    void getTemplates().then(setTemplates).catch(() => message.error('加载模板失败'));
  }, []);

  const handleUseTemplate = (templateId: string) => {
    message.success(`模板 ${templateId} 已加载到实验配置页`);
    navigate(`/?template=${encodeURIComponent(templateId)}`);
  };

  const handleDeleteTemplate = (templateId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后模板将移入 .trash/ 目录，可以手动恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        void deleteTemplate(templateId)
          .then(() => setTemplates((current) => current.filter((t) => t.id !== templateId)))
          .catch(() => message.error('模板删除失败'));
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
                  <Tag color={template.level === '内置' ? 'default' : 'blue'}>
                    {template.level || '工作目录'}
                  </Tag>
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
                  {template.level === '内置' ? (
                    <Button type="text" icon={<CopyOutlined />} onClick={() => void handleCopy(template.id)}>
                      复制到工作目录
                    </Button>
                  ) : (
                    <>
                      <Button type="text" icon={<EditOutlined />} onClick={() => void handleEdit(template.id)}>
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
                    </>
                  )}
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

  async function handleEdit(templateId: string) {
    const template = templates.find((item) => item.id === templateId);
    if (!template) return;
    const name = window.prompt('模板名称', template.name);
    if (!name || name === template.name) return;
    const updated = await updateTemplate(templateId, { ...template, name });
    setTemplates((current) => current.map((item) => (item.id === templateId ? updated : item)));
    message.success('模板已更新');
  }

  async function handleCopy(templateId: string) {
    const template = templates.find((item) => item.id === templateId);
    if (!template) return;
    const copied = await createTemplate({
      ...template,
      id: undefined,
      name: `${template.name}（副本）`,
      level: '工作目录',
    });
    setTemplates((current) => [...current, copied]);
    message.success('模板已复制到工作目录');
  }
};

export default TemplatesPage;
