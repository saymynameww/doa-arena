"""按接口规范 9.2 节计算 RMSE。"""

import numpy as np

from arena_api import MatchedSet, Metric, MetricValue, Param, ParamsModel


class RMSEMetric(Metric):
    """默认只纳入估计数正确且无运行错误的试验。"""

    id = "rmse"
    name = "RMSE"
    unit = "°"
    log_axis = True

    class Params(ParamsModel):
        """漏检和虚警的惩罚设置。"""

        include_failed: bool = Param(False, label="纳入估计数错误的试验")
        penalty_deg: float = Param(90, gt=0, label="未匹配惩罚", unit="°")

    def compute(self, ms: MatchedSet, params: ParamsModel) -> MetricValue:
        """对匹配误差平方求平均后开方。"""
        p = self.Params.model_validate(params)
        valid = ~ms.failed & (ms.K_hat == ms.K)
        if p.include_failed:
            valid = np.ones(len(ms.K), dtype=bool)
        per_trial = []
        per_source: list[list[float]] = [[] for _ in range(ms.truth.shape[1])]
        for i in np.flatnonzero(valid):
            errors = ms.error[i, : ms.K[i]] ** 2
            if p.include_failed:
                errors = np.where(np.isfinite(errors), errors, p.penalty_deg**2)
            denominator = max(int(ms.K[i]), int(ms.K_hat[i]))
            if denominator:
                missing = max(0, int(ms.K_hat[i] - ms.K[i]))
                per_trial.append((np.sum(errors) + missing * p.penalty_deg**2) / denominator)
            for j, error in enumerate(errors):
                per_source[j].append(float(error))
        return MetricValue(
            float(np.sqrt(np.mean(per_trial))) if per_trial else np.nan,
            np.asarray([np.sqrt(np.mean(x)) if x else np.nan for x in per_source]),
            len(per_trial),
        )


rmse_metric = RMSEMetric()
