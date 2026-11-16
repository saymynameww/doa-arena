import React from 'react';
import { Card, Form, Input, InputNumber, Select, Switch, Button, message, Divider } from 'antd';
import { SaveOutlined } from '@ant-design/icons';

const { Option } = Select;

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm();

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      console.log('保存设置:', values);
      message.success('设置已保存');
    } catch (error) {
      message.error('保存失败');
    }
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
