import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Button, Tag, Space, message } from 'antd';
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { getTasks } from '@/services/api';
import type { Task } from '@/types';
import type { ColumnsType } from 'antd/es/table';

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTasks();
  }, []);

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
        <Button
          icon={<ReloadOutlined />}
          onClick={loadTasks}
          loading={loading}
        >
          刷新
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={tasks}
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
