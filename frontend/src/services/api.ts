import axios from 'axios';
import type { Algorithm, ChartData, ExperimentConfig, Task, ExperimentResult, Template } from '@/types';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// 健康检查
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// 算法相关
export const getAlgorithms = async (): Promise<Algorithm[]> => {
  const response = await api.get('/algorithms');
  return response.data.algorithms;
};

export const getAlgorithm = async (id: string): Promise<Algorithm> => {
  const response = await api.get(`/algorithms/${id}`);
  return response.data;
};

// 实验相关
export const runExperiment = async (config: ExperimentConfig) => {
  const response = await api.post('/experiments/run', config);
  return response.data;
};

export const getTasks = async (): Promise<Task[]> => {
  const response = await api.get('/experiments/tasks');
  return response.data.tasks;
};

export const getTask = async (taskId: string): Promise<Task> => {
  const response = await api.get(`/experiments/tasks/${taskId}`);
  return response.data;
};

export const getTaskResult = async (taskId: string): Promise<ExperimentResult> => {
  const response = await api.get(`/experiments/tasks/${taskId}/result`);
  return response.data;
};

export const getTaskCharts = async (taskId: string): Promise<ChartData[]> => {
  const response = await api.get(`/experiments/tasks/${taskId}/charts`);
  return response.data.charts;
};

export const downloadTaskExport = async (taskId: string, format: string): Promise<Blob> => {
  const response = await api.get(`/experiments/tasks/${taskId}/export/${format}`, {
    responseType: 'blob',
  });
  return response.data;
};

export const getTemplates = async (): Promise<Template[]> => {
  const response = await api.get('/templates');
  return response.data.templates;
};

export const deleteTemplate = async (templateId: string): Promise<void> => {
  await api.delete(`/templates/${templateId}`);
};

export const cancelTask = async (taskId: string) => {
  const response = await api.delete(`/experiments/tasks/${taskId}`);
  return response.data;
};

// SSE 进度订阅
export const subscribeTaskProgress = (
  taskId: string,
  onMessage: (data: any) => void,
  onError?: (error: any) => void
) => {
  const eventSource = new EventSource(`/api/experiments/tasks/${taskId}/progress`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);

    // 任务完成，关闭连接
    if (['completed', 'failed', 'cancelled'].includes(data.status)) {
      eventSource.close();
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE error:', error);
    if (onError) onError(error);
    eventSource.close();
  };

  return eventSource;
};
