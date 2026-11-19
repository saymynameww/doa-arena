/** 扫描能力来自 Schema；范围记忆独立于实际实验配置。 */
export type SweepSpec = { category: string; default?: string; when?: Record<string, any[]> };
export function sweepAvailable(spec: SweepSpec | undefined, values: any): boolean {
  return !!spec && ["scenario", "advanced", "algorithm"].includes(spec.category) &&
    Object.entries(spec.when || {}).every(([key, allowed]) => allowed.includes(values?.[key]));
}
export function selectSweepRange(ranges: Record<string, string>, path: string, spec: SweepSpec): string {
  return ranges[path] ?? spec.default ?? "";
}
export function restoreSweepRanges(saved: any, draft: any, useSaved = true): Record<string, string> {
  const ranges = useSaved ? { ...saved?.sweepRanges } : {};
  if (draft.sweep?.path) {
    ranges[draft.sweep.path] = useSaved && typeof saved?.range === "string"
      ? saved.range : ranges[draft.sweep.path] ?? draft.sweep.values?.join(", ") ?? "";
  }
  return ranges;
}
export function removeAlgorithmRanges(ranges: Record<string, string>, index: number): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [path, value] of Object.entries(ranges)) {
    const match = path.match(/^algorithms\[(\d+)\]/);
    if (!match) result[path] = value;
    else if (Number(match[1]) !== index) {
      const next = Number(match[1]) > index ? Number(match[1]) - 1 : Number(match[1]);
      result[path.replace(/^algorithms\[\d+\]/, `algorithms[${next}]`)] = value;
    }
  }
  return result;
}

export function activeSweepInfo(schema: any, draft: any): { spec?: SweepSpec; values?: any } {
  const path = draft.sweep?.path;
  if (!path) return {};
  let root = schema;
  let definition = schema;
  let values = draft;
  let parts = path.replace(/\[(\d+)\]/g, ".$1").split(".");
  if (parts[0] === "algorithms") {
    values = draft.algorithms[Number(parts[1])]?.params;
    root = schema["x-algorithms"].find((p: any) => p.id === draft.algorithms[Number(parts[1])]?.id)?.schema;
    definition = root; parts = parts.slice(3);
  } else if (parts.slice(0, 3).join(".") === "scenario.array.params") {
    values = draft.scenario.array.params;
    root = schema["x-arrays"].find((p: any) => p.id === draft.scenario.array.type)?.schema;
    definition = root; parts = parts.slice(3);
  } else if (parts.slice(0, 2).join(".") === "scenario.impairments") {
    const imp = draft.scenario.impairments[Number(parts[2])];
    values = imp?.params;
    root = schema["x-impairments"].find((p: any) => p.id === imp?.type)?.schema;
    definition = root; parts = parts.slice(4);
  }
  for (let i = 0; i < parts.length; i++) {
    if (definition?.$ref) definition = root?.$defs?.[definition.$ref.split("/").pop()];
    const field = definition?.properties?.[parts[i]];
    if (i === parts.length - 1) return { spec: field?.["x-sweep"], values };
    definition = field; values = values?.[parts[i]];
  }
  return {};
}
