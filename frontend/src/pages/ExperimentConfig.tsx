/* eslint-disable react-hooks/exhaustive-deps -- validation is intentionally triggered by form values. */
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  Dropdown,
} from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { createTemplate, getAlgorithms, getExperimentSchema, getTemplates, runExperiment } from '@/services/api';
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
import type { Algorithm, ExperimentConfig, AlgorithmInstance, ExperimentSchema } from '@/types';
import type { ValidationError } from '@/utils/validation';

const { Panel } = Collapse;
const { Option } = Select;
const { Text } = Typography;

const ExperimentConfigPage: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [schema, setSchema] = useState<ExperimentSchema | null>(null);
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; level?: string }>>([]);
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<AlgorithmInstance[]>([]);
  const [experimentType, setExperimentType] = useState<'single' | 'monte_carlo' | 'sweep'>(
    'monte_carlo'
  );
  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [impairments, setImpairments] = useState<Record<string, any>>({});

  useEffect(() => {
    void loadConfiguration();
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
    const sourceCount = form.getFieldValue('sourceCount') || 2;
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

  const loadConfiguration = async () => {
    try {
      const [loadedSchema, loadedAlgorithms, loadedTemplates] = await Promise.all([
        getExperimentSchema(),
        getAlgorithms(),
        getTemplates(),
      ]);
      setSchema(loadedSchema);
      setAlgorithms(loadedAlgorithms);
      setTemplates(loadedTemplates);
      const templateId = searchParams.get('template');
      if (templateId) {
        const template = (await getTemplates()).find((item) => item.id === templateId);
        if (template?.config) {
          const scenario = template.config.scenario;
          form.setFieldsValue({
            name: template.name,
            trials: template.config.trials,
            seed: scenario?.seed,
            arraySize: scenario?.array.params.M,
            snapshots: scenario?.snapshots,
            sourceCount: scenario?.sources.K,
            sourceAngles: scenario?.sources.angles.values?.join(', '),
          });
          setExperimentType(template.config.type);
        }
      }
    } catch (error) {
      message.error('加载实验配置 Schema 失败');
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

      const sourceCount = values.sourceCount || 2;
      const angles = String(values.sourceAngles || '-20, 20')
        .split(',')
        .map((value) => Number(value.trim()))
        .filter((value) => Number.isFinite(value));
      const config: ExperimentConfig = {
        name: values.name || '未命名实验',
        type: experimentType,
        trials: values.trials || 50,
        scenario: {
          seed: values.seed || 42,
          array: { type: 'ula', params: { M: values.arraySize || 16, d: values.elementSpacing || 0.5 } },
          sources: {
            K: sourceCount,
            angles: { mode: 'fixed', values: angles },
            snr_db: values.snrDb || 10,
            correlation: { mode: 'none' },
          },
          snapshots: values.snapshots || 100,
          noise_power: values.noisePower || 1,
          impairments: Object.entries(impairments).map(([type, params]) => ({
            type,
            enabled: true,
            realization: 'fixed',
            params,
          })),
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

  const handleSaveTemplate = async () => {
    const values = form.getFieldsValue(true);
    const name = window.prompt('模板名称', values.name || '未命名模板');
    if (!name) return;
    try {
      await createTemplate({
        name,
        description: '从当前实验配置保存',
        type: experimentType,
        algorithms: selectedAlgorithms.map((item) => item.id),
        createdAt: new Date().toISOString().slice(0, 10),
        config: {
          name,
          type: experimentType,
          trials: values.trials || 50,
          scenario: {
            seed: values.seed || 42,
            array: { type: 'ula', params: { M: values.arraySize || 16, d: values.elementSpacing || 0.5 } },
            sources: {
              K: values.sourceCount || 2,
              angles: { mode: 'fixed', values: String(values.sourceAngles || '-20, 20').split(',').map(Number) },
              snr_db: values.snrDb || 10,
              correlation: { mode: 'none' },
            },
            snapshots: values.snapshots || 100,
            noise_power: values.noisePower || 1,
            impairments: [],
          },
          algorithms: selectedAlgorithms,
          options: {},
        },
      });
      message.success('模板已保存');
    } catch (error) {
      message.error('模板保存失败');
    }
  };

  const handleExport = (format: 'json' | 'py') => {
    const values = form.getFieldsValue(true);
    const payload = {
      name: values.name || '未命名实验',
      type: experimentType,
      trials: values.trials || 50,
      scenario: {
        seed: values.seed || 42,
        array: { type: 'ula', params: { M: values.arraySize || 16, d: values.elementSpacing || 0.5 } },
        sources: {
          K: values.sourceCount || 2,
          angles: { mode: 'fixed', values: String(values.sourceAngles || '-20, 20').split(',').map(Number) },
          snr_db: values.snrDb || 10,
          correlation: { mode: 'none' },
        },
        snapshots: values.snapshots || 100,
        noise_power: values.noisePower || 1,
        impairments: [],
      },
      algorithms: selectedAlgorithms,
      options: {},
    };
    const content = format === 'json'
      ? JSON.stringify(payload, null, 2)
      : `import arena\nconfig = ${JSON.stringify(payload, null, 2)}\nresult = arena.run(config)\n`;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
    link.download = format === 'json' ? 'experiment_config.json' : 'experiment_config.py';
    link.click();
    URL.revokeObjectURL(link.href);
    message.success(`已导出 ${format.toUpperCase()}`);
  };

  return (
    <Row gutter={16}>
      <Col span={16}>
        <Card
          title="新建实验"
          extra={
            <Space>
              <Dropdown
                menu={{
                  items: templates.map((template) => ({
                    key: template.id,
                    label: `${template.name}${template.level === '内置' ? '（内置）' : ''}`,
                    onClick: () => navigate(`/?template=${encodeURIComponent(template.id)}`),
                  })),
                }}
              >
                <Button>从模板加载</Button>
              </Dropdown>
              <Button onClick={() => void handleSaveTemplate()}>保存为模板</Button>
              <Dropdown
                menu={{
                  items: [
                    { key: 'json', label: 'JSON', onClick: () => handleExport('json') },
                    { key: 'py', label: 'Python 脚本', onClick: () => handleExport('py') },
                  ],
                }}
              >
                <Button>导出 JSON / 脚本</Button>
              </Dropdown>
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
                      {(schema?.['x-sweep-paths'] || []).map((item) => (
                        <Option key={item.path} value={item.path}>
                          <Space direction="vertical" size={0}>
                            <span>{item.label}</span>
                            <span style={{ fontSize: 11, color: '#8c8c8c' }}>{item.unit}</span>
                          </Space>
                        </Option>
                      ))}
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
                  <Form.Item label="信源数 K" name="sourceCount" initialValue={2}>
                    <InputNumber min={1} max={16} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="信源角度（度，逗号分隔）" name="sourceAngles" initialValue="-20, 20">
                    <Input placeholder="例如：-20, 20" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="信噪比" name="snrDb" initialValue={10}>
                    <InputNumber style={{ width: '100%' }} />
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
        <div className="experiment-runbar">
          <div>
            <strong>{experimentType === 'sweep' ? `${form.getFieldValue('sweepValues')?.length || 0} 个扫描点 × ` : ''}</strong>
            {experimentType === 'single' ? '单次实验' : `${form.getFieldValue('trials') || 50} 次试验`} × {selectedAlgorithms.length} 个算法
            {validationErrors.filter((error) => error.severity === 'warning').length > 0 && (
              <Tag color="warning" style={{ marginLeft: 12 }}>
                {validationErrors.filter((error) => error.severity === 'warning').length} 条警告
              </Tag>
            )}
          </div>
          <Button
            type="primary"
            onClick={handleSubmit}
            loading={loading}
            icon={<PlayCircleOutlined />}
          >
            运行实验
          </Button>
        </div>
      </Card>
    </Col>

    <Col span={8}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 场景预览 */}
        <ScenePreview
          arraySize={form.getFieldValue('arraySize') || 16}
          sourceAngles={String(form.getFieldValue('sourceAngles') || '-20, 20').split(',').map(Number)}
          faultyElements={[]}
        />

        {/* 配置摘要 */}
        <ConfigSummary
          config={{
            experimentType,
            trials: form.getFieldValue('trials'),
            arraySize: form.getFieldValue('arraySize') || 16,
            sourceCount: form.getFieldValue('sourceCount') || 2,
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
