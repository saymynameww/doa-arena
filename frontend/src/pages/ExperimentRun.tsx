/* eslint-disable react-hooks/exhaustive-deps -- subscription lifecycle is keyed by route id. */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Progress,
  Statistic,
  Row,
  Col,
  Alert,
  Button,
  Space,
  Spin,
  Descriptions,
  Tag,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { getTask, subscribeTaskProgress, getTaskResult } from '@/services/api';
import ResultCharts from '@/components/ResultCharts';
import ExportMenu from '@/components/ExportMenu';
import type { Task } from '@/types';

const ExperimentRunPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultPath, setResultPath] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    loadTask();

    // 订阅实时进度
    const eventSource = subscribeTaskProgress(
      id,
      (data) => {
        setTask((previous) => ({ ...previous, ...data }));

        // 任务完成时加载结果
        if (data.status === 'completed') {
          loadResult();
        }
      },
      (err) => {
        console.error('进度订阅失败:', err);
      }
    );

    return () => {
      eventSource.close();
    };
  }, [id]);

  const loadTask = async () => {
    if (!id) return;

    try {
      setLoading(true);
      const data = await getTask(id);
      setTask(data);

      // 如果已完成，加载结果
      if (data.status === 'completed') {
        loadResult();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载任务失败');
    } finally {
      setLoading(false);
    }
  };

  const loadResult = async () => {
    if (!id) return;

    try {
      const result = await getTaskResult(id);
      setResultPath(result.result_path);
    } catch (err) {
      console.error('加载结果失败:', err);
    }
  };

  const renderStatusTag = (status: string) => {
    const statusMap = {
      pending: { color: 'default', icon: <SyncOutlined spin />, text: '等待中' },
      running: { color: 'processing', icon: <SyncOutlined spin />, text: '运行中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      cancelled: { color: 'default', icon: <CloseCircleOutlined />, text: '已取消' },
    };

    const config = statusMap[status as keyof typeof statusMap] || statusMap.pending;

    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (error || !task) {
    return (
      <Alert
        message="错误"
        description={error || '任务不存在'}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={() => navigate('/history')}>
            返回历史实验
          </Button>
        }
      />
    );
  }

  const progress = task.progress || {
    current_trial: 0,
    total_trials: 0,
    completed_trials: 0,
    percent: 0,
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 顶部导航 */}
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/history')}>
          返回历史实验
        </Button>

        {/* 任务状态卡片 */}
        <Card>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="任务 ID" value={task.task_id} />
            </Col>
            <Col span={6}>
              <div>
                <div style={{ color: '#8c8c8c', fontSize: 14, marginBottom: 8 }}>状态</div>
                {renderStatusTag(task.status)}
              </div>
            </Col>
            <Col span={6}>
              <Statistic
                title="已用时间"
                value={
                  task.elapsed_seconds
                    ? `${task.elapsed_seconds.toFixed(1)} 秒`
                    : '-'
                }
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="当前试验"
                value={`${progress.current_trial} / ${progress.total_trials}`}
              />
            </Col>
          </Row>
        </Card>

        {/* 进度条 */}
        {task.status === 'running' && (
          <Card title="实验进度">
            <Progress
              percent={progress.percent}
              status="active"
              strokeColor={{
                from: '#108ee9',
                to: '#87d068',
              }}
            />
            <div style={{ marginTop: 16, color: '#8c8c8c' }}>
              {progress.completed_trials} / {progress.total_trials} 次试验已完成
            </div>
          </Card>
        )}

        {/* 错误信息 */}
        {task.status === 'failed' && task.error && (
          <Alert
            message="实验失败"
            description={task.error}
            type="error"
            showIcon
          />
        )}

        {/* 完成信息 */}
        {task.status === 'completed' && (
          <>
            <Alert
              message="实验完成"
              description="结果已保存，可以查看图表和数据。"
              type="success"
              showIcon
              action={
                <ExportMenu taskId={task.task_id} resultPath={resultPath || undefined} />
              }
            />

            {/* 结果图表 */}
            {resultPath && (
              <ResultCharts taskId={task.task_id} resultPath={resultPath} />
            )}
          </>
        )}

        {/* 任务详情 */}
        <Card title="任务详情">
          <Descriptions column={2}>
            <Descriptions.Item label="创建时间">
              {new Date(task.created_at * 1000).toLocaleString('zh-CN')}
            </Descriptions.Item>
            {task.started_at && (
              <Descriptions.Item label="开始时间">
                {new Date(task.started_at * 1000).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
            {task.completed_at && (
              <Descriptions.Item label="完成时间">
                {new Date(task.completed_at * 1000).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      </Space>
    </div>
  );
};

export default ExperimentRunPage;
