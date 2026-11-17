"""记录真实示例 CNN 的批量速度、显存和插件一致性验收。"""

import argparse
import json
import logging
import statistics
import time
from pathlib import Path

from arena.core.config import ExperimentConfig
from arena.core.plugin_check import check_plugin
from arena.core.plugins import discover, resolve_algorithm
from arena.core.rng import RNGTree
from arena.core.runner.core import build_scene
from arena.core.storage.writer import ResultWriter
from arena_api import RunContext


def main() -> None:
    """使用用户指定课题中的已训练模型，不改动课题代码或基础环境。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("需要可用 CUDA 环境")
    project = args.project.resolve()
    catalog = discover(
        [{"type": "path", "value": str(project / "algorithms"), "import_root": str(project)}]
    )
    entry = next(a for a in catalog["algorithms"] if a["category"] == "learning")
    cls = resolve_algorithm(entry["id"], entry["origin"])
    parameters = {
        "model": str(project / "arena_ws/models/cnn_demo"),
        "device": "cuda",
        "batch_size": 256,
    }
    checked = check_plugin(cls, parameters, "cuda", project / "arena_ws")
    scene, array = build_scene(ExperimentConfig.model_validate({}))
    tree = RNGTree(12345)
    observations = [scene.generate(tree.for_trial(i)) for i in range(256)]
    ctx = RunContext(
        "cuda", logging.getLogger("gpu-performance"), False, project, tree.for_algorithm(cls.id, 0)
    )
    algorithm = cls()
    params = cls.Params.model_validate(parameters)
    torch.cuda.reset_peak_memory_stats()
    try:
        algorithm.load(params, ctx)
        algorithm.configure(params, array, ctx)
        algorithm.estimate_batch(observations, ctx)
        samples = {"batch_seconds": [], "single_seconds": []}
        for _ in range(5):
            for name in samples:
                torch.cuda.synchronize()
                start = time.perf_counter()
                if name == "batch_seconds":
                    algorithm.estimate_batch(observations, ctx)
                else:
                    for observation in observations:
                        algorithm.estimate(observation, ctx)
                torch.cuda.synchronize()
                samples[name].append(time.perf_counter() - start)
        summary = {name: statistics.median(values) for name, values in samples.items()}
        summary["speedup"] = summary["single_seconds"] / summary["batch_seconds"]
        data = {
            "gpu": torch.cuda.get_device_name(),
            "torch": torch.__version__,
            "samples": 256,
            "timings": samples,
            "median": summary,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "plugin_check": checked,
        }
        ResultWriter(args.out.parent)._write_json(args.out, data)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        assert checked["passed"], checked
        assert summary["speedup"] > 1, summary
        assert data["peak_reserved_bytes"] < 8 * 1024**3
    finally:
        algorithm.close()


if __name__ == "__main__":
    main()
