import type { Task, ExperimentConfig } from "@/types";

export const experimentModes: Record<string, string> = {
  single: "单次实验",
  monte_carlo: "蒙特卡洛",
  sweep: "参数扫描",
};

export function compareReason(tasks: Task[]): string {
  if (tasks.length < 2) return "至少选择 2 个实验";
  if (tasks.length > 4) return "一次最多对比 4 个实验";
  if (tasks.some((t) => t.type !== "sweep")) return "只有参数扫描实验可以对比";
  if (tasks.some((t) => !t.has_results)) return "选中的实验尚无可用结果";
  if (new Set(tasks.map((t) => t.config.sweep?.path)).size !== 1)
    return "选中的实验扫描变量不同";
  return "";
}

export function editExperiment(config: ExperimentConfig) {
  sessionStorage.setItem(
    "arena.experimentDraft",
    JSON.stringify({ draft: config, range: config.sweep?.values.join(", ") }),
  );
}

export function flattenConfig(
  value: unknown,
  prefix = "",
): Record<string, string> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.fromEntries(
      Object.entries(value).flatMap(([key, item]) =>
        Object.entries(flattenConfig(item, prefix ? `${prefix}.${key}` : key)),
      ),
    );
  }
  return { [prefix]: JSON.stringify(value) ?? "—" };
}
