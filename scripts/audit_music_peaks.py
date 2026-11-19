"""MUSIC 寻峰数值审计；候选搜索器仅用于实验，不注册到产品。"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import minimize_scalar
from threadpoolctl import threadpool_info, threadpool_limits

from arena.core.algorithms import MUSIC
from arena.core.crb import compute_stochastic_crb
from arena.core.rng import RNGTree
from arena.core.scenario.generator import generate_trial_data
from arena_api import ArrayDescriptor, Observation, RunContext, kit

METHODS = ("grid", "parabolic", "local_dense")
PROFILES = ("on_grid", "offset_027", "half_grid", "random_angles")


def make_array() -> ArrayDescriptor:
    """构造与用户实验相同的 16 阵元半波长 ULA。"""
    return ArrayDescriptor(
        "ula",
        {"M": 16, "d": 0.5},
        np.column_stack([np.arange(16) * 0.5, np.zeros((16, 2))]),
    )


def make_context(seed: int = 42) -> RunContext:
    """为独立审计构造 CPU 上下文。"""
    return RunContext(
        "cpu", logging.getLogger("peak-audit"), False, None, RNGTree(seed).for_algorithm("music", 0)
    )


def truth_for(profile: str, seed: int, trial: int) -> np.ndarray:
    """固定角度不随搜索步长改变，随机角度按独立派生路径抽样。"""
    base = np.array([-10.0, 10.0])
    if profile == "random_angles":
        return base + RNGTree(seed).for_algorithm("angle-offset", trial).uniform(-0.05, 0.05, 2)
    return base + {"on_grid": 0.0, "offset_027": 0.027, "half_grid": 0.05}[profile]


def local_dense(
    array: ArrayDescriptor,
    noise: np.ndarray,
    coarse: np.ndarray,
    step: float,
    target: float = 0.0001,
) -> np.ndarray:
    """在已检出的峰左右一格内逐级十等分并重算谱，不输入真实角度。

    本候选只验证良好分离的内部峰；不能恢复粗搜索已经漏掉的峰。
    """
    result = []
    for angle in coarse:
        lower, upper = max(-90.0, angle - step), min(90.0, angle + step)
        width = step
        while width > target * (1 + 1e-10):
            left, right = max(lower, angle - width), min(upper, angle + width)
            spacing = max(target, width / 10)
            count = int(np.ceil((right - left) / spacing - 1e-9))
            grid = np.linspace(left, right, count + 1)
            angle = float(grid[np.argmax(kit.music_spectrum(array.steering(grid), noise))])
            width = (right - left) / count
        result.append(angle)
    return np.sort(np.asarray(result))


def continuous_reference(
    array: ArrayDescriptor,
    noise: np.ndarray,
    coarse: np.ndarray,
    step: float,
) -> np.ndarray:
    """用独立有界优化检查局部离散搜索；只是数值参考，不是真值。"""
    results = []
    for angle in coarse:

        def objective(theta: float) -> float:
            return float(np.sum(np.abs(noise.conj().T @ array.steering([theta])) ** 2))

        opt = minimize_scalar(
            objective,
            bounds=(angle - step, angle + step),
            method="bounded",
            options={"xatol": 1e-10},
        )
        if not opt.success:
            raise RuntimeError("局部连续参考未收敛")
        results.append(opt.x)
    return np.sort(np.asarray(results))


def candidate_estimate(obs: Observation, algo: MUSIC, array: ArrayDescriptor) -> np.ndarray:
    """复用当前 MUSIC 的协方差、子空间、谱及粗峰规则，仅替换细化阶段。"""
    _, noise, _, _ = kit.subspace_decomposition(obs.covariance(), obs.K)
    spectrum = kit.music_spectrum(algo.A_grid, noise)
    spectrum /= spectrum.max()
    coarse, _ = kit.peak_search(
        spectrum, algo.grid, obs.K, min_separation=algo.params.grid_step * 0.5
    )
    return local_dense(array, noise, coarse, algo.params.grid_step)


def shared_estimates(obs: Observation, algo: MUSIC, array: ArrayDescriptor) -> list[np.ndarray]:
    """精度试验共用相同子空间和粗谱；计时试验另行完整执行各方法。"""
    _, noise, _, _ = kit.subspace_decomposition(obs.covariance(), obs.K)
    spectrum = kit.music_spectrum(algo.A_grid, noise)
    spectrum /= spectrum.max()
    coarse, _ = kit.peak_search(
        spectrum, algo.grid, obs.K, min_separation=algo.params.grid_step * 0.5
    )
    return [
        np.sort(coarse),
        kit.refine_peaks(spectrum, algo.grid, coarse),
        local_dense(array, noise, coarse, algo.params.grid_step),
    ]


def summarize(errors: np.ndarray, times: np.ndarray, bound: float, seed: int) -> dict:
    """给出配对试验的 RMSE、源别偏差和按试验重采样的 95% 区间。"""
    valid = np.all(np.isfinite(errors), axis=1)
    e = errors[valid]
    if not len(e):
        raise RuntimeError("全部估计失败，请检查场景与搜索器")
    squared = np.mean(e**2, axis=1)
    rng = RNGTree(seed).for_algorithm("bootstrap", 0)
    bootstrap = np.sqrt(np.mean(squared[rng.integers(0, len(e), (1000, len(e)))], axis=1))
    return {
        "valid": int(valid.sum()),
        "failed": int((~valid).sum()),
        "rmse_deg": float(np.sqrt(np.mean(squared))),
        "rmse_ci95_deg": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "bias_deg_by_source": np.mean(e, axis=0).tolist(),
        "error_std_deg_by_source": np.std(e, axis=0).tolist(),
        "sqrt_mean_crb_deg": bound,
        "ratio": float(np.sqrt(np.mean(squared)) / bound),
        "mean_ms": float(np.mean(times) * 1000),
        "median_ms": float(np.median(times) * 1000),
        "p95_ms": float(np.quantile(times, 0.95) * 1000),
    }


def audit_reference(seed: int) -> dict:
    """在四类角度的 80 次试验中量化局部搜索与独立连续参考的差。"""
    array = make_array()
    grid = np.arange(-90, 90.05, 0.1)
    steering = array.steering(grid)
    differences = {str(target): 0.0 for target in (0.0001, 0.00001)}
    for profile in PROFILES:
        for trial in range(20):
            truth = truth_for(profile, seed, trial)
            obs = generate_trial_data(
                array, truth, 2, 200, 30, trial_rng=RNGTree(seed).for_trial(trial)
            )
            _, noise, _, _ = kit.subspace_decomposition(obs.covariance(), 2)
            coarse, _ = kit.peak_search(kit.music_spectrum(steering, noise), grid, 2)
            reference = continuous_reference(array, noise, coarse, 0.1)
            for target in (0.0001, 0.00001):
                dense = local_dense(array, noise, coarse, 0.1, target)
                differences[str(target)] = max(
                    differences[str(target)], float(np.max(np.abs(dense - reference)))
                )
    return {"reference_trials": 80, "max_difference_to_continuous_reference_deg": differences}


def run_audit(trials: int, seed: int, steps: list[float], snrs: list[float]) -> tuple[dict, dict]:
    """共用观测、轮换执行次序，比较生产算法两种设置与实验候选。"""
    array, ctx = make_array(), make_context(seed)
    rows, raw, setup = [], {}, {}
    started = perf_counter()
    for step in steps:
        algorithms = []
        t0 = perf_counter()
        for refine in (False, True):
            algo = MUSIC()
            algo.configure(
                MUSIC.Params(grid_step=step, refine=refine, legacy_grid=True), array, ctx
            )
            algorithms.append(algo)
        setup[str(step)] = (perf_counter() - t0) * 500
        for profile in PROFILES:
            for snr in snrs:
                errors = np.full((3, trials, 2), np.nan)
                timing_trials = min(trials, 50)
                times = np.empty((3, timing_trials))
                bounds = []
                truths = []
                tree = RNGTree(seed)
                for trial in range(-3, trials):
                    # 三次热身不计入统计；所有步长及方法重用相同随机派生路径。
                    truth = truth_for(profile, seed, max(trial, 0))
                    obs = generate_trial_data(
                        array, truth, 2, 200, snr, trial_rng=tree.for_trial(max(trial, 0))
                    )
                    if trial >= timing_trials:
                        estimates = shared_estimates(obs, algorithms[0], array)
                        for method, angles in enumerate(estimates):
                            if len(angles) == 2 and np.all(np.isfinite(angles)):
                                errors[method, trial] = np.sort(angles) - truth
                        truths.append(truth)
                        bounds.append(np.mean(compute_stochastic_crb(array, truth, snr, 200)))
                        continue
                    for j in range(3):
                        method = (trial + j) % 3
                        # 每种方法拿到独立协方差缓存，避免后执行者少算一次协方差。
                        fresh = Observation(obs.X, K=2)
                        t0 = perf_counter()
                        if method < 2:
                            angles = algorithms[method].estimate(fresh, ctx).angles
                        else:
                            angles = candidate_estimate(fresh, algorithms[0], array)
                        elapsed = perf_counter() - t0
                        if trial >= 0:
                            times[method, trial] = elapsed
                            if len(angles) == 2 and np.all(np.isfinite(angles)):
                                # 一维等数量平方误差的最优配对等价于排序配对。
                                errors[method, trial] = np.sort(angles) - truth
                    if trial >= 0:
                        truths.append(truth)
                        bounds.append(np.mean(compute_stochastic_crb(array, truth, snr, 200)))
                key = f"{profile}_snr{snr:g}_step{step:g}"
                raw[key + "_errors"] = errors
                raw[key + "_seconds"] = times
                raw[key + "_truth"] = np.asarray(truths)
                bound = float(np.sqrt(np.mean(bounds)))
                for method, name in enumerate(METHODS):
                    rows.append(
                        {
                            "profile": profile,
                            "snr_db": snr,
                            "step_deg": step,
                            "method": name,
                            **summarize(errors[method], times[method], bound, seed),
                        }
                    )
                print(f"完成 {key}", flush=True)
    return {
        "seed": seed,
        "trials_per_cell": trials,
        "timing_trials_per_cell": min(trials, 50),
        "M": 16,
        "K": 2,
        "N": 200,
        "local_target_deg": 0.0001,
        "steps_deg": steps,
        "snrs_db": snrs,
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "blas": threadpool_info(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "configure_mean_ms_per_algorithm": setup,
        "elapsed_seconds": perf_counter() - started,
        "results": rows,
    }, raw


def main() -> None:
    """运行完整审计并原子保存摘要和逐试验结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261119)
    parser.add_argument("--steps", nargs="+", type=float, default=[0.1, 0.05, 0.01, 0.005])
    parser.add_argument("--snrs", nargs="+", type=float, default=[0, 20, 30])
    parser.add_argument("--output", type=Path, default=Path("arena_ws/music_peak_review"))
    args = parser.parse_args()
    if args.trials < 2 or any(s < 0.0001 or s > 5 for s in args.steps):
        parser.error("试验数至少为 2，网格步长须在 [0.0001, 5] 内")
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=1):
        summary, raw = run_audit(args.trials, args.seed, args.steps, args.snrs)
        summary["reference_validation"] = audit_reference(args.seed)
    temp = args.output / "summary.tmp"
    temp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(args.output / "summary.json")
    temp = args.output / "trials.tmp"
    with temp.open("wb") as stream:
        np.savez_compressed(stream, **raw)
    temp.replace(args.output / "trials.npz")


if __name__ == "__main__":
    main()
