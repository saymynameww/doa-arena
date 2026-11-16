"""标准场景集与排行榜公共入口。"""

from .core.benchmark import BenchmarkSuite, leaderboard, list_suites, run_suite, save_suite

__all__ = ["BenchmarkSuite", "leaderboard", "list_suites", "run_suite", "save_suite"]
