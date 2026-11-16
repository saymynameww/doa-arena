// API 类型定义

import type { PluginInfo as Algorithm } from './generated';
export type { PluginInfo as Algorithm } from './generated';

export type { ParamSchema } from './generated';

export type { ExperimentConfig, ScenarioConfig, SweepConfig } from './generated';
export type { AlgorithmConfig as AlgorithmInstance } from './generated';

export type {
  TaskResponse as Task,
  TaskProgress,
  ResultFiles as ExperimentResult,
  ChartData,
  Template,
} from './generated';

export interface ExperimentSchema {
  $defs?: Record<string, Record<string, any>>;
  properties?: Record<string, Record<string, any>>;
  ['x-algorithms']?: Algorithm[];
  ['x-sweep-paths']?: Array<{ path: string; label: string; unit: string }>;
}
