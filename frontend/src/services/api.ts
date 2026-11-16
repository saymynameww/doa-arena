import axios from 'axios';
import type {
  Algorithm,
  ChartData,
  ExperimentConfig,
  ExperimentSchema,
  Task,
  ExperimentResult,
  Template,
} from '@/types';

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

export const refreshAlgorithms = async (): Promise<{ algorithms: Algorithm[]; failures: any[]; sources: any[] }> => {
  const response = await api.post('/algorithms/refresh');
  return response.data;
};

export const getAlgorithm = async (id: string): Promise<Algorithm> => {
  const response = await api.get(`/algorithms/${id}`);
  return response.data;
};

export const getExperimentSchema = async (): Promise<ExperimentSchema> => {
  const response = await api.get('/schema/experiment');
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

export const getExperimentNotes = async (taskId: string) => {
  const response = await api.get<import('@/types/generated').ExperimentNotes>(`/experiments/tasks/${taskId}/notes`);
  return response.data;
};

export const saveExperimentNotes = async (taskId: string, notes: import('@/types/generated').ExperimentNotes) => {
  await api.put(`/experiments/tasks/${taskId}/notes`, notes);
};

export const getTaskResult = async (taskId: string): Promise<ExperimentResult> => {
  const response = await api.get(`/experiments/tasks/${taskId}/result`);
  return response.data;
};

export const finalizePartialResult = async (taskId: string) => {
  await api.post(`/experiments/tasks/${taskId}/finalize`);
};

export const getTaskCharts = async (taskId: string): Promise<ChartData[]> => {
  const response = await api.get(`/experiments/tasks/${taskId}/charts`);
  return response.data.charts;
};

export const recomputeTaskMetrics = async (taskId: string, metrics: Record<string, unknown>) => {
  const response = await api.post(`/experiments/tasks/${taskId}/recompute`, metrics);
  return response.data;
};

export const downloadTaskExport = async (taskId: string, format: string, options?: { chart?: string; metric?: string }): Promise<Blob> => {
  const response = await api.get(`/experiments/tasks/${taskId}/export/${format}`, {
    responseType: 'blob',
    params: options,
  });
  return response.data;
};

export const getTemplates = async (): Promise<Template[]> => {
  const response = await api.get('/templates');
  return response.data.templates;
};

export const createTemplate = async (template: Partial<Template>): Promise<Template> => {
  const response = await api.post('/templates', template);
  return response.data;
};

export const deleteTemplate = async (templateId: string): Promise<void> => {
  await api.delete(`/templates/${templateId}`);
};

export const updateTemplate = async (
  templateId: string,
  template: Partial<Template>
): Promise<Template> => {
  const response = await api.put(`/templates/${templateId}`, template);
  return response.data;
};

export const getSettings = async (): Promise<Record<string, any>> => {
  const response = await api.get('/settings');
  return response.data;
};

export const updateSettings = async (settings: Record<string, any>) => {
  const response = await api.put('/settings', settings);
  return response.data;
};

export const getWorkspaces = async (): Promise<Array<Record<string, any>>> => {
  const response = await api.get('/workspaces');
  return response.data.workspaces;
};

export const getCurrentWorkspace = async (): Promise<Record<string, any>> => {
  const response = await api.get('/workspaces/current');
  return response.data;
};

export const addWorkspace = async (workspace: Record<string, any>) => {
  const response = await api.post('/workspaces', workspace);
  return response.data;
};

export const getAlgorithmSources = async (): Promise<{ sources: any[]; failures: any[] }> => {
  const response = await api.get('/algorithms/sources');
  return response.data;
};

export const selectWorkspace = async (workspace: Record<string, any>) => {
  const response = await api.put('/workspaces/current', workspace);
  return response.data;
};

export const getLeaderboard = async (): Promise<{ rows: Array<Record<string, any>> }> => {
  const response = await api.get('/leaderboard');
  return response.data;
};

export const getLeaderboardScenarios = async (): Promise<{ scenarios: Array<Record<string, any>> }> => {
  const response = await api.get('/leaderboard/scenarios');
  return response.data;
};

export const rebuildWorkspaceIndex = async (): Promise<Record<string, any>> => {
  const response = await api.post('/workspaces/rebuild-index');
  return response.data;
};

export const copyTask = async (taskId: string) => {
  const response = await api.post(`/experiments/tasks/${taskId}/copy`);
  return response.data;
};

export const rerunTask = async (taskId: string) => {
  const response = await api.post(`/experiments/tasks/${taskId}/rerun`);
  return response.data;
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

export const validateExperiment = async (config: ExperimentConfig) => {
  const response = await api.post('/experiments/validate', config);
  return response.data as import('@/types/generated').ValidationResult;
};

export const getScenarioPreview = async (scenario: import('@/types/generated').ScenarioConfig) => {
  const response = await api.post<import('@/types/generated').ScenarioPreview>('/schema/preview', { scenario });
  return response.data;
};
