"""信号生成模块。"""

from .correlation import CorrelationMatrix, generate_correlated_sources
from .generator import SignalGenerator

__all__ = [
    "SignalGenerator",
    "CorrelationMatrix",
    "generate_correlated_sources",
]
