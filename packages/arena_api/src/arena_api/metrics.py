"""指标计算相关类型。"""

from dataclasses import dataclass

import numpy as np


@dataclass
class MatchedSet:
    """匹配后的估计与真值集合。

    Attributes:
        estimates: 估计角度，形状 (K̂,)
        truth: 真实角度，形状 (K,)
        matched_pairs: 匹配对，形状 (min(K, K̂), 2)，每行 [est_idx, truth_idx]
        matched_errors: 匹配误差，形状 (min(K, K̂),)
        time_ms: 估计耗时（毫秒）
    """

    estimates: np.ndarray
    truth: np.ndarray
    matched_pairs: np.ndarray
    matched_errors: np.ndarray
    time_ms: float

    @property
    def K_hat(self) -> int:
        """估计信源数。"""
        return len(self.estimates)

    @property
    def K(self) -> int:
        """真实信源数。"""
        return len(self.truth)

    @property
    def num_matched(self) -> int:
        """匹配数量。"""
        return len(self.matched_pairs)

    @property
    def is_correct_count(self) -> bool:
        """是否正确检测信源数。"""
        return self.K_hat == self.K

    def per_source_errors(self) -> dict[int, float]:
        """按信源的误差。

        Returns:
            字典，键为真值索引，值为误差
        """
        result: dict[int, float] = {}
        for est_idx, truth_idx in self.matched_pairs:
            result[truth_idx] = self.matched_errors[len(result)]
        return result


@dataclass
class MetricValue:
    """指标值。

    Attributes:
        value: 标量值或按信源的数组
        count: 参与统计的试验数
        failed: 失败的试验数
    """

    value: float | np.ndarray
    count: int
    failed: int = 0

    @property
    def success_rate(self) -> float:
        """成功率。"""
        total = self.count + self.failed
        return self.count / total if total > 0 else 0.0
