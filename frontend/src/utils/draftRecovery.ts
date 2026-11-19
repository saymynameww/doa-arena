/** 草稿允许处于编辑中；只有运行和保存时才要求配置完整有效。 */
export type DraftIssue = { level: string; message: string };

export function parseRange(text: string): number[] {
  const parts = text.trim().split(":").map(Number);
  if (parts.length === 3) {
    const [start, step, stop] = parts;
    if (
      !parts.every(Number.isFinite) ||
      step === 0 ||
      (stop - start) / step < 0 ||
      Math.abs((stop - start) / step) > 10000
    )
      throw Error("扫描范围应为起点:步长:终点，步长须指向终点且最多 10001 点");
    return Array.from(
      { length: Math.floor((stop - start) / step + 1e-9) + 1 },
      (_, i) => Number((start + i * step).toPrecision(12)),
    );
  }
  const values = text
    .split(/[,，\s]+/)
    .filter(Boolean)
    .map(Number);
  if (values.length < 2 || !values.every(Number.isFinite))
    throw Error("请填写至少两个有限数值，或使用起点:步长:终点");
  return values;
}

export function configurationErrors(error: any): DraftIssue[] {
  const detail = error?.response?.data?.detail;
  const fields = Array.isArray(detail) ? detail : detail?.errors;
  if (Array.isArray(fields)) return fields.map((field: any) => ({
    level: "error", message: `${field.path || field.loc?.join(".") || "配置"}：${field.message || field.msg}`,
  }));
  return [{ level: "error", message: typeof detail === "string" ? detail : error?.message || "配置校验失败，草稿已保留" }];
}

export async function restoreExperimentDraft(
  draft: any, range: string, normalize: (value: any) => Promise<any>,
): Promise<{ draft: any; issues: DraftIssue[] }> {
  // range 是用户当前输入，优先于上次选择变量时留下的空 values。
  let prepared = draft;
  try {
    if (draft.type === "sweep" && draft.sweep?.path) {
      try {
        prepared = { ...draft, sweep: { ...draft.sweep, values: parseRange(range) } };
      } catch (error) {
        return { draft, issues: [{ level: "error", message: `sweep.values（扫描取值）：${(error as Error).message}` }] };
      }
    }
    return { draft: await normalize(prepared), issues: [] };
  } catch (error) {
    // 不丢弃输入、不清空存储、不用默认值覆盖不合法字段。
    return { draft: prepared, issues: configurationErrors(error) };
  }
}
