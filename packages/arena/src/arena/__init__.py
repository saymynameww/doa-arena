"""DOA算法竞技场 - 核心库。

脚本模式门面，提供简洁的顶层API。
"""

__version__ = "0.1.0"

# 门面函数将在实现runner后导出
# from .core.runner import run_experiment as run
# from .core.storage import load_result
# from .core.datasets import generate_dataset as generate

__all__ = [
    "__version__",
    # "run",
    # "load_result",
    # "generate",
]
