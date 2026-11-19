"""寻峰审计的独立参考、离网格诊断与网格收敛；不改变生产算法。"""

import numpy as np
import pytest
from scripts.audit_music_peaks import (
    candidate_estimate,
    continuous_reference,
    local_dense,
    make_array,
    make_context,
    shared_estimates,
    summarize,
    truth_for,
)
from threadpoolctl import threadpool_limits

from arena.core.algorithms import MUSIC
from arena.core.rng import RNGTree
from arena.core.scenario.generator import generate_trial_data
from arena_api import Observation, kit


@pytest.mark.parametrize("step", [0.1, 0.01])
def test_shared_accuracy_path_matches_full_production_calls(step):
    array, ctx = make_array(), make_context()
    obs = generate_trial_data(array, np.array([-9.973, 10.027]), 2, 200, 20, seed=42)
    algorithms = []
    for refine in (False, True):
        algo = MUSIC()
        algo.configure(MUSIC.Params(grid_step=step, refine=refine), array, ctx)
        algorithms.append(algo)
    with threadpool_limits(limits=1):
        shared = shared_estimates(obs, algorithms[0], array)
        for i, algo in enumerate(algorithms):
            # 相同核心操作只允许浮点舍入差；不会把审计路径的偏差当成产品现象。
            np.testing.assert_allclose(
                shared[i],
                np.sort(algo.estimate(Observation(obs.X, K=2), ctx).angles),
                rtol=0,
                atol=1e-12,
            )
        np.testing.assert_allclose(
            shared[2], candidate_estimate(obs, algorithms[0], array), rtol=0, atol=1e-12
        )


@pytest.mark.parametrize("profile", ["on_grid", "offset_027", "half_grid", "random_angles"])
def test_local_dense_matches_independent_continuous_peak(profile):
    array = make_array()
    grid = np.arange(-90, 90.05, 0.1)
    with threadpool_limits(limits=1):
        steering = array.steering(grid)
        for trial in range(20):
            truth = truth_for(profile, 20261119, trial)
            obs = generate_trial_data(
                array, truth, 2, 200, 30, trial_rng=RNGTree(20261119).for_trial(trial)
            )
            _, noise, _, _ = kit.subspace_decomposition(obs.covariance(), 2)
            coarse, _ = kit.peak_search(kit.music_spectrum(steering, noise), grid, 2)
            reference = continuous_reference(array, noise, coarse, 0.1)
            dense = local_dense(array, noise, coarse, 0.1)
            # 0.0001° 格点量化上限为半格，额外 0.000001° 覆盖优化器误差。
            np.testing.assert_allclose(dense, reference, rtol=0, atol=0.000051)
            finer = local_dense(array, noise, coarse, 0.1, target=0.00001)
            np.testing.assert_allclose(finer, reference, rtol=0, atol=0.000006)


@pytest.mark.slow
def test_off_grid_error_and_grid_convergence_diagnostic():
    array, ctx = make_array(), make_context()
    algorithms = []
    for step in (0.1, 0.01):
        algo = MUSIC()
        algo.configure(MUSIC.Params(grid_step=step), array, ctx)
        algorithms.append(algo)
    errors = np.empty((2, 3, 200, 2))
    with threadpool_limits(limits=1):
        for trial in range(200):
            truth = truth_for("random_angles", 20261119, trial)
            obs = generate_trial_data(
                array, truth, 2, 200, 20, trial_rng=RNGTree(20261119).for_trial(trial)
            )
            for j, algo in enumerate(algorithms):
                errors[j, :, trial] = np.asarray(shared_estimates(obs, algo, array)) - truth
    rmse = np.sqrt(np.mean(errors**2, axis=(2, 3)))
    # 诊断当前粗网格误差及收敛特征，不作为 MUSIC 新的工程验收门限。
    assert rmse[0, 0] > 3 * rmse[0, 2], rmse
    assert rmse[0, 1] > 2 * rmse[0, 2], rmse
    assert abs(rmse[1, 1] - rmse[1, 2]) < abs(rmse[0, 1] - rmse[0, 2]) / 5, rmse
    # 同一连续峰的两种粗网格定位结果至多相差一个局部终止格距。
    np.testing.assert_allclose(errors[0, 2], errors[1, 2], rtol=0, atol=0.000101)


def test_summary_reports_failures_and_does_not_cancel_source_bias():
    errors = np.array([[0.1, -0.1], [0.1, -0.1], [np.nan, np.nan]])
    result = summarize(errors, np.array([0.001, 0.002, 0.009]), 0.01, 42)
    assert result["failed"] == 1
    assert result["valid"] == 2
    assert result["rmse_deg"] == pytest.approx(0.1)
    np.testing.assert_allclose(result["bias_deg_by_source"], [0.1, -0.1], atol=1e-15)
    assert result["median_ms"] == pytest.approx(2)
