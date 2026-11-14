"""实验运行器。"""

from .core import run_experiment, run_trial
from .results import TrialResult

__all__ = [
    "run_trial",
    "run_experiment",
    "TrialResult",
]
