"""MDL/AIC 信源数估计（接口规范参考 Wax & Kailath）。"""

import numpy as np

from arena_api import Observation


def estimate_source_count(obs: Observation, method: str) -> int:
    """由噪声特征值的几何/算术均值比选择模型阶数。"""
    eigenvalues = np.linalg.eigvalsh(obs.covariance())[::-1].real
    eigenvalues = np.maximum(eigenvalues, max(float(eigenvalues[0]), 1.0) * 1e-15)
    scores = []
    for k in range(obs.M):
        noise = eigenvalues[k:]
        likelihood = obs.N * (obs.M - k) * (np.log(np.mean(noise)) - np.mean(np.log(noise)))
        parameters = k * (2 * obs.M - k)
        scores.append(
            likelihood + 0.5 * parameters * np.log(obs.N)
            if method == "mdl"
            else 2 * likelihood + 2 * parameters
        )
    return int(np.argmin(scores))
