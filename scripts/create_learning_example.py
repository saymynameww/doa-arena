"""在竞技场仓库外创建独立课题示例；训练代码不依赖 Web 服务。"""

from __future__ import annotations

import argparse
from pathlib import Path

NETWORK = '''"""纯 PyTorch 网络定义，插件加载阶段不导入 torch。"""
def build_network(M, n_grid, channels=8):
    import torch
    return torch.nn.Sequential(
        torch.nn.Conv2d(2, channels, 3, padding=1), torch.nn.ReLU(),
        torch.nn.Conv2d(channels, channels, 3, padding=1), torch.nn.ReLU(),
        torch.nn.Flatten(), torch.nn.Linear(channels * M * M, n_grid))
'''

PLUGIN = '''"""只依赖 arena_api 的外部学习算法。"""
import numpy as np
from arena_api import ModelAlgorithm, Estimate, Spectrum
from .net import build_network

class CnnGrid(ModelAlgorithm):
    id = "cnn_grid_example"
    name = "CNN 网格分类示例"
    version = "1.0.0"

    def build_network(self, meta, params):
        return build_network(meta.array["params"]["M"], meta.output.grid.size, **meta.hparams)

    def preprocess(self, obs_list, meta, params):
        import torch
        R = np.stack([obs.covariance() for obs in obs_list])
        R = R / np.maximum(np.linalg.norm(R, axis=(1, 2), keepdims=True), 1e-12)
        return torch.from_numpy(np.stack([R.real, R.imag], axis=1)).float()

    def postprocess(self, output, obs_list, meta, params, want_spectrum):
        from scipy.signal import find_peaks
        probabilities = output.sigmoid().detach().cpu().numpy()
        grid = meta.output.grid.points
        results = []
        for values, obs in zip(probabilities, obs_list):
            peaks, _ = find_peaks(values)
            count = obs.K if obs.K is not None else int(np.count_nonzero(values[peaks] >= .5))
            selected = peaks[np.argsort(values[peaks])[::-1][:count]]
            spectrum = Spectrum(grid, values, "probability") if want_spectrum else None
            results.append(Estimate(np.sort(grid[selected]), spectrum))
        return results
'''

TRAIN = '''"""普通课题训练脚本：生成数据、训练、导出；不启动 Arena Web。"""
import argparse
import json
from pathlib import Path
import numpy as np
from arena import datasets, models
from algorithms.cnn_grid.net import build_network

def main():
    import torch
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("arena_ws/models/cnn_demo"))
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads(Path("dataset_config.json").read_text(encoding="utf-8"))
    config["num_samples"] = args.samples
    directory = datasets.generate(config, Path("data/train"))
    training = datasets.TorchDataset(directory)
    seeds = np.random.SeedSequence(config["seed"], spawn_key=(3,)).generate_state(2)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seeds[0]))
        network = build_network(config["scenario"]["array"]["params"]["M"], 121)
    generator = torch.Generator().manual_seed(int(seeds[1]))
    loader = torch.utils.data.DataLoader(training, batch_size=32, shuffle=True, generator=generator)
    optimizer = torch.optim.Adam(network.parameters(), lr=.003)
    criterion = torch.nn.BCEWithLogitsLoss()
    losses = []
    for epoch in range(args.epochs):
        network.train()
        total = 0.0
        for batch in loader:
            R = batch["R"]
            R = R / torch.linalg.vector_norm(R, dim=(1, 2), keepdim=True).clamp_min(1e-12)
            x = torch.stack([R.real, R.imag], dim=1)
            optimizer.zero_grad()
            loss = criterion(network(x), batch["labels"])
            loss.backward()
            optimizer.step()
            total += float(loss.detach())
        losses.append(total / len(loader))
    models.export(network.state_dict(), args.output,
        model_name="cnn_demo", algorithm_id="cnn_grid_example",
        array=config["scenario"]["array"], input="normalized_covariance_real_imag",
        output={"type": "grid_probability", "grid": config["content"]["grid_labels"]["grid"]},
        hparams={"channels": 8}, dataset=directory,
        training={"platform": "local_or_cloud", "epochs": args.epochs,
            "final_metrics": {"loss": losses[-1]}})
    print(json.dumps({"model": str(args.output.resolve()), "losses": losses}))

if __name__ == "__main__":
    main()
'''


def create_example(target: Path) -> Path:
    """将示例写入新建的独立课题目录，不覆盖现有研究文件。"""
    target = target.resolve()
    repository = Path(__file__).resolve().parents[1]
    if target.is_relative_to(repository):
        raise ValueError("训练示例必须放在竞技场仓库外的独立课题目录")
    if target.exists():
        raise ValueError("目标目录已存在，请指定新的课题目录")
    (target / "algorithms" / "cnn_grid").mkdir(parents=True)
    files = {
        "algorithms/__init__.py": "",
        "algorithms/cnn_grid/__init__.py": "",
        "algorithms/cnn_grid/net.py": NETWORK,
        "algorithms/cnn_grid/arena_plugin.py": PLUGIN,
        "train.py": TRAIN,
        ".gitignore": "data/\narena_ws/models/\n__pycache__/\n",
        "README.md": "# 独立 CNN 课题示例\n\n先安装现有环境匹配的 PyTorch，再安装 Arena 核心包。\n\n在此目录运行 `python train.py`，输出普通模型包；将本目录的 algorithms 注册到 Arena，即可选择模型评测。此示例验证数据—训练—导出—推理链路，不承诺训练后的估计精度。\n",  # noqa: E501
    }
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8", newline="\n")
    config = {
        "name": "CNN 训练示例",
        "seed": 12345,
        "num_samples": 512,
        "shard_size": 128,
        "scenario": {
            "array": {"type": "ula", "params": {"M": 16, "d": 0.5}},
            "sources": {
                "K": 2,
                "angles": {"mode": "random", "min": -60, "max": 60, "min_separation": 3},
                "snr_db": {"uniform": [-10, 20]},
            },
            "snapshots": 200,
        },
        "content": {
            "observation": "R",
            "grid_labels": {"grid": {"start": -60, "stop": 60, "step": 1}},
        },
    }
    from arena.core.storage.writer import ResultWriter

    ResultWriter(target)._write_json(target / "dataset_config.json", config)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建独立的 CNN 训练课题")
    parser.add_argument("out", type=Path)
    print(create_example(parser.parse_args().out))
