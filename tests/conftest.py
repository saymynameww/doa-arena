"""Pytest 配置文件。"""

import numpy as np
import pytest


@pytest.fixture
def fixed_seed():
    """固定随机种子。"""
    return 42


@pytest.fixture
def rng(fixed_seed):
    """随机数生成器。"""
    return np.random.Generator(np.random.PCG64(fixed_seed))
