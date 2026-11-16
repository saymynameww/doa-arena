/* eslint-disable react-hooks/exhaustive-deps -- filtering follows the displayed task state. */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Button, Tag, Space, message, Select, Input, Alert, Modal } from 'antd';
import { EyeOutlined, ReloadOutlined, SearchOutlined, PlusOutlined } from '@ant-design/icons';
import { cancelTask, copyTask, getTasks, rerunTask } from '@/services/api';
import type { Task } from '@/types';
import type { ColumnsType } from 'antd/es/table';

const { Option } = Select;

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filteredTasks, setFilteredTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchText, setSearchText] = useState<string>('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  useEffect(() => {
    loadTasks();
  }, []);

  useEffect(() => {
    filterTasks();
  }, [tasks, statusFilter, searchText]);

  const filterTasks = () => {
    let filtered = tasks;

    // 状态筛选
    if (statusFilter !== 'all') {
      filtered = filtered.filter((task) => task.status === statusFilter);
    }

    // 搜索筛选
    if (searchText) {
      filtered = filtered.filter((task) =>
        `${task.task_id} ${task.name || ''}`.toLowerCase().includes(searchText.toLowerCase())
      );
    }

    setFilteredTasks(filtered);
  };

  const loadTasks = async () => {
    try {
      setLoading(true);
      const data = await getTasks();
      setTasks(data);
    } catch (error) {
      message.error('加载历史实验失败');
    } finally {
      setLoading(false);
    }
  };

  const renderStatus = (status: string) => {
    const statusMap = {
      pending: { color: 'default', text: '等待中' },
      running: { color: 'processing', text: '运行中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
      cancelled: { color: 'default', text: '已取消' },
    };

    const config = statusMap[status as keyof typeof statusMap] || statusMap.pending;
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const columns: ColumnsType<Task> = [
    {
      title: '任务 ID',
      dataIndex: 'name',
      key: 'task_id',
      width: 220,
      render: (name: string | undefined, record) => (
        <Space direction="vertical" size={0}>
          <span>{name || `实验 ${record.task_id}`}</span>
          <span style={{ fontSize: 11, color: '#8c8c8c' }}>{record.task_id}</span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: renderStatus,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (timestamp: number) =>
        new Date(timestamp * 1000).toLocaleString('zh-CN'),
    },
    {
      title: '耗时',
      dataIndex: 'elapsed_seconds',
      key: 'elapsed_seconds',
      width: 100,
      render: (seconds?: number) =>
        seconds ? `${seconds.toFixed(1)} 秒` : '-',
    },
    {
      title: '进度',
      key: 'progress',
      width: 120,
      render: (_, record) => {
        if (record.progress) {
          return `${record.progress.percent}%`;
        }
        return '-';
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/runs/${record.task_id}`)}
          >
            查看
          </Button>
          <Button type="link" size="small" onClick={() => void handleCopy(record.task_id)}>
            复制
          </Button>
          <Button type="link" size="small" onClick={() => void handleRerun(record.task_id)}>
            重跑
          </Button>
          <Button type="link" danger size="small" onClick={() => void handleDelete(record.task_id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const selectedTasks = tasks.filter((task) => selectedRowKeys.includes(task.task_id));
  const compareReason =
    selectedRowKeys.length < 2
      ? '再选择一个实验才可以对比'
      : selectedRowKeys.length > 4
        ? '一次最多对比 4 个实验'
        : selectedTasks.some((task) => task.type !== 'sweep')
          ? '只有参数扫描实验可以对比'
          : new Set(selectedTasks.map((task) => task.config?.sweep?.path)).size > 1
            ? '选中的实验扫描变量不同'
            : '';

  function handleCompare() {
    navigate(`/compare?ids=${selectedRowKeys.join(',')}`);
  }

  return (
    <Card
      title="历史实验"
      extra={
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/')}>
            新建实验
          </Button>
          <Input
            placeholder="搜索任务 ID"
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 120 }}
          >
            <Option value="all">全部状态</Option>
            <Option value="completed">已完成</Option>
            <Option value="running">运行中</Option>
            <Option value="failed">失败</Option>
            <Option value="cancelled">已取消</Option>
          </Select>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadTasks}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      }
    >
      {selectedRowKeys.length > 0 && (
        <Alert
          style={{ marginBottom: 16 }}
          type={compareReason ? 'warning' : 'info'}
          message={`已选择 ${selectedRowKeys.length} 个实验`}
          description={compareReason || '可以进入多实验对比'}
          action={
            <Space>
              <Button type="primary" disabled={Boolean(compareReason)} onClick={handleCompare}>
                对比
              </Button>
              <Button onClick={() => setSelectedRowKeys([])}>取消选择</Button>
            </Space>
          }
        />
      )}
      <Table
        columns={columns}
        dataSource={filteredTasks}
        rowKey="task_id"
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as string[]),
        }}
        loading={loading}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />
    </Card>
  );

  async function handleCopy(taskId: string) {
    await copyTask(taskId);
    message.success('已复制实验配置');
    await loadTasks();
  }

  async function handleRerun(taskId: string) {
    const result = await rerunTask(taskId);
    message.success('已重新提交实验');
    navigate(`/runs/${result.task_id}`);
  }

  async function handleDelete(taskId: string) {
    Modal.confirm({
      title: '确认删除实验？',
      content: '实验文件夹将移入当前工作目录的 .trash/ 目录，可手动恢复。',
      okText: '移入回收站',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await cancelTask(taskId);
        message.success('实验已移入回收站');
        await loadTasks();
      },
    });
  }
};

export default HistoryPage;
