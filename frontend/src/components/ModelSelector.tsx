import { useEffect, useState } from 'react';
import { AutoComplete, message } from 'antd';
import { getModels } from '@/services/api';

export default function ModelSelector({value, onChange}: {value?: string; onChange: (value: string) => void}) {
  const [options, setOptions] = useState<{value: string; label: string}[]>([]);
  useEffect(() => {
    getModels().then(data => setOptions(data.models.map(model => ({value: model.path, label: `${model.name} · ${model.algorithm_id}`}))))
      .catch(() => message.error('模型列表加载失败，可输入模型包的绝对路径'));
  }, []);
  return <AutoComplete value={value} options={options} onChange={onChange} placeholder="选择已导入模型或输入绝对路径" style={{minWidth: 300}} />;
}
