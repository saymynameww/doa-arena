import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button, Progress, Tag, Select, Space } from 'antd';
import {
  ExperimentOutlined,
  HistoryOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SettingOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { getTasks, getWorkspaces, selectWorkspace } from '@/services/api';
import type { Task } from '@/types';

const { Sider, Content } = Layout;
const { Title } = Typography;

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [workspaces, setWorkspaces] = useState<Array<Record<string, any>>>([]);

  useEffect(() => {
    void Promise.all([getTasks(), getWorkspaces()]).then(([loadedTasks, loadedWorkspaces]) => {
      setTasks(loadedTasks);
      setWorkspaces(loadedWorkspaces);
    });
  }, [location.pathname]);

  const currentTask = useMemo(
    () => tasks.find((task) => task.status === 'running' || task.status === 'pending') || tasks[0],
    [tasks]
  );
  const selectedKey = location.pathname.startsWith('/runs') || location.pathname === '/compare'
    ? '/history'
    : location.pathname;

  const menuItems = [
    {
      type: 'group' as const,
      label: '实验',
      children: [
        { key: '/', icon: <ExperimentOutlined />, label: '新建实验' },
        { key: '/history', icon: <HistoryOutlined />, label: '历史实验' },
      ],
    },
    {
      type: 'group' as const,
      label: '资源',
      children: [
        { key: '/algorithms', icon: <DatabaseOutlined />, label: '算法库' },
        { key: '/templates', icon: <FileTextOutlined />, label: '模板' },
      ],
    },
    {
      type: 'group' as const,
      label: '评测',
      children: [{ key: '/leaderboard', icon: <TrophyOutlined />, label: '排行榜' }],
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ];

  const handleWorkspaceChange = (value: string) => {
    const workspace = workspaces.find((item) => (item.name || item.path) === value);
    if (!workspace) return;
    void selectWorkspace(workspace).then(() => window.location.reload());
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        className="arena-sider"
        width={220}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
        }}
      >
        <div className="arena-brand">
          <Title level={4} style={{ margin: 0 }}>
            DOA 竞技场
          </Title>
        </div>
        <div className="arena-workspace">
          <Typography.Text type="secondary">工作目录</Typography.Text>
          <Select
            size="small"
            value={workspaces[0]?.name || '当前工作目录'}
            options={workspaces.map((workspace) => ({
              label: workspace.name || workspace.path,
              value: workspace.name || workspace.path,
            }))}
            placeholder="选择工作目录"
            onChange={handleWorkspaceChange}
            style={{ width: '100%', marginTop: 6 }}
          />
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        {currentTask && (
          <div className="arena-current-task">
            <Space>
              <Tag color={currentTask.status === 'running' ? 'processing' : 'default'}>
                {currentTask.status === 'running' ? '运行中' : '最近任务'}
              </Tag>
              <Button type="link" size="small" onClick={() => navigate(`/runs/${currentTask.task_id}`)}>
                {currentTask.name || currentTask.task_id}
              </Button>
            </Space>
            {currentTask.progress && <Progress percent={currentTask.progress.percent} size="small" showInfo={false} />}
          </div>
        )}
        <Content className="arena-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
