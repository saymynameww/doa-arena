/* eslint-disable react-hooks/exhaustive-deps -- validation is intentionally triggered by form values. */
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
import { PlayCircleOutlined } from '@ant-design/icons';
import { getAlgorithms, runExperiment } from '@/services/api';
import AlgorithmCard from '@/components/AlgorithmCard';
import ScenePreview from '@/components/ScenePreview';
import ConfigSummary from '@/components/ConfigSummary';
import ValidationAlert from '@/components/ValidationAlert';
import { ImpairmentConfig } from '@/components/ImpairmentConfig';
import {
  validateArrayAndSources,
  validateSnapshots,
  validateTrials,
  validateSweep,
  validateAlgorithms,
  debounce,
} from '@/utils/validation';
import type { Algorithm, ExperimentConfig, AlgorithmInstance } from '@/types';
import type { ValidationError } from '@/utils/validation';

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
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [impairments, setImpairments] = useState<Record<string, any>>({});

  useEffect(() => {
    loadAlgorithms();
  }, []);

  // 防抖校验
  const debouncedValidate = React.useMemo(
    () => debounce(() => validateConfig(), 300),
    [selectedAlgorithms]
  );

  useEffect(() => {
    debouncedValidate();
  }, [
    experimentType,
    selectedAlgorithms,
    form.getFieldValue('arraySize'),
    form.getFieldValue('snapshots'),
    form.getFieldValue('trials'),
  ]);

  const validateConfig = () => {
    const errors: ValidationError[] = [];

    // 校验阵元数和信源数
    const arraySize = form.getFieldValue('arraySize') || 16;
    const sourceCount = 2; // TODO: 从表单获取
    errors.push(...validateArrayAndSources(arraySize, sourceCount));

    // 校验快拍数
    const snapshots = form.getFieldValue('snapshots') || 100;
    errors.push(...validateSnapshots(snapshots, arraySize));

    // 校验试验次数
    if (experimentType !== 'single') {
      const trials = form.getFieldValue('trials') || 50;
      errors.push(...validateTrials(trials));
    }

    // 校验扫描配置
    if (experimentType === 'sweep') {
      const sweepPath = form.getFieldValue('sweepPath');
      const sweepValues = form.getFieldValue('sweepValues');
      errors.push(...validateSweep(sweepPath, sweepValues));
    }

    // 校验算法选择
    errors.push(...validateAlgorithms(selectedAlgorithms));

    setValidationErrors(errors);
  };

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
            <Space>
              <Button
                onClick={() => {
                  const config = form.getFieldsValue();
                  const blob = new Blob([JSON.stringify(config, null, 2)], {
                    type: 'application/json',
                  });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement('a');
                  link.href = url;
                  link.download = 'experiment_config.json';
                  link.click();
                  URL.revokeObjectURL(url);
                  message.success('配置已导出');
                }}
              >
                导出 JSON
              </Button>
              <Button>保存为模板</Button>
              <Button
                type="primary"
                onClick={handleSubmit}
                loading={loading}
                icon={<PlayCircleOutlined />}
              >
                运行实验
              </Button>
            </Space>
          }
        >
        <Form form={form} layout="vertical" onValuesChange={() => validateConfig()}>
          {/* 校验提示 */}
          <ValidationAlert errors={validationErrors} />

          {/* 基本信息 */}
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="实验名称" name="name">
                <Input placeholder="输入实验名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label={
                  experimentType === 'sweep'
                    ? '每点试验次数'
                    : experimentType === 'monte_carlo'
                    ? '试验次数'
                    : '快拍数'
                }
                name="trials"
                initialValue={50}
                hidden={experimentType === 'single'}
              >
                <InputNumber min={1} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {/* 实验类型 */}
          <Form.Item label="实验类型">
            <Radio.Group
              value={experimentType}
              onChange={(e) => setExperimentType(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Card
                  size="small"
                  style={{
                    border: experimentType === 'single' ? '2px solid #1890ff' : undefined,
                  }}
                >
                  <Radio value="single">
                    <strong>单次实验</strong>
                  </Radio>
                  <div style={{ marginLeft: 24, color: '#8c8c8c', fontSize: 12 }}>
                    生成一次场景并估计，查看空间谱和估计角度
                  </div>
                </Card>

                <Card
                  size="small"
                  style={{
                    border: experimentType === 'monte_carlo' ? '2px solid #1890ff' : undefined,
                  }}
                >
                  <Radio value="monte_carlo">
                    <strong>蒙特卡洛</strong>
                  </Radio>
                  <div style={{ marginLeft: 24, color: '#8c8c8c', fontSize: 12 }}>
                    重复多次试验，统计 RMSE、成功率等指标
                  </div>
                </Card>

                <Card
                  size="small"
                  style={{
                    border: experimentType === 'sweep' ? '2px solid #1890ff' : undefined,
                  }}
                >
                  <Radio value="sweep">
                    <strong>参数扫描</strong>
                  </Radio>
                  <div style={{ marginLeft: 24, color: '#8c8c8c', fontSize: 12 }}>
                    扫描某个参数（如 SNR），绘制指标曲线
                  </div>
                </Card>
              </Space>
            </Radio.Group>
          </Form.Item>

          {/* 参数扫描配置 */}
          {experimentType === 'sweep' && (
            <Card
              size="small"
              title="扫描配置"
              style={{ marginBottom: 16, backgroundColor: '#fafafa' }}
            >
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="扫描路径" name="sweepPath">
                    <Select placeholder="选择扫描变量">
                      <Option value="scenario.sources.snr_db">
                        <Space direction="vertical" size={0}>
                          <span>SNR (dB)</span>
                          <span style={{ fontSize: 11, color: '#8c8c8c' }}>
                            信噪比
                          </span>
                        </Space>
                      </Option>
                      <Option value="scenario.snapshots">
                        <Space direction="vertical" size={0}>
                          <span>快拍数</span>
                          <span style={{ fontSize: 11, color: '#8c8c8c' }}>
                            采样点数
                          </span>
                        </Space>
                      </Option>
                      <Option value="scenario.sources.K">
                        <Space direction="vertical" size={0}>
                          <span>信源数 K</span>
                          <span style={{ fontSize: 11, color: '#8c8c8c' }}>
                            入射信号数量
                          </span>
                        </Space>
                      </Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={10}>
                  <Form.Item
                    label="扫描范围"
                    name="sweepValues"
                    tooltip="格式：起:步长:止 或 逗号分隔，如 0,5,10,15,20"
                  >
                    <Select mode="tags" placeholder="例如: 0, 5, 10, 15, 20">
                      {[0, 5, 10, 15, 20].map((v) => (
                        <Option key={v} value={v}>
                          {v}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                  {form.getFieldValue('sweepValues')?.length > 0 && (
                    <div style={{ marginTop: -16, marginBottom: 8, fontSize: 12, color: '#52c41a' }}>
                      ✓ {form.getFieldValue('sweepValues').length} 个取值
                    </div>
                  )}
                </Col>
                <Col span={3}>
                  <Form.Item label="标签" name="sweepLabel" initialValue="SNR">
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={3}>
                  <Form.Item label="单位" name="sweepUnit" initialValue="dB">
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          )}

          <Divider />

          {/* 场景配置 */}
          <Collapse defaultActiveKey="scene">
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

            <Panel header="阵列误差" key="impairments">
              <ImpairmentConfig
                value={impairments}
                onChange={setImpairments}
              />
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
                  onSelect={(algorithmId: string | undefined) => {
                    if (algorithmId) handleAddAlgorithm(algorithmId);
                  }}
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
