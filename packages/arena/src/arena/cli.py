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
        else:
            import uvicorn

            uvicorn.run(
                "arena.server.app:create_app", factory=True, host="127.0.0.1", port=args.port
            )
    except (ValueError, OSError) as exc:
        parser.exit(1, f"运行失败：{exc}\n请检查配置与文件路径后重试。\n")
