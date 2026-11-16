import { Button, Input, InputNumber, Select, Switch } from "antd";

export type JsonSchema = Record<string, any>;
export function resolveSchema(
  schema: JsonSchema,
  root: JsonSchema,
): JsonSchema {
  if (schema.$ref)
    return {
      ...resolveSchema(root.$defs?.[schema.$ref.split("/").pop()] || {}, root),
      ...schema,
      $ref: undefined,
    };
  return schema;
}
export function schemaDefault(raw: JsonSchema, root: JsonSchema): any {
  const s = resolveSchema(raw, root);
  if (s.default !== undefined) return structuredClone(s.default);
  if (s.type === "object" || s.properties)
    return Object.fromEntries(
      Object.entries(s.properties || {}).map(([k, v]) => [
        k,
        schemaDefault(v as JsonSchema, root),
      ]),
    );
  if (s.type === "array") return [];
  return undefined;
}
interface Props {
  schema: JsonSchema;
  root: JsonSchema;
  value: any;
  onChange: (value: any) => void;
  path: string;
  sweep?: string;
  sweepRange?: string;
  onRange?: (value: string) => void;
  onSweep?: (path: string, label: string) => void;
}
export default function ConfigFields({
  schema: raw,
  root,
  value,
  onChange,
  path,
  sweep,
  sweepRange,
  onRange,
  onSweep,
}: Props) {
  const schema = resolveSchema(raw, root);
  if (schema.anyOf) {
    const choices = schema.anyOf
      .map((s: JsonSchema) => resolveSchema(s, root))
      .filter((s: JsonSchema) => s.type !== "null");
    const type = Array.isArray(value)
      ? "array"
      : typeof value === "number"
        ? choices.find((s: JsonSchema) => s.type === "integer")
          ? "integer"
          : "number"
        : typeof value;
    const selected =
      choices.find((s: JsonSchema) => s.type === type) || choices[0];
    const merged = { ...schema, ...selected, anyOf: undefined };
    return (
      <>
        {choices.length > 1 && (
          <Select
            aria-label={`${path}输入方式`}
            value={selected.type}
            options={choices.map((s: JsonSchema) => ({
              value: s.type,
              label:
                (
                  {
                    object: "随机取值",
                    array: "逐项设置",
                    number: "统一数值",
                    integer: "固定",
                    string: "随机相位",
                  } as Record<string, string>
                )[s.type] || s.type,
            }))}
            onChange={(v) => {
              const target = choices.find((s: JsonSchema) => s.type === v);
              onChange(
                schemaDefault(target, root) ??
                  (v === "string" ? target.enum?.[0] || "random" : 2),
              );
            }}
          />
        )}
        <ConfigFields
          schema={merged}
          root={root}
          value={value}
          path={path}
          onChange={onChange}
          sweep={sweep}
          sweepRange={sweepRange}
          onRange={onRange}
          onSweep={onSweep}
        />
      </>
    );
  }
  if (schema.properties)
    return (
      <>
        {Object.entries(schema.properties).map(([key, field]) => {
          const spec = resolveSchema(field as JsonSchema, root);
          if (
            spec["x-visible-when"] &&
            !Object.entries(spec["x-visible-when"]).every(
              ([k, v]) => value?.[k] === v,
            )
          )
            return null;
          const child = `${path}.${key}`;
          const label =
            spec["x-label"] ||
            spec.label ||
            spec.description ||
            spec.title ||
            key;
          const numeric =
            ["number", "integer"].includes(spec.type) ||
            (spec.anyOf?.some((s: JsonSchema) =>
              ["number", "integer"].includes(s.type),
            ) &&
              (typeof value?.[key] === "number" || value?.[key] == null));
          return (
            <div
              key={key}
              className={`schema-field ${sweep === child ? "schema-field-scanned" : ""}`}
            >
              <label title={spec.description}>
                {label}
                {spec.unit ? ` (${spec.unit})` : ""}
              </label>
              <div className="schema-control">
                {sweep === child && onRange ? (
                  <Input
                    aria-label={`${child}扫描取值`}
                    value={sweepRange}
                    onChange={(e) => onRange(e.target.value)}
                    placeholder="起点:步长:终点"
                  />
                ) : (
                  <ConfigFields
                    schema={spec}
                    root={root}
                    value={value?.[key]}
                    onChange={(v) => onChange({ ...value, [key]: v })}
                    path={child}
                    sweep={sweep}
                    sweepRange={sweepRange}
                    onRange={onRange}
                    onSweep={onSweep}
                  />
                )}
              </div>
              {numeric && onSweep && (
                <Button
                  type="link"
                  size="small"
                  onClick={() => onSweep(child, label)}
                >
                  {sweep === child ? "取消扫描" : "扫描"}
                </Button>
              )}
            </div>
          );
        })}
      </>
    );
  if (schema.enum)
    return (
      <Select
        aria-label={path}
        value={value ?? schema.default}
        options={schema.enum.map((v: any) => ({
          value: v,
          label: schema["x-enum-labels"]?.[v] || String(v),
        }))}
        onChange={onChange}
      />
    );
  if (schema.type === "boolean")
    return (
      <Switch
        aria-label={path}
        checked={value ?? schema.default}
        onChange={onChange}
      />
    );
  if (["integer", "number"].includes(schema.type))
    return (
      <InputNumber
        aria-label={path}
        value={value ?? schema.default}
        min={schema.minimum}
        max={schema.maximum}
        step={schema.type === "integer" ? 1 : 0.1}
        onChange={onChange}
      />
    );
  if (schema.type === "array") {
    const itemSchema = schema.items || {};
    const values: any[] = Array.isArray(value) ? value : [];
    if (
      ["number", "integer"].includes(itemSchema.type) ||
      schema.prefixItems?.every((s: JsonSchema) =>
        ["number", "integer"].includes(s.type),
      )
    )
      return (
        <Input
          key={JSON.stringify(value)}
          aria-label={path}
          defaultValue={values.join(", ")}
          placeholder="逗号分隔数值"
          onBlur={(e) => {
            const text = e.target.value.trim();
            const next = text
              .split(/[,，\s]+/)
              .filter(Boolean)
              .map(Number);
            if (next.every(Number.isFinite)) onChange(text ? next : null);
          }}
        />
      );
    return (
      <div className="schema-array">
        {values.map((item, index) => (
          <div key={index} className="schema-array-item">
            <ConfigFields
              schema={schema.prefixItems?.[index] || itemSchema}
              root={root}
              value={item}
              onChange={(v) =>
                onChange(values.map((x, i) => (i === index ? v : x)))
              }
              path={`${path}[${index}]`}
              sweep={sweep}
              sweepRange={sweepRange}
              onRange={onRange}
              onSweep={onSweep}
            />
            <Button
              size="small"
              onClick={() => onChange(values.filter((_, i) => i !== index))}
            >
              移除
            </Button>
          </div>
        ))}
        <Button
          size="small"
          onClick={() =>
            onChange([
              ...values,
              schemaDefault(
                schema.prefixItems?.[values.length] || itemSchema,
                root,
              ) ?? 0,
            ])
          }
        >
          添加
        </Button>
        {value !== null && (
          <Button type="link" size="small" onClick={() => onChange(null)}>
            使用默认
          </Button>
        )}
      </div>
    );
  }
  return (
    <Input
      aria-label={path}
      value={value ?? schema.default ?? ""}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
