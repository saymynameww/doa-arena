import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button, Progress, Select } from 'antd';
import {
  ExperimentOutlined,
  HistoryOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SettingOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { getCurrentWorkspace, getTasks, getWorkspaces, selectWorkspace } from '@/services/api';
import type { Task } from '@/types';

const { Sider, Content } = Layout;
const { Title } = Typography;

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [workspaces, setWorkspaces] = useState<Array<Record<string, any>>>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Record<string, any>>({});

  useEffect(() => {
    void Promise.all([getTasks(), getWorkspaces(), getCurrentWorkspace()]).then(([loadedTasks, loadedWorkspaces, loadedCurrent]) => {
      setTasks(loadedTasks);
      setWorkspaces(loadedWorkspaces);
      setCurrentWorkspace(loadedCurrent);
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
    void selectWorkspace(workspace).then((selected) => {
      setCurrentWorkspace(selected);
      window.location.reload();
    });
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        className="arena-sider"
        width={200}
        style={{
          background: '#0f1b2d',
        }}
      >
        <div className="arena-brand">
          <Title level={4} style={{ margin: 0, color: '#fff' }}>
            DOA 竞技场
          </Title>
        </div>
        <div className="arena-workspace">
          <Typography.Text style={{ color: 'rgba(255,255,255,0.65)' }}>工作目录</Typography.Text>
          <Select
            size="small"
            value={currentWorkspace.name || currentWorkspace.path || workspaces[0]?.name || '当前工作目录'}
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
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
        {currentTask && (
          <div className="arena-current-task">
            <Typography.Text className="arena-task-label">
              {currentTask.status === 'running' ? '当前任务' : '最近查看'}
            </Typography.Text>
            <Button type="link" size="small" onClick={() => navigate(`/runs/${currentTask.task_id}`)}>
              {currentTask.name || currentTask.task_id}
            </Button>
            {currentTask.progress && <Progress percent={currentTask.progress.percent} size="small" showInfo={false} />}
          </div>
        )}
      </Sider>
      <Layout>
        <Content className="arena-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
