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
