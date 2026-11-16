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
  "carrier_hz"?: number;
  "params"?: Record<string, unknown>;
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
  "label"?: string | null;
  "enabled"?: boolean;
  "realization"?: "fixed" | "per_trial";
  "params"?: Record<string, unknown>;
};

export type MetricParameters = {
  "success_rate"?: SuccessParameters;
  "rmse"?: RmseParameters;
};

export type MetricsConfig = {
  "include"?: Array<string>;
  "params"?: MetricParameters;
};

export type RandomSourceCount = {
  "values"?: Array<number>;
  "weights"?: Array<number> | null;
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

export type SweepConfig = {
  "path": string;
  "values": Array<number>;
  "label"?: string | null;
  "unit"?: string | null;
};

export type ValidationError = {
  "loc": Array<string | number>;
  "msg": string;
  "type": string;
  "input"?: unknown;
  "ctx"?: Record<string, unknown>;
};
