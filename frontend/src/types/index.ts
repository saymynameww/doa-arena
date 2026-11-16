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

import type { ExperimentConfig } from './generated';
export type { ExperimentConfig, ScenarioConfig, SweepConfig } from './generated';
export type { AlgorithmConfig as AlgorithmInstance } from './generated';

export interface Task {
  notes?: string;
  tags?: string[];
  starred?: boolean;
  task_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
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
