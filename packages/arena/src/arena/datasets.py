"""无需 Web 或 PyTorch 的数据集公共入口。"""

from .core.datasets import Dataset, DatasetConfig, TorchDataset, generate, grid_labels

open = Dataset

__all__ = ["Dataset", "DatasetConfig", "TorchDataset", "generate", "grid_labels", "open"]
