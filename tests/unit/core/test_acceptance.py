"""接口规范 13.4 与架构 5.7 的独立数值验收。"""

import logging

import numpy as np
import pytest

from arena.core.algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC
from arena.core.crb import compute_stochastic_crb
from arena_api import ArrayDescriptor, Observation, RunContext, kit


def context():
    return RunContext(
        device="cpu",
        log=logging.getLogger("acceptance"),
        want_spectrum=True,
        workspace=None,
        rng=np.random.default_rng(123),
    )


def array():
    return ArrayDescriptor(
        "ula",
        {"M": 16, "d": 0.5},
        np.column_stack([np.arange(16) * 0.5, np.zeros(16), np.zeros(16)]),
    )


def observation(angles, snr, n, seed=123):
    rng = np.random.default_rng(seed)
    a = array().steering(angles)
    s = (rng.normal(size=(len(angles), n)) + 1j * rng.normal(size=(len(angles), n))) * np.sqrt(
        10 ** (snr / 10) / 2
    )
    noise = (rng.normal(size=(16, n)) + 1j * rng.normal(size=(16, n))) / np.sqrt(2)
    return Observation(X=a @ s + noise, K=len(angles))


def test_peak_edges_are_not_sources():
    angles, _ = kit.peak_search(np.array([5.0, 4.0, 3.0, 2.0, 1.0]), np.arange(5.0), K=2)
    assert len(angles) == 0


def test_single_source_stochastic_crb_closed_form():
    # 单信源随机 CRB 闭式；容差只覆盖矩阵浮点运算。
    m, n, p = 16, 200, 10.0
    theta = np.array([20.0])
    derivative_energy = (2 * np.pi * 0.5 * np.cos(np.deg2rad(20))) ** 2 * m * (m * m - 1) / 12
    expected = (1 + p * m) / (2 * n * p * p * m * derivative_energy) * (180 / np.pi) ** 2
    np.testing.assert_allclose(
        compute_stochastic_crb(array(), theta, 10.0, n), [expected], rtol=1e-10
    )


@pytest.mark.parametrize("cls", [CBF, MVDR, MUSIC, RootMUSIC, ESPRIT])
def test_sign_and_accuracy(cls):
    algo = cls()
    ctx = context()
    params = cls.Params()
    algo.configure(params, array(), ctx)
    est = algo.estimate(observation([20.0], 30, 1000), ctx)
    np.testing.assert_allclose(est.angles, [20.0], atol=0.05)
    if est.spectrum is not None:
        assert np.max(est.spectrum.values) == pytest.approx(1.0)


@pytest.mark.parametrize("cls", [MUSIC, RootMUSIC, ESPRIT])
def test_smoothing_auto_aperture(cls):
    algo = cls()
    params = cls.Params(smoothing="fb")
    algo.configure(params, array(), context())
    if cls is MUSIC:
        assert algo._get_subarray_size(params, 16, 2) == 16
    else:
        assert algo._get_subarray_size(16, 2) == 16


def test_complex_correlation_is_hermitian_and_psd():
    from arena.core.signals import CorrelationMatrix

    p = CorrelationMatrix.partial_correlated(np.ones(3), 0.9, 0).to_matrix()
    np.testing.assert_allclose(p, 0.9 * np.ones((3, 3)) + 0.1 * np.eye(3), atol=1e-14)
    with pytest.raises(ValueError, match="半正定"):
        CorrelationMatrix.partial_correlated(np.ones(3), 0.9, 90).to_matrix()


def test_coherent_sources_respect_individual_powers():
    from arena.core.signals import CorrelationMatrix

    powers = np.array([1.0, 10.0])
    p = CorrelationMatrix.coherent(powers, np.exp(1j * np.array([0.0, 1.0]))).to_matrix()
    np.testing.assert_allclose(np.diag(p).real, powers, rtol=1e-14)


@pytest.mark.slow
def test_two_sources_all_baselines():
    # 接口规范 13.4 的 100 次双信源验收，不根据结果修改阈值。
    classes = [CBF, MVDR, MUSIC, RootMUSIC, ESPRIT]
    algorithms = [cls() for cls in classes]
    ctx = context()
    for algo in algorithms:
        algo.configure(algo.Params(), array(), ctx)
    tolerances = [0.3, 0.1, 0.1, 0.05, 0.05]
    for seed in range(100):
        obs = observation([-10.0, 10.0], 20, 500, seed)
        for algo, tolerance in zip(algorithms, tolerances):
            np.testing.assert_allclose(
                np.sort(algo.estimate(obs, ctx).angles), [-10.0, 10.0], atol=tolerance
            )


@pytest.mark.slow
def test_coherent_smoothing_acceptance():
    from arena.core.config import ExperimentConfig
    from arena.core.runner.core import run_experiment

    config = ExperimentConfig(
        algorithms=[
            {"id": "music", "label": "plain"},
            {"id": "music", "label": "fb", "params": {"smoothing": "fb"}},
        ],
        trials=1000,
        scenario={
            "snapshots": 500,
            "sources": {
                "snr_db": 20,
                "angles": {"values": [-3.0, 3.0]},
                "correlation": {"mode": "coherent"},
            },
        },
    )
    result = run_experiment(config)
    rates = {
        name: np.mean(
            [
                np.max(np.abs(np.sort(t.estimates[name].angles) - [-3, 3])) < 1
                if len(t.estimates[name].angles) == 2
                else False
                for t in result.points[0].trials
            ]
        )
        for name in ["plain", "fb"]
    }
    assert rates["plain"] < 0.5, rates
    assert rates["fb"] > 0.95, rates


@pytest.mark.slow
@pytest.mark.parametrize("snr", [0, 10, 20, 30])
def test_efficiency_against_crb(snr):
    ctx = context()
    algorithms = [RootMUSIC(), ESPRIT()]
    for algo in algorithms:
        algo.configure(algo.Params(), array(), ctx)
    errors = [[], []]
    for seed in range(500):
        obs = observation([-10.0, 10.0], snr, 500, seed)
        for i, algo in enumerate(algorithms):
            errors[i].append(np.sort(algo.estimate(obs, ctx).angles) - [-10, 10])
    bound = np.sqrt(np.mean(compute_stochastic_crb(array(), np.array([-10.0, 10.0]), snr, 500)))
    ratios = [np.sqrt(np.mean(np.square(e))) / bound for e in errors]
    if snr >= 10:
        # 接口规范 v0.6（2026-11-16 需求方批准）：仅拆分规定场景的门限。
        assert ratios[0] < 1.5, {"root_music": ratios[0]}
        assert ratios[1] < 2.0, {"tls_esprit": ratios[1]}


@pytest.mark.slow
def test_thousand_trials_five_algorithms_under_one_minute():
    import time

    from arena.core.config import ExperimentConfig
    from arena.core.runner.core import run_experiment

    start = time.perf_counter()
    run_experiment(
        ExperimentConfig(
            algorithms=[{"id": cls.id} for cls in [CBF, MVDR, MUSIC, RootMUSIC, ESPRIT]],
            trials=1000,
        )
    )
    assert time.perf_counter() - start < 60
