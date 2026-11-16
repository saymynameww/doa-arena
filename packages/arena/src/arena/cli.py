"""命令行入口，与脚本和 Web 共享核心执行器。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    """解析命令行参数并运行实验或本地服务。"""
    parser = argparse.ArgumentParser(prog="arena", description="DOA 算法竞技场")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="运行 JSON/YAML 配置或已有实验目录")
    run_parser.add_argument("config", type=Path)
    run_parser.add_argument("--workspace", type=Path, default=Path("arena_workspace"))
    serve_parser = commands.add_parser("serve", help="启动本地 Web 服务")
    serve_parser.add_argument("--port", type=int, default=8765)
    dataset_parser = commands.add_parser("dataset", help="生成训练数据集")
    dataset_commands = dataset_parser.add_subparsers(dest="dataset_command", required=True)
    generate_parser = dataset_commands.add_parser("generate", help="可恢复地生成 npz 分片")
    generate_parser.add_argument("config", type=Path)
    generate_parser.add_argument("--out", type=Path, required=True)
    generate_parser.add_argument("--range", dest="sample_range", help="全局索引区间 start:stop")
    schema_parser = commands.add_parser("schema", help="导出配置 JSON Schema")
    schema_parser.add_argument("action", choices=["export"])
    schema_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            if args.config.is_dir():
                from .core.runner.job import run_job

                config = json.loads((args.config / "config.json").read_text(encoding="utf-8"))
                run_job(config, str(args.config))
            else:
                from .core.facade import run

                result = run(args.config, workspace=args.workspace)
                print(result.metadata["directory"])
        elif args.command == "dataset":
            from .core.datasets import generate

            start, stop = 0, None
            if args.sample_range:
                start, stop = map(int, args.sample_range.split(":"))
            print(generate(args.config, args.out, start=start, stop=stop))
        elif args.command == "schema":
            from arena_api import ModelMeta

            from .core.config import ExperimentConfig
            from .core.datasets import DatasetConfig
            from .core.storage.writer import ResultWriter

            writer = ResultWriter(args.out)
            for name, model in (
                ("experiment", ExperimentConfig),
                ("dataset", DatasetConfig),
                ("model", ModelMeta),
            ):
                writer._write_json(args.out / f"{name}.schema.json", model.model_json_schema())
        else:
            import uvicorn

            uvicorn.run(
                "arena.server.app:create_app", factory=True, host="127.0.0.1", port=args.port
            )
    except (ValueError, OSError) as exc:
        parser.exit(1, f"运行失败：{exc}\n请检查配置与文件路径后重试。\n")
