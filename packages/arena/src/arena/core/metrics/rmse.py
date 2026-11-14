"""RMSE 指标插件。"""

from typing import Any, ClassVar

import numpy as np
from arena_api import Metric


class RMSEMetric(Metric):
    """RMSE（Root Mean Square Error）指标。

    对匹配成功的信源计算均方根误差。
    """

    id: ClassVar[str] = "rmse"
    name: ClassVar[str] = "RMSE"
    unit: ClassVar[str] = "°"
    lower_is_better: ClassVar[bool] = True

    def compute(
        self,
        estimates: np.ndarray,
        truth: np.ndarray,
        matched: np.ndarray,
        **kwargs: Any,
    ) -> float:
        """计算 RMSE。

        Args:
            estimates: 估计角度，形状 (K̂,)
            truth: 真实角度，形状 (K,)
            matched: 匹配关系，形状 (K_matched, 2)
            **kwargs: 额外参数

        Returns:
            RMSE（度）
        """
        if len(matched) == 0:
            return np.nan

        # 提取匹配的角度
        est_matched = estimates[matched[:, 0]]
        truth_matched = truth[matched[:, 1]]

        # 计算误差
        errors = est_matched - truth_matched

        # RMSE
        rmse = np.sqrt(np.mean(errors**2))

        return float(rmse)


# 导出实例
rmse_metric = RMSEMetric()
