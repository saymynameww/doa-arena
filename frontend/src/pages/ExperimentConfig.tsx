import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Space,
  Radio,
  Divider,
  Row,
  Col,
  message,
  Collapse,
  Tag,
  Typography,
} from 'antd';
import { PlusOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { getAlgorithms, runExperiment } from '@/services/api';
import AlgorithmCard from '@/components/AlgorithmCard';
import ScenePreview from '@/components/ScenePreview';
import ConfigSummary from '@/components/ConfigSummary';
import type { Algorithm, ExperimentConfig, AlgorithmInstance } from '@/types';

const { Panel } = Collapse;
const { Option } = Select;
const { Text } = Typography;

const ExperimentConfigPage: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<AlgorithmInstance[]>([]);
  const [experimentType, setExperimentType] = useState<'single' | 'monte_carlo' | 'sweep'>(
    'monte_carlo'
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAlgorithms();
  }, []);

  const loadAlgorithms = async () => {
    try {
      const algos = await getAlgorithms();
      setAlgorithms(algos);
    } catch (error) {
      message.error('加载算法列表失败');
    }
  };

  const handleAddAlgorithm = (algorithmId: string) => {
    const algo = algorithms.find((a) => a.id === algorithmId);
    if (!algo) return;

    const newInstance: AlgorithmInstance = {
      id: algorithmId,
      label: algo.name,
      params: {},
    };

    setSelectedAlgorithms([...selectedAlgorithms, newInstance]);
  };

  const handleRemoveAlgorithm = (index: number) => {
    const newAlgorithms = [...selectedAlgorithms];
    newAlgorithms.splice(index, 1);
    setSelectedAlgorithms(newAlgorithms);
  };

  const handleCopyAlgorithm = (index: number) => {
    const algo = selectedAlgorithms[index];
    const newInstance: AlgorithmInstance = {
      ...algo,
      label: `${algo.label} (副本)`,
    };
    setSelectedAlgorithms([...selectedAlgorithms, newInstance]);
  };

  const handleAlgorithmLabelChange = (index: number, label: string) => {
    const newAlgorithms = [...selectedAlgorithms];
    newAlgorithms[index].label = label;
    setSelectedAlgorithms(newAlgorithms);
  };

  const handleAlgorithmParamsChange = (index: number, params: Record<string, any>) => {
    const newAlgorithms = [...selectedAlgorithms];
    newAlgorithms[index].params = params;
    setSelectedAlgorithms(newAlgorithms);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      if (selectedAlgorithms.length === 0) {
        message.error('请至少选择一个算法');
        return;
      }

      const config: ExperimentConfig = {
        name: values.name || '未命名实验',
        type: experimentType,
        trials: values.trials || 50,
        scenario: {
          seed: values.seed || 42,
          snapshots: values.snapshots || 100,
        },
        algorithms: selectedAlgorithms,
        options: {},
      };

      // 参数扫描配置
      if (experimentType === 'sweep' && values.sweepPath) {
        config.sweep = {
          path: values.sweepPath,
          values: values.sweepValues || [],
          label: values.sweepLabel || '扫描变量',
          unit: values.sweepUnit || '',
        };
      }

      setLoading(true);
      const response = await runExperiment(config);
      message.success('实验已提交');
      navigate(`/runs/${response.task_id}`);
    } catch (error: any) {
      console.error('提交失败:', error);
      message.error(error.response?.data?.detail || '提交实验失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Row gutter={16}>
      <Col span={16}>
        <Card
          title="新建实验"
          extra={
            <Button
              type="primary"
              onClick={handleSubmit}
              loading={loading}
              icon={<PlayCircleOutlined />}
            >
              运行实验
            </Button>
          }
        >
        <Form form={form} layout="vertical">
          {/* 基本信息 */}
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="实验名称" name="name">
                <Input placeholder="输入实验名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="试验次数" name="trials" initialValue={50}>
                <InputNumber min={1} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {/* 实验类型 */}
          <Form.Item label="实验类型">
            <Radio.Group value={experimentType} onChange={(e) => setExperimentType(e.target.value)}>
              <Radio.Button value="single">单次实验</Radio.Button>
              <Radio.Button value="monte_carlo">蒙特卡洛</Radio.Button>
              <Radio.Button value="sweep">参数扫描</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {/* 参数扫描配置 */}
          {experimentType === 'sweep' && (
            <Card size="small" title="扫描配置" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="扫描路径" name="sweepPath">
                    <Select placeholder="选择扫描变量">
                      <Option value="scenario.sources.snr_db">SNR (dB)</Option>
                      <Option value="scenario.snapshots">快拍数</Option>
                      <Option value="scenario.sources.K">信源数</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="扫描范围" name="sweepValues">
                    <Select mode="tags" placeholder="例如: 0, 5, 10, 15, 20">
                      {[0, 5, 10, 15, 20].map((v) => (
                        <Option key={v} value={v}>
                          {v}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item label="标签" name="sweepLabel" initialValue="SNR">
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item label="单位" name="sweepUnit" initialValue="dB">
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          )}

          <Divider />

          {/* 场景配置 */}
          <Collapse defaultActiveKeys={['scene']}>
            <Panel header="场景配置" key="scene">
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="阵元数 M" name="arraySize" initialValue={16}>
                    <InputNumber min={2} max={64} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="快拍数" name="snapshots" initialValue={100}>
                    <InputNumber min={10} max={10000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="随机种子" name="seed" initialValue={42}>
                    <InputNumber min={0} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Panel>
          </Collapse>

          <Divider />

          {/* 算法选择 */}
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Text strong>算法</Text>
                <Select
                  placeholder="添加算法"
                  style={{ width: 200 }}
                  onSelect={handleAddAlgorithm}
                  value={undefined}
                >
                  {algorithms.map((algo) => (
                    <Option key={algo.id} value={algo.id}>
                      {algo.name}
                    </Option>
                  ))}
                </Select>
                <Tag color="blue">{selectedAlgorithms.length} 个算法</Tag>
              </Space>
            </div>

            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {selectedAlgorithms.map((instance, index) => {
                const algo = algorithms.find((a) => a.id === instance.id);
                if (!algo) return null;

                return (
                  <AlgorithmCard
                    key={index}
                    algorithm={algo}
                    instance={instance}
                    index={index}
                    onLabelChange={handleAlgorithmLabelChange}
                    onParamsChange={handleAlgorithmParamsChange}
                    onRemove={handleRemoveAlgorithm}
                    onCopy={handleCopyAlgorithm}
                  />
                );
              })}
            </Space>
          </div>
        </Form>
      </Card>
    </Col>

    <Col span={8}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 场景预览 */}
        <ScenePreview
          arraySize={form.getFieldValue('arraySize') || 16}
          sourceAngles={[-20, 20]}
          faultyElements={[]}
        />

        {/* 配置摘要 */}
        <ConfigSummary
          config={{
            experimentType,
            trials: form.getFieldValue('trials'),
            arraySize: form.getFieldValue('arraySize') || 16,
            sourceCount: 2,
            algorithms: selectedAlgorithms.map((a) => a.label),
            seed: form.getFieldValue('seed'),
          }}
        />
      </Space>
    </Col>
  </Row>
  );
};

export default ExperimentConfigPage;
