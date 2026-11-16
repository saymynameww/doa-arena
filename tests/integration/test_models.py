"""模型包安全检查、生命周期与批推理。"""

import logging
import zipfile

import numpy as np
import pytest

from arena import models
from arena.core.exploration import Scenario
from arena.core.models import training_issues
from arena_api import Estimate, ModelAlgorithm, ModelMeta, RunContext


class TinyModel(ModelAlgorithm):
    id = "tiny_test"
    name = "测试模型"
    version = "1.0.0"

    def build_network(self, meta, params):
        import torch

        return torch.nn.Linear(2, 2)

    def preprocess(self, obs_list, meta, params):
        import torch

        return torch.tensor(
            [[obs.covariance()[0, 0].real, 1] for obs in obs_list], dtype=torch.float32
        )

    def postprocess(self, output, obs_list, meta, params, want_spectrum):
        return [Estimate(row.detach().cpu().numpy()) for row in output]


def export_tiny(directory):
    torch = pytest.importorskip("torch")
    # 固定参数隔离网络初始化随机性，测试只验证导出、推理生命周期。
    state = {"weight": torch.tensor([[0.01, 0], [0, 0.02]]), "bias": torch.tensor([-1.0, 1.0])}
    return models.export(
        state,
        directory,
        model_name="tiny",
        algorithm_id=TinyModel.id,
        array={"type": "ula", "params": {"M": 8, "d": 0.5}},
        input="covariance",
        output={"type": "angles"},
        dataset={
            "num_samples": 10,
            "scenario": {
                "array": {"type": "ula", "params": {"M": 8, "d": 0.5}},
                "sources": {"K": 2, "snr_db": {"uniform": [0, 10]}},
            },
        },
    )


def test_model_export_import_and_inference(tmp_path):
    package = export_tiny(tmp_path / "原始模型")
    meta = ModelMeta.from_file(package)
    meta.verify_weights()
    imported = models.import_package(package, tmp_path / "中文课题")
    assert imported.name == "tiny"
    with pytest.raises(ValueError, match="同名"):
        models.import_package(package, tmp_path / "中文课题")
    trial = Scenario({"array": {"params": {"M": 8, "d": 0.5}}}).sample(seed=10)
    params = TinyModel.Params(model=str(imported), device="cpu", batch_size=2)
    assert not TinyModel.check(params, trial.array, 2)
    instance = TinyModel()
    ctx = RunContext("cpu", logging.getLogger("test"), False, tmp_path, np.random.default_rng(0))
    instance.load(params, ctx)
    instance.configure(params, trial.array, ctx)
    outputs = instance.estimate_batch([trial.observation] * 5, ctx)
    assert len(outputs) == 5
    for output in outputs:
        # 线性层 float32 推理，容差取 1e-6。
        np.testing.assert_allclose(output.angles, outputs[0].angles, rtol=1e-6)
    assert not instance.model.training
    instance.close()
    assert instance.model is None
    warnings = training_issues(meta, Scenario({"sources": {"snr_db": 20}}).config)
    assert any("SNR" in issue.message for issue in warnings)
    (imported / "model.pt").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="哈希"):
        instance.load(params, ctx)


def test_zip_path_traversal_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("../outside.txt", "bad")
    with pytest.raises(ValueError, match="不安全"):
        models.import_package(archive, tmp_path / "workspace")
    assert not (tmp_path / "outside.txt").exists()


def test_metadata_checks_do_not_import_torch(tmp_path):
    import subprocess
    import sys

    source = (
        "import sys; from arena_api import ModelAlgorithm, ModelMeta; "
        "from arena import datasets, models; assert 'torch' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_core_import_without_plotting_dependencies():
    import subprocess
    import sys

    source = (
        "import sys; sys.modules['plotly'] = None; "
        "from arena import datasets, models; "
        "assert 'torch' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
