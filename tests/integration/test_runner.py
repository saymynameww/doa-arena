"""测试 Runner 和端到端流程。"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from arena import ExperimentConfig, ExperimentType, run_experiment
from arena.core.config import AlgorithmConfig, ScenarioConfig


def test_single_experiment():
    """测试单次实验。"""
    # 配置
    config = ExperimentConfig(
        name="Test Single",
        type=ExperimentType.SINGLE,
        trials=1,
        scenario=ScenarioConfig(
            seed=42,
            snapshots=100,
        ),
        algorithms=[
            AlgorithmConfig(id="music", label="MUSIC"),
            AlgorithmConfig(id="esprit", label="ESPRIT"),
        ],
    )

    # 运行
    result = run_experiment(config)

    # 验证
    assert len(result.points) == 1
    assert len(result.points[0].trials) == 1

    trial = result.points[0].trials[0]
    assert "MUSIC" in trial.estimates
    assert "ESPRIT" in trial.estimates

    # 检查估计结果
    music_est = trial.estimates["MUSIC"]
    assert music_est.K_hat == 2
    assert len(music_est.angles) == 2


def test_monte_carlo_experiment():
    """测试蒙特卡洛实验。"""
    config = ExperimentConfig(
        name="Test Monte Carlo",
        type=ExperimentType.MONTE_CARLO,
        trials=10,
        scenario=ScenarioConfig(seed=42),
        algorithms=[
            AlgorithmConfig(id="music"),
        ],
    )

    result = run_experiment(config)

    # 验证
    assert len(result.points) == 1
    assert len(result.points[0].trials) == 10

    # 所有试验都应该有结果
    for trial in result.points[0].trials:
        assert "music" in trial.estimates


def test_sweep_experiment():
    """测试扫描实验。"""
    from arena.core.config import SweepConfig

    config = ExperimentConfig(
        name="Test Sweep",
        type=ExperimentType.SWEEP,
        trials=5,
        scenario=ScenarioConfig(seed=42),
        algorithms=[
            AlgorithmConfig(id="music"),
            AlgorithmConfig(id="esprit"),
        ],
        sweep=SweepConfig(
            path="scenario.sources.snr_db",
            values=[0, 5, 10],
            label="SNR",
            unit="dB",
        ),
    )

    result = run_experiment(config)

    # 验证
    assert len(result.points) == 3  # 3 个扫描点
    assert result.points[0].sweep_value == 0
    assert result.points[1].sweep_value == 5
    assert result.points[2].sweep_value == 10

    # 每个点都有 5 次试验
    for point in result.points:
        assert len(point.trials) == 5


def test_result_storage():
    """测试结果存储。"""
    from arena.core.storage import ResultWriter

    # 临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "exp_001"

        # 运行实验
        config = ExperimentConfig(
            name="Test Storage",
            type=ExperimentType.MONTE_CARLO,
            trials=10,
            algorithms=[AlgorithmConfig(id="music")],
        )

        result = run_experiment(config)

        # 写入结果
        writer = ResultWriter(output_dir)
        writer.write_experiment(result)

        # 验证文件存在
        assert (output_dir / "config.json").exists()
        assert (output_dir / "meta.json").exists()
        assert (output_dir / "results.npz").exists()
        assert (output_dir / "summary.json").exists()

        # 验证可以读取
        import json

        with open(output_dir / "config.json") as f:
            config_data = json.load(f)
            assert config_data["name"] == "Test Storage"

        # 验证 npz（读取后立即关闭）
        data = np.load(output_dir / "results.npz")
        keys = list(data.keys())
        data.close()  # 显式关闭，避免 Windows 文件锁定

        assert "music__estimates" in keys
        assert "music__times_ms" in keys


def test_warmup():
    """测试预热功能。"""
    config = ExperimentConfig(
        name="Test Warmup",
        type=ExperimentType.MONTE_CARLO,
        trials=3,
        algorithms=[AlgorithmConfig(id="music")],
    )

    # 启用预热
    config.options.warmup = True
    result_warmup = run_experiment(config)

    # 禁用预热
    config.options.warmup = False
    result_no_warmup = run_experiment(config)

    # 两种情况都应该成功
    assert len(result_warmup.points[0].trials) == 3
    assert len(result_no_warmup.points[0].trials) == 3


def test_common_random_numbers():
    """测试公共随机数。"""
    from arena.core.config import SweepConfig

    config = ExperimentConfig(
        name="Test CRN",
        type=ExperimentType.SWEEP,
        trials=5,
        algorithms=[AlgorithmConfig(id="music")],
        sweep=SweepConfig(
            path="scenario.sources.snr_db",
            values=[5, 10],
        ),
    )

    # 启用公共随机数
    config.options.common_random_numbers = True
    result_crn = run_experiment(config)

    # 禁用公共随机数
    config.options.common_random_numbers = False
    result_no_crn = run_experiment(config)

    # 两种情况结果不同（随机性导致）
    # 但都应该成功运行
    assert len(result_crn.points) == 2
    assert len(result_no_crn.points) == 2


def test_multiple_algorithms():
    """测试多个算法。"""
    config = ExperimentConfig(
        name="Test Multiple",
        trials=5,
        algorithms=[
            AlgorithmConfig(id="cbf", label="CBF"),
            AlgorithmConfig(id="mvdr", label="MVDR"),
            AlgorithmConfig(id="music", label="MUSIC"),
            AlgorithmConfig(id="root_music", label="Root-MUSIC"),
            AlgorithmConfig(id="esprit", label="ESPRIT"),
        ],
    )

    result = run_experiment(config)

    # 验证所有算法都运行了
    trial = result.points[0].trials[0]
    assert len(trial.estimates) == 5
    assert all(
        label in trial.estimates
        for label in ["CBF", "MVDR", "MUSIC", "Root-MUSIC", "ESPRIT"]
    )


def test_algorithm_parameters():
    """测试算法参数传递。"""
    config = ExperimentConfig(
        name="Test Params",
        trials=3,
        algorithms=[
            AlgorithmConfig(
                id="music",
                label="MUSIC-FB",
                params={"smoothing": "fb", "subarray_size": 11},
            ),
        ],
    )

    result = run_experiment(config)

    # 应该成功运行
    trial = result.points[0].trials[0]
    assert "MUSIC-FB" in trial.estimates


@pytest.mark.slow
def test_large_experiment():
    """测试较大规模实验。"""
    from arena.core.config import SweepConfig

    config = ExperimentConfig(
        name="Large Experiment",
        type=ExperimentType.SWEEP,
        trials=50,
        algorithms=[
            AlgorithmConfig(id="music"),
            AlgorithmConfig(id="esprit"),
        ],
        sweep=SweepConfig(
            path="scenario.sources.snr_db",
            values=list(range(-10, 21, 5)),  # -10 到 20，步长 5
        ),
    )

    result = run_experiment(config)

    # 验证
    assert len(result.points) == 7  # 7 个扫描点
    for point in result.points:
        assert len(point.trials) == 50
