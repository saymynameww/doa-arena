"""信号生成模块。"""

from .generator import SignalGenerator
from .correlation import CorrelationMatrix, generate_correlated_sources

__all__ = [
    "SignalGenerator",
    "CorrelationMatrix",
    "generate_correlated_sources",
]
