// API 类型定义

export interface Algorithm {
  id: string;
  name: string;
  description: string;
  type: string;
  params: Record<string, ParamSchema>;
}

export interface ParamSchema {
  type: string;
  default?: any;
  min?: number;
  max?: number;
  enum?: string[];
  description?: string;
}

export interface ExperimentConfig {
  name: string;
  type: 'single' | 'monte_carlo' | 'sweep';
  trials: number;
  scenario?: {
    seed?: number;
    snapshots?: number;
  };
  algorithms: AlgorithmInstance[];
  sweep?: SweepConfig;
  options?: Record<string, any>;
}

export interface AlgorithmInstance {
  id: string;
  label: string;
  params?: Record<string, any>;
}

export interface SweepConfig {
  path: string;
  values: number[];
  label: string;
  unit: string;
}

export interface Task {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: number;
  started_at?: number;
  completed_at?: number;
  elapsed_seconds?: number;
  error?: string;
  progress?: TaskProgress;
}

export interface TaskProgress {
  current_point?: number;
  total_points?: number;
  current_trial: number;
  total_trials: number;
  completed_trials: number;
  percent: number;
}

export interface ExperimentResult {
  task_id: string;
  result_path: string;
  files: string[];
}
