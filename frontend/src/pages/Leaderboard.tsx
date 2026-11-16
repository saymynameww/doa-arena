import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Checkbox, Empty, Input, Modal, Select, Space, Table, Tag, Tooltip, message } from 'antd';
import { Link } from 'react-router-dom';
import { getLeaderboard, getLeaderboardScenarios, runBenchmark, importBenchmarkSuite, getBenchmarkRuns } from '@/services/api';
import type { AlgorithmConfig, LeaderboardResponse } from '@/types/generated';

export default function LeaderboardPage() {
  const [suites, setSuites] = useState<Array<Record<string, any>>>([]);
  const [selected, setSelected] = useState('');
  const [column, setColumn] = useState(0);
  const [revision, setRevision] = useState<string>();
  const [board, setBoard] = useState<LeaderboardResponse>();
  const [runs, setRuns] = useState<Array<Record<string, any>>>([]);
  const [error, setError] = useState('');
  const [runOpen, setRunOpen] = useState(false);
  const [algorithms, setAlgorithms] = useState<AlgorithmConfig[]>([]);
  const [checked, setChecked] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [suiteText, setSuiteText] = useState('');
  const suite = suites.find(item => `${item.suite_id}@${item.version}` === selected);
  const loadSuites = useCallback(async () => {
    const data = await getLeaderboardScenarios();
    setSuites(data.suites);
    setSelected(value => value || (data.suites[0] ? `${data.suites[0].suite_id}@${data.suites[0].version}` : ''));
  }, []);
  useEffect(() => { void loadSuites().catch(e => setError(e.response?.data?.detail || '场景集加载失败')); }, [loadSuites]);
  const refresh = useCallback(async () => {
    if (!suite) return;
    try {
      const [data, running] = await Promise.all([getLeaderboard(suite.suite_id, suite.version, column, revision), getBenchmarkRuns()]);
      setBoard(data); setRuns(running.runs.filter(item => item.suite_id === suite.suite_id && item.suite_version === suite.version)); setError('');
    } catch (e: any) { setError(e.response?.data?.detail || '排行榜加载失败'); }
  }, [suite, column, revision]);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 5000); return () => window.clearInterval(timer); }, [refresh]);
  const openRun = () => {
    let draft: any;
    try { draft = JSON.parse(sessionStorage.getItem('arena.experimentDraft') || 'null')?.draft; } catch { draft = null; }
    const items = (draft?.algorithms || []).filter((item: AlgorithmConfig) => item.enabled !== false);
    setAlgorithms(items); setChecked(items.map((_: AlgorithmConfig, index: number) => index)); setRunOpen(true);
  };
  const run = async (items: AlgorithmConfig[], scenarios?: string[]) => {
    if (!suite) return;
    setBusy(true);
    try {
      await runBenchmark({suite_id: suite.suite_id, version: suite.version, algorithms: items, scenarios});
      setRunOpen(false); setRevision(undefined); message.success('场景集已加入实验队列'); await refresh();
    } catch (e: any) { message.error(e.response?.data?.detail || '评测创建失败，请检查算法配置'); }
    finally { setBusy(false); }
  };
  const importSuite = async () => {
    try { await importBenchmarkSuite(JSON.parse(suiteText)); await loadSuites(); setImportOpen(false); message.success('场景集已导入'); }
    catch (e: any) { message.error(e.response?.data?.detail || e.message); }
  };
  const rows = (board?.rows || []) as Array<Record<string, any>>;
  const columns: any[] = [
    {title: '排名', dataIndex: 'rank', width: 64, render: (value: number | null) => value ?? '—'},
    {title: '算法 / 版本', dataIndex: 'label', fixed: 'left', width: 200, render: (label: string, row: any) => {
      const versions = [...new Set(row.values.filter(Boolean).map((cell: any) => `${cell.version || ''} · ${cell.commit?.slice(0, 8) || '随竞技场'}${cell.dirty ? ' · 有未提交修改' : ''}`))];
      return <Tooltip title={JSON.stringify(row.algorithm.params)}><strong>{label}</strong>{versions.map(value => <div key={String(value)}><small>{String(value)}</small></div>)}</Tooltip>;
    }},
    ...((board?.columns || []) as Array<Record<string, any>>).map((spec, index) => {
      const values = rows.map(row => row.values[index]?.value).filter(value => typeof value === 'number');
      const best = values.length ? (spec.higher_is_better ? Math.max(...values) : Math.min(...values)) : undefined;
      return {key: String(index), title: <Button type="link" onClick={() => setColumn(index)} style={{height: 'auto', whiteSpace: 'normal'}}>{spec.label}{index === column ? ' ↓' : ''}<br/><small>{spec.higher_is_better ? '越大越好' : '越小越好'}</small></Button>, width: 170,
        render: (_: unknown, row: any) => {
          const cell = row.values[index];
          if (!cell) return <Button type="link" size="small" disabled={busy} onClick={() => void run([row.algorithm], [spec.scenario])}>未运行，补跑</Button>;
          return <Tooltip title={`评测 ${cell.run_id}；commit ${cell.commit || '随竞技场'}`}><Link to={`/runs/${cell.experiment_id}`} style={{fontWeight: cell.value === best ? 700 : 400}}>{cell.value == null ? '无有效值，查看结果' : Number(cell.value).toPrecision(4)}</Link></Tooltip>;
        }};
    }),
  ];
  return <Space direction="vertical" size={20} style={{width: '100%'}}>
    <Card title="排行榜" extra={<Space><Button onClick={() => setImportOpen(true)}>导入自定义场景集</Button><Button type="primary" disabled={!suite} onClick={openRun}>运行场景集</Button></Space>}>
      <Space wrap style={{marginBottom: 16}}>
        <Select aria-label="场景集及版本" style={{minWidth: 260}} value={selected || undefined} options={suites.map(item => ({value: `${item.suite_id}@${item.version}`, label: `${item.name} · v${item.version}`}))} onChange={value => {setSelected(value); setColumn(0); setRevision(undefined);}} />
        <Select aria-label="评测版本" style={{minWidth: 250}} value={revision || 'latest'} options={[{value: 'latest', label: '每个算法在各场景的最新结果'}, ...(board?.revisions || []).map(item => ({value: item.run_id, label: item.run_id}))]} onChange={value => setRevision(value === 'latest' ? undefined : value)} />
        <Button onClick={() => void refresh()}>刷新</Button>
      </Space>
      {suite && <p>共 {suite.scenarios.length} 个场景，同一版本内配置和随机种子固定。点击列名切换排名，数值可打开实验结果。不同场景不做综合评分。</p>}
      {error && <Alert type="error" showIcon message={error} style={{marginBottom: 16}} />}
      {board?.failures.length ? <Alert type="warning" message={board.failures.join('；')} /> : null}
      {rows.length ? <Table rowKey="key" dataSource={rows} columns={columns} pagination={false} scroll={{x: 1200}} /> : <Empty description="尚无此场景集版本的评测。先在新建实验页配置算法，再运行场景集。" />}
    </Card>
    {runs.slice(0, 3).map(record => <Card size="small" key={record.run_id} title={`评测 ${record.run_id}`}><Space wrap>{Object.entries(record.states).map(([name, state]: [string, any]) => <Link key={name} to={`/runs/${state.experiment_id}`}><Tag color={state.status === 'completed' ? 'green' : state.status === 'failed' ? 'red' : 'blue'}>{name} · {({queued: '排队', running: '运行中', completed: '完成', failed: '失败', cancelled: '已取消', interrupted: '已中断'} as any)[state.status] || state.status}</Tag></Link>)}</Space></Card>)}
    <Modal title="运行场景集" open={runOpen} onCancel={() => setRunOpen(false)} onOk={() => void run(checked.map(index => algorithms[index]))} confirmLoading={busy} okButtonProps={{disabled: !checked.length}}>
      <p>使用新建实验页当前的算法和参数。本次运行 {suite?.scenarios.length || 0} 个场景；耗时取决于所选算法，可在任务页查看进度和取消。</p>
      {algorithms.length ? <Checkbox.Group options={algorithms.map((item, index) => ({value: index, label: item.label || item.id}))} value={checked} onChange={values => setChecked(values as number[])} /> : <Empty description={<span>请先到 <Link to="/">新建实验</Link> 配置算法。</span>} />}
    </Modal>
    <Modal title="导入自定义场景集" open={importOpen} onCancel={() => setImportOpen(false)} onOk={() => void importSuite()}>
      <p>粘贴场景集 JSON。必须提供固定种子、版本和排行榜扫描点；修改已发布内容需要升版本。</p>
      <Input.TextArea aria-label="场景集 JSON" rows={12} value={suiteText} onChange={e => setSuiteText(e.target.value)} />
    </Modal>
  </Space>;
}
