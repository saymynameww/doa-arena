"""独立实验进程入口；只通过原子文件交换状态和结果。"""

from __future__ import annotations

import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any

from ..config import ExperimentConfig
from ..storage import ResultWriter
from .core import run_experiment


def run_job(config: dict[str, Any], directory: str) -> None:
    """执行一个实验，保留取消前的完整块和异常详情。"""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    writer = ResultWriter(output)
    started = time.time()
    log = logging.FileHandler(output / "log.txt", encoding="utf-8")
    logging.getLogger().addHandler(log)
    last_update = 0.0

    def progress(completed: int, total: int, point: int, points: int) -> None:
        nonlocal last_update
        now = time.monotonic()
        if now - last_update < 0.2 and completed != total:
            return
        last_update = now
        elapsed = time.time() - started
        writer._write_json(
            output / "status.json",
            {
                "status": "running",
                "completed_trials": completed,
                "total_trials": total,
                "current_point": point,
                "total_points": points,
                "percent": int(100 * completed / total),
                "heartbeat": time.time(),
                "pid": os.getpid(),
                "eta_seconds": elapsed * (total - completed) / completed if completed else None,
            },
        )

    try:
        result = run_experiment(
            ExperimentConfig.model_validate(config),
            progress,
            cancel_callback=lambda: (output / "CANCEL").exists(),
            checkpoint_callback=writer.write_experiment,
        )
        writer.write_experiment(result)
        writer._write_json(
            output / "status.json",
            {
                "status": result.metadata["status"],
                "heartbeat": time.time(),
                "pid": os.getpid(),
                "completed_trials": sum(len(p.trials) for p in result.points),
                "total_trials": result.metadata["num_points"] * result.metadata["num_trials"],
                "percent": 100 if result.metadata["status"] == "completed" else None,
            },
        )
    except BaseException as exc:
        writer._write_json(
            output / "status.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "heartbeat": time.time(),
            },
        )
        raise
    finally:
        logging.getLogger().removeHandler(log)
        log.close()
