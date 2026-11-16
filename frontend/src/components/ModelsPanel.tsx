import { useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Empty, Input, Modal, Space, Tag, message } from 'antd';
import { getModels, importModel, inspectModel } from '@/services/api';
import type { ModelRecord, ModelInspection } from '@/types/generated';

export default function ModelsPanel() {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [failures, setFailures] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);
  const [inspection, setInspection] = useState<ModelInspection | null>(null);
  const reload = async () => {
    const data = await getModels();
    setModels(data.models); setFailures(data.failures);
  };
  useEffect(() => { void reload().catch(() => message.error('模型库加载失败')); }, []);
  const submit = async () => {
    setBusy(true);
    try {
      if (!inspection) { setInspection(await inspectModel(path)); return; }
      await importModel(path); await reload(); setOpen(false); setPath(''); setInspection(null); message.success('模型包已导入');
    }
    catch (error: any) { message.error(error.response?.data?.detail || '导入失败，请检查模型目录与权重哈希'); }
    finally { setBusy(false); }
  };
  return <Card title="模型包" style={{marginTop: 24}} extra={<Button onClick={() => setOpen(true)}>导入模型包</Button>}>
    {failures.length > 0 && <Alert type="warning" message={failures.join('；')} />}
    {models.length === 0 && <Empty description="尚未导入模型包。训练完成后导入包含 model.json 和权重的目录或 ZIP。" />}
    {models.map(model => <Card key={model.path} size="small" title={<Space>{model.name}<Tag>{model.algorithm_id}</Tag></Space>} style={{marginBottom: 12}}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="模型目录">{model.path}</Descriptions.Item>
        <Descriptions.Item label="输入 / 输出">{String(model.metadata.input)} / {String((model.metadata.output as any)?.type)}</Descriptions.Item>
        <Descriptions.Item label="训练信息"><pre style={{whiteSpace: 'pre-wrap'}}>{JSON.stringify({trained_on: model.metadata.trained_on, training: model.metadata.training}, null, 2)}</pre></Descriptions.Item>
      </Descriptions>
    </Card>)}
    <Modal title="导入模型包" open={open} onCancel={() => setOpen(false)} onOk={() => void submit()} okText={inspection ? '确认导入' : '检查模型包'} confirmLoading={busy} okButtonProps={{disabled: !path.trim()}}>
      <p>输入本机模型包目录或 ZIP 的绝对路径。导入会校验权重，同名模型不会覆盖。</p>
      <Input value={path} onChange={e => { setPath(e.target.value); setInspection(null); }} placeholder="模型包绝对路径" />
      {inspection && <Space direction="vertical" style={{marginTop: 12}}><Alert type="success" message={inspection.checks.join('；')} />{inspection.warnings.map(warning => <Alert key={warning} type="warning" message={warning} />)}</Space>}
    </Modal>
  </Card>;
}
