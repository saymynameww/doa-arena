"""中断后的标准扫描点检查点合并。"""

import json
from pathlib import Path

import numpy as np

from ..runner.results import ExperimentResult
from .reader import read_result
from .writer import ResultWriter


def finalize_directory(directory: Path) -> ExperimentResult:
    """保留最后原子检查点，缺少总文件时由扫描点恢复，再标记部分结果。"""
    directory = Path(directory)
    writer = ResultWriter(directory)
    files = sorted((directory / "points").glob("p_*.npz"))
    if not (directory / "results.npz").exists():
        if not files:
            raise ValueError("中断前没有完整检查点，请重新运行")
        points = []
        for file in files:
            with np.load(file, allow_pickle=False) as raw:
                points.append({key: raw[key] for key in raw.files})
        arrays = {}
        for key in set.intersection(*(set(point) for point in points)):
            values = [point[key] for point in points]
            if key.startswith("impairment__") or (
                key.startswith("spectrum__") and not key.endswith("__values")
            ):
                arrays[key] = values[0]
                continue
            shape = tuple(max(value.shape[i] for value in values) for i in range(values[0].ndim))
            fill = 7 if key == "status" else (np.nan if values[0].dtype.kind in "fc" else -1)
            joined = np.full((len(values), *shape), fill, dtype=values[0].dtype)
            for i, value in enumerate(values):
                if value.ndim:
                    joined[i][tuple(slice(0, n) for n in value.shape)] = value
                else:
                    joined[i] = value
            arrays[key] = joined
        writer._write_npz(directory / "results.npz", arrays)
    result = read_result(directory)
    result.metadata["status"] = "cancelled"
    writer.write_experiment(result)
    writer._write_json(directory / "status.json", {"schema_version": 1, "status": "cancelled"})
    result.saved_summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    return result
