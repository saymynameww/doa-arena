"""M6 数据集数值、索引与恢复契约。"""

import copy

import numpy as np
import pytest

from arena import datasets
from arena.core.datasets import read_config, sample
from arena_api import AngleGrid


def configuration():
    return {
        "name": "中文训练集",
        "seed": 123,
        "num_samples": 9,
        "shard_size": 3,
        "scenario": {
            "array": {"type": "ula", "params": {"M": 8, "d": 0.5}},
            "sources": {
                "K": {"choice": [1, 2, 3]},
                "angles": {"mode": "random", "min": -50, "max": 50, "min_separation": 3},
                "snr_db": {"uniform": [-10, 20]},
            },
            "snapshots": {"choice": [8, 20]},
        },
        "content": {"grid_labels": {"grid": {"start": -60, "stop": 60, "step": 1}}},
    }


def test_grid_contract_and_labels():
    grid = AngleGrid(-1, 1, 0.1)
    assert grid.size == 21
    assert grid.points[-1] == 1
    assert grid.index(0.29) == 13
    with pytest.raises(ValueError, match="整除"):
        AngleGrid(0, 1, 0.3)
    labels = datasets.grid_labels(np.array([-0.2, 0.3]), grid)
    assert labels.sum() == 2
    smooth = datasets.grid_labels(np.array([-0.2, 0.3]), grid, 0.1)
    # 高斯取最大值，不做求和；真值恰好在网格点时为 1。
    np.testing.assert_allclose(smooth[[8, 13]], [1, 1], atol=1e-7)


def test_range_resume_and_online_core_are_identical(tmp_path):
    cfg = configuration()
    output = tmp_path / "中文数据集"
    datasets.generate(cfg, output, start=3, stop=7)
    partial = datasets.open(output)
    with pytest.raises(IndexError, match="尚未生成"):
        partial[0]
    datasets.generate(cfg, output)
    ds = datasets.open(output)
    assert ds.manifest["status"] == "complete"
    assert len(ds) == 9
    for i in range(len(ds)):
        expected = sample(read_config(cfg), i)
        for key, value in ds[i].items():
            np.testing.assert_array_equal(value, expected[key])
            assert not value.flags.writeable
        assert ds[i]["R"].dtype == np.complex64
    before = (output / "dataset.json").read_bytes()
    datasets.generate(cfg, output)
    assert (output / "dataset.json").read_bytes() == before
    changed = copy.deepcopy(cfg)
    changed["seed"] += 1
    with pytest.raises(ValueError, match="不同配置"):
        datasets.generate(changed, output)
    shard = output / ds.manifest["shards"][0]["file"]
    shard.write_bytes(b"invalid")
    with pytest.raises(ValueError, match="哈希"):
        datasets.open(output)[0]


def test_shards_do_not_change_sample_values(tmp_path):
    cfg = configuration()
    datasets.generate(cfg, tmp_path / "a")
    cfg["shard_size"] = 4
    datasets.generate(cfg, tmp_path / "b")
    a, b = datasets.open(tmp_path / "a"), datasets.open(tmp_path / "b")
    for i in range(len(a)):
        for key in a[i]:
            np.testing.assert_array_equal(a[i][key], b[i][key])


def test_dataset_validation_rejects_unusable_distribution():
    cfg = configuration()
    cfg["content"]["observation"] = "X"
    with pytest.raises(ValueError, match="快拍数必须固定"):
        read_config(cfg)
    cfg = configuration()
    cfg["scenario"]["array"]["params"]["M"] = {"choice": [8, 16]}
    with pytest.raises(ValueError, match="不允许分布"):
        read_config(cfg)


def test_torch_online_offline(tmp_path):
    torch = pytest.importorskip("torch")
    cfg = configuration()
    datasets.generate(cfg, tmp_path)
    online = datasets.TorchDataset(cfg)
    offline = datasets.TorchDataset(tmp_path)
    for i in range(len(online)):
        for key in online[i]:
            torch.testing.assert_close(
                online[i][key], offline[i][key], rtol=0, atol=0, equal_nan=True
            )
    batch = next(iter(torch.utils.data.DataLoader(online, batch_size=3)))
    assert batch["R"].shape == (3, 8, 8)
