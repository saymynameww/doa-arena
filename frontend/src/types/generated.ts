// 自动生成：python scripts/generate_api_types.py；请勿手工编辑。

export type AlgorithmConfig = {
  "id": string;
  "origin"?: Record<string, unknown> | null;
  "label"?: string | null;
  "enabled"?: boolean;
  "params"?: Record<string, unknown>;
};

export type AnglesConfig = {
  "mode"?: "fixed" | "random" | "separation";
  "values"?: Array<number> | null;
  "range_deg"?: Array<unknown> | null;
  "center"?: number;
  "min_separation"?: number;
  "delta"?: number | null;
};

export type ArrayConfig = {
  "type"?: string;
  "origin"?: Record<string, unknown> | null;
  "carrier_hz"?: number;
  "params"?: Record<string, unknown>;
};

export type BenchmarkRunRecord = {
  "run_id": string;
  "suite_id": string;
  "suite_version": string;
  "suite_hash": string;
  "created_at": string;
  "algorithms": Array<AlgorithmConfig>;
  "experiments": Record<string, string>;
};

export type BenchmarkRunRequest = {
  "suite_id": string;
  "version": string;
  "algorithms": Array<AlgorithmConfig>;
  "scenarios"?: Array<string> | null;
};

export type ChartData = {
  "title": string;
  "data": Array<Record<string, unknown>>;
  "layout": Record<string, unknown>;
};

export type ChartList = {
  "charts": Array<ChartData>;
};

export type CorrelationConfig = {
  "mode"?: "none" | "partial" | "coherent";
  "rho_mag"?: number | null;
  "rho_phase_deg"?: number;
  "phases_deg"?: "random" | Array<number>;
};

export type ExperimentConfig = {
  "schema_version"?: 1;
  "description"?: string;
  "tags"?: Array<string>;
  "name"?: string;
  "scenario"?: ScenarioConfig;
  "algorithms"?: Array<AlgorithmConfig>;
  "type"?: ExperimentType;
  "trials"?: number;
  "sweep"?: SweepConfig | null;
  "metrics"?: MetricsConfig;
  "options"?: ExperimentOptions;
};

export type ExperimentNotes = {
  "schema_version"?: number;
  "display_name"?: string | null;
  "notes"?: string;
  "tags"?: Array<string>;
  "starred"?: boolean;
  "updated_at"?: string;
};

export type ExperimentOptions = {
  "chunk_size"?: number;
  "max_consecutive_errors"?: number;
  "source_count"?: "true" | "mdl" | "aic";
  "save_spectra"?: "auto" | "all" | "none";
  "save_observations"?: "auto" | "none";
  "workers"?: number;
  "common_random_numbers"?: boolean;
  "warmup"?: boolean;
  "save_estimates"?: boolean;
};

export type ExperimentType = "single" | "monte_carlo" | "sweep";

export type HTTPValidationError = {
  "detail"?: Array<ValidationError>;
};

export type ImpairmentConfig = {
  "type": string;
  "origin"?: Record<string, unknown> | null;
  "label"?: string | null;
  "enabled"?: boolean;
  "realization"?: "fixed" | "per_trial";
  "params"?: Record<string, unknown>;
};

export type LeaderboardResponse = {
  "suite_id": string;
  "version": string;
  "columns": Array<Record<string, unknown>>;
  "rows": Array<Record<string, unknown>>;
  "revisions": Array<Record<string, string>>;
  "failures": Array<string>;
};

export type MetricParameters = {
  "success_rate"?: SuccessParameters;
  "rmse"?: RmseParameters;
};

export type MetricsConfig = {
  "include"?: Array<string>;
  "params"?: MetricParameters;
  "origins"?: Record<string, Record<string, unknown>>;
};

export type ModelImportRequest = {
  "path": string;
};

export type ModelInspection = {
  "metadata": Record<string, unknown>;
  "checks": Array<string>;
  "warnings": Array<string>;
};

export type ModelList = {
  "models": Array<ModelRecord>;
  "failures": Array<string>;
};

export type ModelRecord = {
  "path": string;
  "name": string;
  "algorithm_id": string;
  "metadata": Record<string, unknown>;
};

export type ParamSchema = {
  "type"?: string;
  "default"?: unknown;
  "min"?: number | null;
  "max"?: number | null;
  "enum"?: Array<string> | null;
  "description"?: string;
};

export type PluginInfo = {
  "kind": string;
  "id": string;
  "name": string;
  "version": string;
  "type": "builtin" | "external";
  "description": string;
  "category": string;
  "params": Record<string, ParamSchema>;
  "schema": Record<string, unknown>;
  "capabilities": Record<string, unknown>;
  "origin": Record<string, unknown> | null;
  "defaults": Record<string, unknown>;
};

export type PluginList = {
  "algorithms": Array<PluginInfo>;
  "arrays": Array<PluginInfo>;
  "impairments": Array<PluginInfo>;
  "metrics": Array<PluginInfo>;
  "failures": Array<Record<string, unknown>>;
  "sources": Array<Record<string, unknown>>;
};

export type RandomSourceCount = {
  "values"?: Array<number>;
  "weights"?: Array<number> | null;
};

export type ResultFiles = {
  "task_id": string;
  "result_path": string;
  "files": Array<string>;
};

export type RmseParameters = {
  "include_failed"?: boolean;
  "penalty_deg"?: number;
};

export type ScenarioConfig = {
  "seed"?: number;
  "array"?: ArrayConfig;
  "sources"?: SourcesConfig;
  "snapshots"?: number;
  "noise_power"?: number;
  "noise"?: "white_gaussian";
  "impairments"?: Array<ImpairmentConfig>;
};

export type ScenarioPreview = {
  "elements": number;
  "angles": Array<number>;
  "physical_spacing_cm": number | null;
};

export type SourcesConfig = {
  "K"?: number | RandomSourceCount;
  "signal"?: "gaussian";
  "angles"?: AnglesConfig;
  "snr_db"?: number | Array<number>;
  "correlation"?: CorrelationConfig;
};

export type SuccessParameters = {
  "threshold_deg"?: number;
};

export type SuiteList = {
  "suites": Array<Record<string, unknown>>;
};

export type SweepConfig = {
  "path": string;
  "values": Array<number>;
  "label"?: string | null;
  "unit"?: string | null;
};

export type TaskList = {
  "tasks": Array<TaskResponse>;
};

export type TaskProgress = {
  "current_point"?: number;
  "total_points"?: number;
  "current_trial"?: number;
  "total_trials"?: number;
  "completed_trials"?: number;
  "percent"?: number;
};

export type TaskResponse = {
  "task_id": string;
  "status": "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  "created_at": number;
  "started_at"?: number | null;
  "completed_at"?: number | null;
  "elapsed_seconds"?: number | null;
  "error"?: string | null;
  "name"?: string;
  "type"?: "single" | "monte_carlo" | "sweep";
  "config": ExperimentConfig;
  "progress"?: TaskProgress | null;
  "notes"?: string;
  "tags"?: Array<string>;
  "starred"?: boolean;
};

export type Template = {
  "id": string;
  "name": string;
  "description"?: string;
  "type"?: string;
  "algorithms"?: Array<string>;
  "createdAt"?: string;
  "level"?: string;
  "config"?: ExperimentConfig;
};

export type TemplateList = {
  "templates": Array<Template>;
};

export type ValidationError = {
  "loc": Array<string | number>;
  "msg": string;
  "type": string;
  "input"?: unknown;
  "ctx"?: Record<string, unknown>;
};

export type ValidationIssue = {
  "level": "error" | "warning";
  "message": string;
  "algorithm"?: string | null;
  "point"?: number | null;
  "param"?: string | null;
  "component"?: string | null;
};

export type ValidationResult = {
  "valid": boolean;
  "issues": Array<ValidationIssue>;
};
