/* eslint-disable react-hooks/exhaustive-deps -- subscription lifecycle is keyed by route id. */
import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
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
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  getTask,
  subscribeTaskProgress,
  getTaskResult,
  finalizePartialResult,
  cancelTask,
  rerunTask,
} from "@/services/api";
import ExperimentNotes from "@/components/ExperimentNotes";
import { editExperiment, experimentModes } from "@/utils/experimentViews";
import ResultCharts from "@/components/ResultCharts";
import ExportMenu from "@/components/ExportMenu";
import type { Task } from "@/types";

const ExperimentRunPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultPath, setResultPath] = useState<string | null>(null);

  const [resultVersion, setResultVersion] = useState(0);
  useEffect(() => {
    if (!id) return;
    setResultPath(null);
    setError(null);
    loadTask();

    // 订阅实时进度
    const eventSource = subscribeTaskProgress(
      id,
      (data) => {
        setTask((previous) => ({ ...previous, ...data }));

        // 任务完成时加载结果
        if (
          ["completed", "cancelled", "failed", "interrupted"].includes(
            data.status,
          )
        ) {
          loadResult();
        }
      },
      (err) => {
        console.error("进度订阅失败:", err);
      },
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
      if (
        ["completed", "cancelled", "failed", "interrupted"].includes(
          data.status,
        )
      ) {
        loadResult();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "加载任务失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (task?.status !== "running") return;
    const timer = window.setInterval(() => void loadResult(), 5000);
    return () => window.clearInterval(timer);
  }, [task?.status, id]);

  const loadResult = async () => {
    if (!id) return;

    try {
      const result = await getTaskResult(id);
      setResultPath(result.result_path);
      setResultVersion((v) => v + 1);
      setTask(await getTask(id));
    } catch (err) {
      console.error("加载结果失败:", err);
    }
  };

  const renderStatusTag = (status: string) => {
    const statusMap = {
      queued: { color: "default", icon: <SyncOutlined spin />, text: "等待中" },
      running: {
        color: "processing",
        icon: <SyncOutlined spin />,
        text: "运行中",
      },
      completed: {
        color: "success",
        icon: <CheckCircleOutlined />,
        text: "已完成",
      },
      failed: { color: "error", icon: <CloseCircleOutlined />, text: "失败" },
      cancelled: {
        color: "default",
        icon: <CloseCircleOutlined />,
        text: "已取消",
      },
      interrupted: {
        color: "warning",
        icon: <CloseCircleOutlined />,
        text: "已中断",
      },
    };

    const config =
      statusMap[status as keyof typeof statusMap] || statusMap.queued;

    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "100px 0" }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (error || !task) {
    return (
      <Alert
        message="错误"
        description={error || "任务不存在"}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={() => navigate("/history")}>
            返回历史实验
          </Button>
        }
      />
    );
  }

  const progress = task.progress || {
    current_point: 0,
    total_points: 1,
    eta_seconds: null,
    current_trial: 0,
    total_trials: 0,
    completed_trials: 0,
    percent: 0,
  };

  return (
    <div>
      <Space direction="vertical" style={{ width: "100%" }} size="large">
        {/* 顶部导航 */}
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/history")}
        >
          返回历史实验
        </Button>
        <Space wrap>
          <h2 style={{ margin: 0 }}>{task.name || task.task_id}</h2>
          <ExperimentNotes
            taskId={task.task_id}
            onComplete={() => void loadTask()}
          />
          <Button
            onClick={() => {
              editExperiment(task.config);
              navigate("/");
            }}
          >
            复制并编辑
          </Button>
          <Button
            onClick={() =>
              void rerunTask(task.task_id)
                .then((r) => navigate(`/runs/${r.task_id}`))
                .catch(() => setError("重跑失败，请重试"))
            }
          >
            重新运行
          </Button>
          {["queued", "running"].includes(task.status) && (
            <Button
              danger
              onClick={() => void cancelTask(task.task_id).then(loadTask)}
            >
              停止运行
            </Button>
          )}
        </Space>
        <Card size="small" title="实验条件">
          <Descriptions column={3} size="small">
            <Descriptions.Item label="实验方式">
              {experimentModes[task.type || "single"]}
            </Descriptions.Item>
            <Descriptions.Item label="试验次数">
              {task.config.trials}
            </Descriptions.Item>
            <Descriptions.Item label="算法">
              {task.config.algorithms
                ?.filter((a) => a.enabled !== false)
                .map((a) => a.label || a.id)
                .join("、")}
            </Descriptions.Item>
            <Descriptions.Item label="随机种子">
              {task.config.scenario?.seed}
            </Descriptions.Item>
            <Descriptions.Item label="扫描变量">
              {task.config.sweep?.label || task.config.sweep?.path || "无"}
            </Descriptions.Item>
            <Descriptions.Item label="备注">
              {task.notes || "暂无备注"}
            </Descriptions.Item>
          </Descriptions>
          <details>
            <summary>完整配置</summary>
            <pre style={{ whiteSpace: "pre-wrap" }}>
              {JSON.stringify(task.config, null, 2)}
            </pre>
          </details>
        </Card>

        {/* 任务状态卡片 */}
        <Card>
          <Row gutter={16}>
            <Col span={6}>
              <div>
                <small>
                  实验 ID ·{" "}
                  {task.mode === "web"
                    ? "网页运行"
                    : task.mode === "script"
                      ? "脚本运行"
                      : "运行模式未记录"}
                </small>
                <div>{task.task_id}</div>
              </div>
            </Col>
            <Col span={6}>
              <div>
                <div
                  style={{ color: "#8c8c8c", fontSize: 14, marginBottom: 8 }}
                >
                  状态
                </div>
                {renderStatusTag(task.status)}
              </div>
            </Col>
            <Col span={6}>
              <Statistic
                title="已用时间"
                value={
                  task.elapsed_seconds
                    ? `${task.elapsed_seconds.toFixed(1)} 秒`
                    : "-"
                }
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="已完成试验"
                value={
                  progress.total_trials
                    ? `${progress.completed_trials} / ${progress.total_trials}`
                    : "暂无进度记录"
                }
              />
            </Col>
          </Row>
        </Card>

        {/* 进度条 */}
        {task.status === "running" && (
          <Card title="实验进度">
            <Progress
              percent={progress.percent}
              status="active"
              strokeColor={{
                from: "#108ee9",
                to: "#87d068",
              }}
            />
            <div style={{ marginTop: 16, color: "#8c8c8c" }}>
              {progress.completed_trials} / {progress.total_trials} 次试验已完成
              {" · "}扫描点 {Math.min((progress.current_point || 0) + 1, progress.total_points || 1)} / {progress.total_points || 1}
              {" · "}预计剩余 {progress.eta_seconds == null ? "计算中" : `${Math.ceil(progress.eta_seconds)} 秒`}
            </div>
          </Card>
        )}
        {task.status === "running" &&
          (resultPath ? (
            <ResultCharts
              canRecompute={false}
              taskId={task.task_id}
              resultPath={resultPath}
              refreshKey={String(resultVersion)}
            />
          ) : (
            <Alert
              type="info"
              message="第一个完整试验块保存后，这里开始展示结果。"
            />
          ))}
        {["queued", "running"].includes(task.status) && (
          <ExperimentNotes
            inline
            taskId={task.task_id}
            onComplete={() => void getTask(task.task_id).then(setTask)}
          />
        )}

        {/* 错误信息 */}
        {task.status === "failed" && task.error && (
          <Alert
            message="实验失败"
            description={task.error}
            type="error"
            showIcon
          />
        )}

        {/* 完成信息 */}
        {task.status === "interrupted" && (
          <Alert
            type="warning"
            showIcon
            message="实验进程已中断"
            description={
              error || "可以整理最后已保存的完整试验块，或从历史页重新运行。"
            }
            action={
              <Button
                onClick={() =>
                  void finalizePartialResult(task.task_id)
                    .then(loadTask)
                    .catch((err) =>
                      setError(
                        err.response?.data?.detail || "整理部分结果失败",
                      ),
                    )
                }
              >
                整理部分结果
              </Button>
            }
          />
        )}
        {task.status === "cancelled" && (
          <Alert
            type="warning"
            showIcon
            message="实验已取消，结果仅包含已保存的试验"
          />
        )}
        {["cancelled", "failed", "interrupted"].includes(task.status) &&
          resultPath && (
            <div className="result-grid">
              <div>
                <ResultCharts
                  canRecompute={task.status === "completed"}
                  taskId={task.task_id}
                  resultPath={resultPath}
                />
              </div>
              <ExperimentNotes
                inline
                taskId={task.task_id}
                onComplete={() => void getTask(task.task_id).then(setTask)}
              />
            </div>
          )}
        {task.status === "completed" && (
          <>
            <Alert
              message="实验完成"
              description="结果已保存，可以查看图表和数据。"
              type="success"
              showIcon
              action={
                <ExportMenu
                  taskId={task.task_id}
                  resultPath={resultPath || undefined}
                />
              }
            />

            {/* 结果图表 */}
            {resultPath && (
              <div className="result-grid">
                <div>
                  <ResultCharts
                    canRecompute={task.status === "completed"}
                    taskId={task.task_id}
                    resultPath={resultPath}
                  />
                </div>
                <ExperimentNotes
                  inline
                  taskId={task.task_id}
                  onComplete={() => void getTask(task.task_id).then(setTask)}
                />
              </div>
            )}
          </>
        )}

        {/* 任务详情 */}
        <Card title="任务详情">
          <Descriptions column={2}>
            <Descriptions.Item label="创建时间">
              {new Date(task.created_at * 1000).toLocaleString("zh-CN")}
            </Descriptions.Item>
            {task.started_at && (
              <Descriptions.Item label="开始时间">
                {new Date(task.started_at * 1000).toLocaleString("zh-CN")}
              </Descriptions.Item>
            )}
            {task.completed_at && (
              <Descriptions.Item label="完成时间">
                {new Date(task.completed_at * 1000).toLocaleString("zh-CN")}
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      </Space>
    </div>
  );
};

export default ExperimentRunPage;
