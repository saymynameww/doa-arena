"""指标计算函数。"""

from __future__ import annotations

from typing import Any, TypedDict

import numpy as np

from arena_api import Estimate, kit


def match_and_compute(
    estimate: Estimate,
    truth: np.ndarray,
) -> dict[str, Any]:
    """匹配估计与真值，计算基础指标。

    Args:
        estimate: 估计结果
        truth: 真实角度，形状 (K,)

    Returns:
        指标字典，包含：
        - K_hat: 估计信源数
        - K: 真实信源数
        - matched_pairs: 匹配对，形状 (min(K, K̂), 2)
        - matched_errors: 匹配误差，形状 (min(K, K̂),)
        - rmse: RMSE（度）
        - max_error: 最大误差（度）
        - success: 是否成功（K̂ == K）
    """
    K_hat = estimate.K_hat
    K = len(truth)

    # 匹配
    matched_pairs, matched_errors = kit.hungarian_matching(
        estimate.angles,
        truth,
    )

    # RMSE
    if len(matched_errors) > 0:
        rmse = np.sqrt(np.mean(matched_errors**2))
        max_error = np.max(matched_errors)
    else:
        rmse = np.nan
        max_error = np.nan

    # 成功标志
    success = K_hat == K

    return {
        "K_hat": K_hat,
        "K": K,
        "matched_pairs": matched_pairs,
        "matched_errors": matched_errors,
        "rmse": rmse,
        "max_error": max_error,
        "success": success,
    }


class MetricsResult(TypedDict):
    """汇总指标，分辨概率仅对双信源定义。"""

    rmse_mean: float
    rmse_std: float
    success_rate: float
    resolution_probability: float | None
    avg_K_hat: float
    num_trials: int
    num_valid: int


def compute_metrics(
    estimates: list[Estimate],
    truth: np.ndarray,
    threshold_deg: float | None = None,
    truths: list[np.ndarray] | None = None,
) -> MetricsResult:
    """批量计算指标统计量。

    Args:
        estimates: 估计结果列表
        truth: 真实角度
        threshold_deg: 成功门限，None 保留旧版检出数判定
        truths: 每次试验的真实角度，用于随机角度或间隔扫描

    Returns:
        统计指标字典：
        - rmse_mean: RMSE 均值
        - rmse_std: RMSE 标准差
        - success_rate: 成功率（正确检测信源数的比例）
        - avg_K_hat: 平均估计信源数
    """
    num_trials = len(estimates)
    rmses = []
    successes = []
    K_hats = []

    resolutions = []
    for idx, est in enumerate(estimates):
        actual_truth = truths[idx] if truths is not None else truth
        result = match_and_compute(est, actual_truth)
        if result["success"]:
            rmses.append(float(result["rmse"]))
        successes.append(
            bool(
                result["success"]
                and (threshold_deg is None or result["max_error"] <= threshold_deg)
            )
        )
        if len(actual_truth) == 2:
            resolutions.append(
                result["success"]
                and result["max_error"] < abs(actual_truth[1] - actual_truth[0]) / 2
            )
        K_hats.append(float(result["K_hat"]))

    # 过滤 NaN
    rmses_valid = [r for r in rmses if not np.isnan(r)]

    if len(rmses_valid) > 0:
        rmse_mean = float(np.sqrt(np.mean(np.square(rmses_valid))))
        rmse_std = float(np.std(rmses_valid))
    else:
        rmse_mean = np.nan
        rmse_std = np.nan

    success_rate = float(np.mean(successes))
    avg_K_hat = float(np.mean(K_hats))

    return {
        "rmse_mean": rmse_mean,
        "rmse_std": rmse_std,
        "success_rate": success_rate,
        "resolution_probability": float(np.mean(resolutions)) if resolutions else None,
        "avg_K_hat": avg_K_hat,
        "num_trials": num_trials,
        "num_valid": len(rmses_valid),
    }
