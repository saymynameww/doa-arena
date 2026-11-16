import { useState } from 'react';
import { Button, Modal, message } from 'antd';
import ConfigFields, { type JsonSchema } from './ConfigFields';
import { getExperimentSchema, getTask, recomputeTaskMetrics } from '@/services/api';

export default function RecomputeMetrics({ taskId, onComplete }: {
  taskId: string;
  onComplete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [schema, setSchema] = useState<JsonSchema>({});
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const load = async () => {
    setBusy(true);
    try {
      const [root, task] = await Promise.all([getExperimentSchema(), getTask(taskId)]);
      setSchema(root);
      setMetrics(structuredClone(task.config?.metrics || {}));
      setOpen(true);
    } catch {
      message.error('读取指标设置失败，请重试');
    } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    try {
      await recomputeTaskMetrics(taskId, metrics);
      setOpen(false);
      message.success('指标已重算，原始估计保持不变');
      onComplete();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '指标重算失败');
    } finally { setBusy(false); }
  };
  return <>
    <Button loading={busy} onClick={() => void load()}>重算指标</Button>
    <Modal title="重算指标" open={open} confirmLoading={busy} okText="重算"
      cancelText="取消" onCancel={() => setOpen(false)} onOk={() => void save()}>
      <p>从已保存的逐次估计重新计算统计量，原始估计不变。未保存估计值的实验无法重算。</p>
      <ConfigFields schema={schema.properties?.metrics || {}} root={schema}
        value={metrics} onChange={setMetrics} path="metrics" />
    </Modal>
  </>;
}
