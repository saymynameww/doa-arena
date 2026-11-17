"""故意违反接口约定的插件必须被检查工具检出。"""

import numpy as np
import pytest

from arena.core.algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC
from arena.core.plugin_check import check_plugin
from arena_api import Algorithm, Capabilities, Estimate


class Good(Algorithm):
    id = "check_example"
    name = "检查示例"
    version = "1.0.0"
    capabilities = Capabilities(batch=True)

    def estimate(self, obs, ctx):
        return Estimate.from_angles([-10, 10])


@pytest.mark.parametrize("plugin", [CBF, MVDR, MUSIC, RootMUSIC, ESPRIT, Good])
def test_builtin_and_valid_plugin_pass(plugin):
    result = check_plugin(plugin)
    assert result["passed"], result


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("definition", "定义"),
        ("output", "默认参数运行与输出格式"),
        ("determinism", "确定性"),
        ("batch", "批量一致"),
        ("input", "不修改输入"),
        ("close", "资源释放"),
        ("random", "无全局随机状态"),
    ],
)
def test_violating_plugins_are_detected(fault, expected):
    class Broken(Good):
        counter = 0

        def estimate(self, obs, ctx):
            if fault == "output":
                return [-10, 10]
            if fault == "determinism":
                Broken.counter += 1
                return Estimate.from_angles([Broken.counter / 10])
            if fault == "input":
                obs.X.flags.writeable = True
                obs.X[0, 0] = 123
            if fault == "random":
                np.random.random()  # noqa: NPY002 -- 故意违规，验证诊断能力
            return super().estimate(obs, ctx)

        def estimate_batch(self, observations, ctx):
            if fault == "batch":
                return [Estimate.from_angles([0])] * len(observations)
            return super().estimate_batch(observations, ctx)

        def close(self):
            if fault == "close":
                raise ValueError("释放失败")

    if fault == "definition":
        Broken.id = "INVALID"
    result = check_plugin(Broken)
    assert not result["passed"]
    assert any(c["name"] == expected and c["status"] == "failed" for c in result["checks"])
