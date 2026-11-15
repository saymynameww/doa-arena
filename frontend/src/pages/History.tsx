import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Button, Tag, Space, message, Select, Input } from 'antd';
import { EyeOutlined, ReloadOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { getTasks } from '@/services/api';
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
        task.task_id.toLowerCase().includes(searchText.toLowerCase())
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
      dataIndex: 'task_id',
      key: 'task_id',
      width: 120,
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
      width: 120,
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
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="历史实验"
      extra={
        <Space>
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
      <Table
        columns={columns}
        dataSource={filteredTasks}
        rowKey="task_id"
        loading={loading}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />
    </Card>
  );
};

export default HistoryPage;
