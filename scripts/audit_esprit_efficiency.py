"""独立复核 TLS 解与 CRB 效率；不修改算法或验收门限。"""

from __future__ import annotations

import json

import numpy as np

from arena.core.crb import compute_stochastic_crb
from arena_api import ArrayDescriptor, kit


def audit() -> dict:
    """用增广 Gram 矩阵特征分解复核生产代码的 SVD TLS 解。"""
    array = ArrayDescriptor(
        "ula",
        {"M": 16, "d": 0.5},
        np.column_stack([np.arange(16) * 0.5, np.zeros((16, 2))]),
    )
    truth = np.array([-10.0, 10.0])
    steering = array.steering(truth)
    rows = []
    max_difference = 0.0
    for snr in (0, 10, 20, 30):
        bound = np.sqrt(np.mean(compute_stochastic_crb(array, truth, snr, 500)))
        for block in range(4):
            errors = []
            for seed in range(block * 500, (block + 1) * 500):
                rng = np.random.default_rng(seed)
                signal = rng.normal(size=(2, 500)) + 1j * rng.normal(size=(2, 500))
                signal *= np.sqrt(10 ** (snr / 10) / 2)
                noise = rng.normal(size=(16, 500)) + 1j * rng.normal(size=(16, 500))
                received = steering @ signal + noise / np.sqrt(2)
                covariance = received @ received.conj().T / 500
                _, vectors = np.linalg.eigh(covariance)
                subspace = vectors[:, -2:]
                augmented = np.column_stack([subspace[:-1], subspace[1:]])
                _, gram_vectors = np.linalg.eigh(augmented.conj().T @ augmented)
                nullspace = gram_vectors[:, :2]
                # 右侧解方程，独立于生产代码的 SVD + 显式求逆路径。
                rotation = np.linalg.solve(nullspace[2:].T, -nullspace[:2].T).T
                angles = np.sort(
                    np.rad2deg(np.arcsin(-np.angle(np.linalg.eigvals(rotation)) / np.pi))
                )
                production = kit.esprit(covariance, 2, d=0.5, method="tls")
                max_difference = max(max_difference, float(np.max(np.abs(angles - production))))
                errors.append(angles - truth)
            rmse = float(np.sqrt(np.mean(np.square(errors))))
            rows.append(
                {
                    "snr_db": snr,
                    "seed_start": block * 500,
                    "trials": 500,
                    "rmse_deg": rmse,
                    "sqrt_crb_deg": float(bound),
                    "ratio": rmse / float(bound),
                }
            )
    return {"max_reference_difference_deg": max_difference, "results": rows}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=False))
