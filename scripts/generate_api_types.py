"""从服务 OpenAPI 生成配置类型；--check 用于检查提交内容是否过期。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arena.server.app import create_app


def typescript(schema: dict[str, Any]) -> str:
    """转换本项目 OpenAPI 使用的 JSON Schema 结构。"""
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "const" in schema:
        return json.dumps(schema["const"], ensure_ascii=False)
    if "enum" in schema:
        return " | ".join(json.dumps(item, ensure_ascii=False) for item in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(typescript(item) for item in schema["anyOf"])
    kind = schema.get("type")
    if kind == "array":
        return f"Array<{typescript(schema.get('items', {}))}>"
    if kind == "object":
        properties = schema.get("properties", {})
        if not properties:
            extra = schema.get("additionalProperties", {})
            return f"Record<string, {typescript(extra) if isinstance(extra, dict) else 'unknown'}>"
        required = schema.get("required", [])
        return (
            "{\n"
            + "\n".join(
                f"  {json.dumps(name)}{'' if name in required else '?'}: {typescript(value)};"
                for name, value in properties.items()
            )
            + "\n}"
        )
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }.get(kind, "unknown")


def main() -> None:
    """生成确定性的声明或在 CI 中验证声明。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schemas = create_app().openapi()["components"]["schemas"]
    content = "// 自动生成：python scripts/generate_api_types.py；请勿手工编辑。\n\n"
    content += (
        "\n\n".join(
            f"export type {name} = {typescript(schema)};"
            for name, schema in sorted(schemas.items())
        )
        + "\n"
    )
    target = Path(__file__).resolve().parents[1] / "frontend/src/types/generated.ts"
    if args.check:
        if target.read_text(encoding="utf-8") != content:
            raise SystemExit("API 类型已过期，请运行 python scripts/generate_api_types.py")
    else:
        target.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
