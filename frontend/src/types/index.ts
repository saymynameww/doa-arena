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
  scenario?: ScenarioConfig;
  algorithms: AlgorithmInstance[];
  sweep?: SweepConfig;
  options?: Record<string, any>;
}

export interface ScenarioConfig {
  seed: number;
  array: { type: string; params: Record<string, any> };
  sources: {
    K: number;
    angles: { mode: string; values?: number[] };
    snr_db: number;
    correlation: { mode: string; rho_mag?: number | null; phases_deg?: string | number[] };
  };
  snapshots: number;
  noise_power: number;
  impairments: Array<Record<string, any>>;
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
  name?: string;
  type?: 'single' | 'monte_carlo' | 'sweep';
  config?: ExperimentConfig;
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

export interface ChartData {
  title: string;
  data: Array<Record<string, unknown>>;
  layout: Record<string, unknown>;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  type: string;
  algorithms: string[];
  createdAt: string;
  level?: string;
  config?: ExperimentConfig;
}

export interface ExperimentSchema {
  $defs?: Record<string, Record<string, any>>;
  properties?: Record<string, Record<string, any>>;
  ['x-algorithms']?: Algorithm[];
  ['x-sweep-paths']?: Array<{ path: string; label: string; unit: string }>;
}
