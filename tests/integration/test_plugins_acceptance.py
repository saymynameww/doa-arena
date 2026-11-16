"""外部算法接入不修改竞技场代码。"""

import numpy as np

from arena.core.plugins import probe, resolve_algorithm


def test_external_directory_import_and_failure_isolation(tmp_path):
    plugin = tmp_path / "algorithms" / "demo"
    plugin.mkdir(parents=True)
    (plugin / "net.py").write_text("VALUE=12.5", encoding="utf-8")
    (plugin / "train.py").write_text("raise RuntimeError('训练脚本不应导入')", encoding="utf-8")
    (plugin / "arena_plugin.py").write_text(
        "from arena_api import Algorithm, Estimate\nfrom .net import VALUE\n"
        "class Demo(Algorithm):\n    id='demo'\n    name='测试算法'\n    version='1.0'\n"
        "    def estimate(self,obs,ctx): return Estimate.from_angles([VALUE])\n",
        encoding="utf-8",
    )
    (plugin.parent / "broken.py").write_text("bad syntax here", encoding="utf-8")
    sources = [{"type": "path", "value": str(plugin.parent)}]
    report = probe(sources)
    assert len(report["failures"]) == 1
    item = next(a for a in report["algorithms"] if a["id"] == "demo")
    cls = resolve_algorithm("demo", item["origin"])
    np.testing.assert_array_equal(cls().estimate(None, None).angles, [12.5])
    assert item["origin"]["code_hash"]


def test_four_plugin_categories_and_external_array_run(tmp_path):
    """同一入口可注册四类插件，类别相同才检查 ID 冲突。"""
    from arena.core.config import ExperimentConfig
    from arena.core.runner.core import run_experiment

    source = tmp_path / "plugins"
    source.mkdir()
    (source / "demo.py").write_text(
        "import numpy as np\n"
        "from arena_api import ArrayModel, Impairment, Metric, MetricValue, ParamsModel\n"
        "class Geometry(ArrayModel):\n id='demo'\n name='几何探针'\n Params=ParamsModel\n"
        " def positions(self,params): return np.column_stack([np.arange(8)*0.5,np.zeros((8,2))])\n"
        "class Error(Impairment):\n id='demo'\n name='误差探针'\n Params=ParamsModel\n"
        " stage='output'\n"
        " def sample(self,rng,M): return {}\n def apply(self,data,draw,params): return data\n"
        "class Score(Metric):\n id='demo'\n name='指标探针'\n Params=ParamsModel\n"
        " def compute(self,*args,**kwargs): return MetricValue(1.0, n_used=1)\n",
        encoding="utf-8",
    )
    report = probe([{"type": "path", "value": str(source)}])
    assert report["failures"] == []
    array = next(item for item in report["arrays"] if item["id"] == "demo")
    impairment = next(item for item in report["impairments"] if item["id"] == "demo")
    metric = next(item for item in report["metrics"] if item["id"] == "demo")
    config = ExperimentConfig.model_validate(
        {
            "trials": 1,
            "scenario": {
                "array": {"type": "demo", "params": {}, "origin": array["origin"]},
                "impairments": [{"type": "demo", "origin": impairment["origin"]}],
            },
            "algorithms": [{"id": "music"}],
            "metrics": {"include": ["demo"], "origins": {"demo": metric["origin"]}},
        }
    )
    result = run_experiment(config)
    assert "music" in result.points[0].trials[0].estimates

    from arena.core.metrics.summary import point_metrics

    assert point_metrics(result, result.points[0], "music")["metric_values"]["demo"]["value"] == 1
    assert {"array/demo", "impairment/demo", "metric/demo"} <= result.metadata["plugins"].keys()
