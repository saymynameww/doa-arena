import React, { useEffect } from 'react';
import { Card, Form, Input, InputNumber, Select, Switch, Button, message, Divider, Table, Tag, Descriptions, Space } from 'antd';
import { PlusOutlined, SaveOutlined, SwapOutlined } from '@ant-design/icons';
import { addWorkspace, getAlgorithmSources, getCurrentWorkspace, getSettings, getWorkspaces, rebuildWorkspaceIndex, selectWorkspace, updateSettings } from '@/services/api';

const { Option } = Select;

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm();
  const [workspaces, setWorkspaces] = React.useState<Array<Record<string, any>>>([]);
  const [currentWorkspace, setCurrentWorkspace] = React.useState<Record<string, any>>({});
  const [sources, setSources] = React.useState<any[]>([]);

  useEffect(() => {
    void Promise.all([getSettings(), getWorkspaces(), getCurrentWorkspace(), getAlgorithmSources()]).then(([settings, loadedWorkspaces, current, sourceData]) => {
      form.setFieldsValue(settings);
      setWorkspaces(loadedWorkspaces);
      setCurrentWorkspace(current);
      setSources(sourceData.sources || []);
    });
  }, [form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      await updateSettings(values);
      message.success('设置已保存');
    } catch (error) {
      message.error('保存失败');
    }
  };

  const handleAddWorkspace = async () => {
    const path = window.prompt('工作目录路径');
    if (!path) return;
    const name = window.prompt('工作目录名称', path.split(/[\\/]/).pop() || '新工作目录');
    if (!name) return;
    const workspace = await addWorkspace({ name, path });
    setWorkspaces((items) => [...items, workspace]);
    message.success('工作目录已添加');
  };

  const handleSelectWorkspace = async (workspace: Record<string, any>) => {
    const selected = await selectWorkspace(workspace);
    setCurrentWorkspace(selected);
    message.success(`已切换到：${workspace.name || workspace.path}`);
  };

  return (
    <Card
      title="系统设置"
      extra={
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
          保存设置
        </Button>
      }
    >
      <Form form={form} layout="vertical">
        {/* 工作目录 */}
        <Divider orientation="left">工作目录</Divider>
        <Form.Item
          label="当前工作目录"
          name="workDir"
          initialValue="D:/Experiments"
          tooltip="实验结果的默认保存位置"
        >
          <Input addonAfter={<Button size="small">浏览</Button>} />
        </Form.Item>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button icon={<PlusOutlined />} onClick={() => void handleAddWorkspace()}>添加工作目录</Button>
            <Button onClick={() => void rebuildWorkspaceIndex().then(() => message.success('工作目录索引已重建'))}>重建索引</Button>
          </Space>
          <span style={{ marginLeft: 12, color: '#8c8c8c' }}>
            已配置工作目录：{workspaces.length} 个
          </span>
        </div>
        <Table
          size="small"
          pagination={false}
          rowKey={(row) => row.path || row.name}
          dataSource={workspaces}
          columns={[{ title: '名称', dataIndex: 'name', render: (name: string, row) => <Space>{name}<>{row.path === currentWorkspace.path && <Tag color="blue">当前</Tag>}</></Space> }, { title: '路径', dataIndex: 'path' }, { title: '状态', render: () => <Tag color="green">可用</Tag> }, { title: '操作', render: (_: unknown, row) => <Button size="small" icon={<SwapOutlined />} disabled={row.path === currentWorkspace.path} onClick={() => void handleSelectWorkspace(row)}>切换到这里</Button> }]}
          locale={{ emptyText: '尚未配置工作目录' }}
        />

        <Divider orientation="left">运行环境</Divider>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="服务地址">127.0.0.1:8765</Descriptions.Item>
          <Descriptions.Item label="结果格式">JSON / NPZ</Descriptions.Item>
          <Descriptions.Item label="算法来源">内置算法库</Descriptions.Item>
          <Descriptions.Item label="前端模式">本地开发</Descriptions.Item>
        </Descriptions>
        <Divider orientation="left">算法来源</Divider>
        <Table size="small" pagination={false} dataSource={sources} rowKey="name" columns={[{ title: '来源', dataIndex: 'name' }, { title: '状态', dataIndex: 'status', render: (status: string) => <Tag color={status === 'ok' ? 'green' : 'orange'}>{status === 'ok' ? '可用' : '异常'}</Tag> }, { title: '数量', dataIndex: 'count' }]} />

        {/* 默认参数 */}
        <Divider orientation="left">默认参数</Divider>

        <Form.Item
          label="默认试验次数"
          name="defaultTrials"
          initialValue={100}
          tooltip="新建实验时的默认值"
        >
          <InputNumber min={1} max={10000} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="默认阵元数"
          name="defaultArraySize"
          initialValue={16}
        >
          <InputNumber min={2} max={64} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="默认随机种子"
          name="defaultSeed"
          initialValue={42}
        >
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>

        {/* 图表设置 */}
        <Divider orientation="left">图表设置</Divider>

        <Form.Item
          label="默认图表格式"
          name="chartFormat"
          initialValue="png"
        >
          <Select>
            <Option value="png">PNG</Option>
            <Option value="svg">SVG</Option>
            <Option value="pdf">PDF</Option>
            <Option value="html">HTML（交互式）</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="图表分辨率（DPI）"
          name="chartDpi"
          initialValue={300}
        >
          <InputNumber min={72} max={600} style={{ width: '100%' }} />
        </Form.Item>

        {/* 性能设置 */}
        <Divider orientation="left">性能设置</Divider>

        <Form.Item
          label="最大并行任务数"
          name="maxParallelTasks"
          initialValue={4}
          tooltip="同时运行的实验任务数量上限"
        >
          <InputNumber min={1} max={16} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="自动清理旧结果"
          name="autoCleanup"
          valuePropName="checked"
          initialValue={true}
          tooltip="自动删除 30 天前的实验结果"
        >
          <Switch />
        </Form.Item>

        {/* 界面设置 */}
        <Divider orientation="left">界面设置</Divider>

        <Form.Item
          label="主题"
          name="theme"
          initialValue="light"
        >
          <Select>
            <Option value="light">浅色</Option>
            <Option value="dark">深色</Option>
            <Option value="auto">跟随系统</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="语言"
          name="language"
          initialValue="zh-CN"
        >
          <Select>
            <Option value="zh-CN">简体中文</Option>
            <Option value="en-US">English</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="显示高级选项"
          name="showAdvanced"
          valuePropName="checked"
          initialValue={false}
        >
          <Switch />
        </Form.Item>
      </Form>
    </Card>
  );
};

export default SettingsPage;
