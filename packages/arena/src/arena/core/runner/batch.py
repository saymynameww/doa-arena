"""批量调用共享逐次随机路径，计时按批大小均摊。"""

import time
from dataclasses import replace

from arena_api import Algorithm, Estimate, RunContext

from ..config import ExperimentConfig
from ..rng import RNGTree

BatchResults = dict[int, dict[str, tuple[Estimate | Exception, float]]]


def execute_batches(
    config: ExperimentConfig,
    point_index: int,
    indices: list[int],
    algorithms: dict[str, Algorithm],
    ctx: RunContext,
) -> BatchResults:
    """仅执行声明支持批量的插件，保留每次试验对应的错误。"""
    from .core import build_scene
    from .source_count import estimate_source_count

    batch_algorithms = {
        label: algo for label, algo in algorithms.items() if algo.capabilities.batch
    }
    # 随机已知掩码要求每次重新 configure，不能共享同一批次阵列描述。
    if any(item.enabled and item.params.get("known") for item in config.scenario.impairments):
        return {}
    if not batch_algorithms:
        return {}
    observations = []
    random_indices = []
    for index in indices:
        random_index = (
            index if config.options.common_random_numbers else point_index * config.trials + index
        )
        scene, _ = build_scene(config, random_index)
        obs = scene.generate(RNGTree(config.scenario.seed).for_trial(random_index))
        if config.options.source_count != "true":
            obs = replace(obs, K=estimate_source_count(obs, config.options.source_count))
        observations.append(obs)
        random_indices.append(random_index)
    results: BatchResults = {index: {} for index in indices}
    for label, algo in batch_algorithms.items():
        rngs = tuple(
            RNGTree(config.scenario.seed)
            .for_trial(index)
            .for_impairment("algorithm:" + label, "random")
            for index in random_indices
        )
        batch_ctx = replace(ctx, rng=rngs[0], _batch_rngs=rngs)
        try:
            start = time.perf_counter()
            estimates = algo.estimate_batch(observations, batch_ctx)
            if algo.capabilities.uses_gpu and getattr(algo, "device_str", "cuda").startswith(
                "cuda"
            ):
                import torch

                if torch.cuda.is_available():
                    torch.cuda.synchronize(getattr(algo, "device_str", None))
            elapsed = (time.perf_counter() - start) * 1000 / len(indices)
            if len(estimates) != len(indices):
                raise ValueError("bad_output：批量输出数量必须与观测数量相同")
            for index, estimate in zip(indices, estimates):
                results[index][label] = (estimate, elapsed)
        except Exception as exc:
            for index in indices:
                results[index][label] = (exc, 0.0)
    return results
