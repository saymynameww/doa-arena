"""规范 9.2 节的偏差、成功率、分辨概率、计时和检出数指标。"""

from typing import Literal

import numpy as np

from arena_api import MatchedSet, Metric, MetricValue, Param, ParamsModel


class Bias(Metric):
    """按信源统计有符号误差。"""

    id = "bias"
    name = "偏差"
    unit = "°"

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """剔除出错与估计数不正确的试验。"""
        valid = ~ms.failed & (ms.K == ms.K_hat)
        differences = ms.matched[valid] - ms.truth[valid]
        values = np.asarray(
            [
                np.mean(col[np.isfinite(col)]) if np.any(np.isfinite(col)) else np.nan
                for col in differences.T
            ]
        )
        finite = values[np.isfinite(values)]
        return MetricValue(
            float(np.mean(finite)) if len(finite) else np.nan, values, int(valid.sum())
        )


class SuccessRate(Metric):
    """信源数正确且所有误差均在门限以内。"""

    id = "success_rate"
    name = "成功率"
    unit = "%"
    higher_is_better = True

    class Params(ParamsModel):
        """成功门限。"""

        threshold_deg: float = Param(1, gt=0, label="成功门限", unit="°")

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """失败试验计入分母。"""
        p = self.Params.model_validate(params)
        success = [
            not ms.failed[i]
            and ms.K_hat[i] == k
            and bool(np.all(ms.error[i, :k] <= p.threshold_deg))
            for i, k in enumerate(ms.K)
        ]
        return MetricValue(float(np.mean(success)) if success else np.nan, n_used=len(success))


class ResolutionProbability(Metric):
    """仅对双信源定义，支持半间隔和谱谷判据。"""

    id = "resolution_prob"
    name = "分辨概率"
    unit = "%"
    higher_is_better = True

    class Params(ParamsModel):
        """分辨判据。"""

        criterion: Literal["halfgap", "spectrum"] = Param("halfgap", label="分辨判据")

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """不可定义或算法无谱时返回 NaN。"""
        p = self.Params.model_validate(params)
        if not len(ms.K) or np.any(ms.K != 2):
            return MetricValue(np.nan, n_used=0)
        if p.criterion == "spectrum":
            values = ms.extra.get("resolved_by_spectrum", np.full(len(ms.K), np.nan))
            finite = values[np.isfinite(values)]
            return MetricValue(
                float(np.mean(finite)) if len(finite) else np.nan, n_used=len(finite)
            )
        gaps = np.abs(ms.truth[:, 1] - ms.truth[:, 0]) / 2
        values = ~ms.failed & (ms.K_hat == 2) & np.all(ms.error[:, :2] < gaps[:, None], axis=1)
        return MetricValue(float(np.mean(values)), n_used=len(values))


class Time(Metric):
    """计时默认中位数，同时提供均值。"""

    id = "time"
    name = "耗时"
    unit = "ms"

    class Params(ParamsModel):
        """用于曲线显示的汇总统计。"""

        stat: Literal["median", "mean"] = Param("median", label="耗时统计方式")

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """只纳入有有效耗时的调用。"""
        p = self.Params.model_validate(params)
        values = ms.time_ms[np.isfinite(ms.time_ms)]
        mean = float(np.mean(values)) if len(values) else np.nan
        median = float(np.median(values)) if len(values) else np.nan
        return MetricValue(
            median if p.stat == "median" else mean,
            n_used=len(values),
            extra={"mean": mean, "median": median},
        )


class DetectionAccuracy(Metric):
    """估计数与真实信源数一致的比例。"""

    id = "detection_accuracy"
    name = "信源数正确率"
    unit = "%"
    higher_is_better = True

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """出错试验记为失败。"""
        values = ~ms.failed & (ms.K_hat == ms.K)
        return MetricValue(float(np.mean(values)) if len(values) else np.nan, n_used=len(values))
