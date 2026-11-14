"""场景生成模块。

整合阵列、信号、误差，生成单次试验数据。
"""

from .generator import ScenarioGenerator, generate_trial_data

__all__ = ["ScenarioGenerator", "generate_trial_data"]
