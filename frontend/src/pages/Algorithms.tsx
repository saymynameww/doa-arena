import { useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Input, Select, Space, Table, Tag, message } from 'antd';
import { getAlgorithmCatalog, refreshAlgorithms } from '@/services/api';
import type { Algorithm } from '@/types';
import ModelsPanel from '@/components/ModelsPanel';

export default function AlgorithmsPage() {
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [failures, setFailures] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('all');
  const load = async (refresh = false) => {
    setLoading(true);
    try {
      const data = await (refresh ? refreshAlgorithms() : getAlgorithmCatalog());
      setAlgorithms(data.algorithms); setFailures(data.failures);
    } catch { message.error('算法库加载失败，请检查算法来源后刷新'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const filtered = algorithms.filter(item => (source === 'all' || item.type === source) && `${item.name} ${item.id}`.toLowerCase().includes(query.toLowerCase()));
  return <>
    <Card title={<Space>算法库 <small>{algorithms.length} 个可用，{failures.length} 个加载失败</small></Space>} extra={<Button onClick={() => void load(true)}>刷新</Button>}>
      <p>内置基线和已登记来源里的算法。修改课题仓库代码后点“刷新”，不需要重启。</p>
      {failures.map((failure, index) => <Alert key={index} type="error" showIcon message={String(failure.message || failure.error || '算法加载失败')} description={<details><summary>查看堆栈</summary><pre style={{whiteSpace:'pre-wrap'}}>{String(failure.traceback || JSON.stringify(failure, null, 2))}</pre></details>} style={{marginBottom:12}} />)}
      <Space style={{marginBottom:16}}><Input.Search aria-label="搜索算法" placeholder="搜索名称或 id" value={query} onChange={e => setQuery(e.target.value)} allowClear /><Select aria-label="来源" value={source} onChange={setSource} options={[{value:'all',label:'全部来源'},{value:'builtin',label:'内置'},{value:'external',label:'外部'}]} /></Space>
      <Table<Algorithm> rowKey="id" size="small" loading={loading} dataSource={filtered} pagination={false} scroll={{x:900}} columns={[
        {title:'名称',dataIndex:'name',render:value => <strong>{value}</strong>},
        {title:'id',dataIndex:'id'},
        {title:'类别',dataIndex:'category',render:value => value === 'learning' ? '学习型' : '传统'},
        {title:'来源',render:(_, item) => item.type === 'builtin' ? <Tag>内置</Tag> : <span style={{overflowWrap:'anywhere'}}>{String(item.origin?.file || '外部')}</span>,width:220},
        {title:'版本',dataIndex:'version'},
        {title:'代码',render:(_,item) => item.type === 'builtin' ? '随竞技场' : <>{String(item.origin?.commit || '未记录 commit').slice(0,12)}{item.origin?.dirty ? <Tag color="gold">有未提交修改</Tag> : null}</>},
        {title:'适用条件',render:(_,item) => <>{item.category === 'learning' ? '阵列与模型一致；' : ''}{item.capabilities.needs_K ? '需要信源数 K；' : ''}{item.capabilities.supports_masked_elements === false ? '全部阵元可用' : '支持阵元掩码'}</>},
      ]} expandable={{expandedRowRender:item => <><p>{item.description || '暂无说明'}</p><Descriptions size="small" column={2}>{Object.entries(item.params).map(([key,schema]) => <Descriptions.Item key={key} label={key}>{schema.default == null ? '未设置默认值' : `默认值：${JSON.stringify(schema.default)}`} {schema.description}</Descriptions.Item>)}</Descriptions></>}} />
    </Card>
    <ModelsPanel />
  </>;
}
