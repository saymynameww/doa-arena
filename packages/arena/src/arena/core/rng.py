"""随机数派生树管理。

实现完全由种子决定的随机数派生，保证：
1. 并行与串行结果相同
2. 同一次试验所有算法使用相同数据
3. 中止后重跑结果相同
"""

from __future__ import annotations

from typing import Literal

import numpy as np


class RNGTree:
    """随机数派生树。

    从根种子派生出各个模块的子生成器，按固定路径派生。

    派生路径（架构 5.4 节）：
        root
        ├─ scenario (场景级)
        │  ├─ trial_0 (试验 0)
        │  │  ├─ sources (信源)
        │  │  ├─ noise (噪声)
        │  │  └─ impairments (误差)
        │  │     ├─ positions
        │  │     ├─ gain_phase
        │  │     └─ ...
        │  ├─ trial_1
        │  └─ ...
        └─ algorithms (算法，每个算法独立分支)
           ├─ music
           └─ ...
    """

    def __init__(self, seed: int) -> None:
        """初始化随机数树。

        Args:
            seed: 根种子
        """
        self.seed = seed
        self._root_seq = np.random.SeedSequence(seed)

    def for_scenario(self) -> np.random.Generator:
        """场景级随机数生成器。"""
        seq = self._root_seq.spawn(1)[0]
        return np.random.Generator(np.random.PCG64(seq))

    def for_trial(self, trial_idx: int) -> TrialRNG:
        """单次试验的随机数管理器。

        Args:
            trial_idx: 试验索引（从 0 开始）

        Returns:
            TrialRNG 实例
        """
        # 从 scenario 分支派生
        scenario_seq = self._root_seq.spawn(1)[0]
        trial_seq = scenario_seq.spawn(trial_idx + 1)[trial_idx]
        return TrialRNG(trial_seq)

    def for_algorithm(self, algorithm_id: str, trial_idx: int) -> np.random.Generator:
        """算法专用的随机数生成器。

        Args:
            algorithm_id: 算法 id
            trial_idx: 试验索引

        Returns:
            该算法该试验的随机数生成器
        """
        # 从 algorithms 分支派生
        algo_branch = self._root_seq.spawn(2)[1]  # [scenario, algorithms]
        # 使用 algorithm_id 的哈希作为子索引
        algo_hash = hash(algorithm_id) % (2**32)
        algo_seq = algo_branch.spawn(1, spawn_key=(algo_hash,))[0]
        # 再派生该算法的第 trial_idx 次试验
        trial_seq = algo_seq.spawn(trial_idx + 1)[trial_idx]
        return np.random.Generator(np.random.PCG64(trial_seq))


class TrialRNG:
    """单次试验的随机数管理。

    按固定顺序派生各部分的随机数。
    """

    def __init__(self, trial_seq: np.random.SeedSequence) -> None:
        """初始化。

        Args:
            trial_seq: 该试验的种子序列
        """
        self._seq = trial_seq
        self._counters: dict[str, int] = {}

    def for_sources(self, K: int | None = None) -> np.random.Generator:
        """信源随机数生成器。

        Args:
            K: 信源数（用于派生子生成器）

        Returns:
            信源生成器
        """
        idx = self._get_counter("sources")
        seq = self._seq.spawn(1, spawn_key=("sources", idx))[0]
        return np.random.Generator(np.random.PCG64(seq))

    def for_noise(self) -> np.random.Generator:
        """噪声随机数生成器。"""
        idx = self._get_counter("noise")
        seq = self._seq.spawn(1, spawn_key=("noise", idx))[0]
        return np.random.Generator(np.random.PCG64(seq))

    def for_impairment(
        self,
        impairment_type: str,
        realization_mode: Literal["fixed", "random"],
    ) -> np.random.Generator:
        """误差随机数生成器。

        Args:
            impairment_type: 误差类型 id
            realization_mode: "fixed" 或 "random"

        Returns:
            误差生成器
        """
        if realization_mode == "fixed":
            # 固定误差：所有试验使用 trial_0 的种子
            idx = 0
        else:
            # 每次随机：使用当前试验的计数器
            key = f"impairment_{impairment_type}"
            idx = self._get_counter(key)

        seq = self._seq.spawn(1, spawn_key=("impairment", impairment_type, idx))[0]
        return np.random.Generator(np.random.PCG64(seq))

    def _get_counter(self, key: str) -> int:
        """获取并递增计数器。"""
        count = self._counters.get(key, 0)
        self._counters[key] = count + 1
        return count


def validate_seed(seed: int) -> None:
    """验证种子值合法性。

    Args:
        seed: 种子值

    Raises:
        ValueError: 种子不合法
    """
    if not isinstance(seed, int):
        raise ValueError(f"种子必须是整数，实际类型为 {type(seed)}")
    if seed < 0 or seed >= 2**32:
        raise ValueError(f"种子必须在 [0, 2^32) 范围内，实际为 {seed}")
