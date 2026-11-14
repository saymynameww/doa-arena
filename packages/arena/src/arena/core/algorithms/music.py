"""MUSIC 算法插件。

按接口规范第 13.2 节实现。
"""

from typing import ClassVar, Literal

import numpy as np
from arena_api import (
    Algorithm,
    ArrayDescriptor,
    Capabilities,
    Estimate,
    Observation,
    Param,
    ParamsModel,
    RunContext,
    Spectrum,
    kit,
)


class MUSIC(Algorithm):
    """MUSIC（Multiple Signal Classification）算法。

    基于子空间分解的经典 DOA 估计算法。
    """

    id: ClassVar[str] = "music"
    name: ClassVar[str] = "MUSIC"
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "subspace"
    description: ClassVar[str] = "基于子空间分解的经典算法，通过搜索噪声子空间的零点估计角度"

    capabilities: ClassVar[Capabilities] = Capabilities(
        needs_K=True,
        coherent="with_smoothing",  # 相干信源需要空间平滑
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(ParamsModel):
        """MUSIC 参数。"""

        grid_start: float = Param(-90, ge=-90, le=90, label="搜索起始角度", unit="°")
        grid_stop: float = Param(90, ge=-90, le=90, label="搜索终止角度", unit="°")
        grid_step: float = Param(0.1, gt=0, le=5, label="网格步长", unit="°")

        smoothing: Literal["none", "forward", "fb"] = Param(
            "none",
            label="空间平滑",
            description="forward=前向, fb=前后向",
        )
        subarray_size: int | None = Param(
            None,
            ge=2,
            label="子阵阵元数",
            none_label="自动",
            description="空间平滑时的子阵大小，None 表示自动选择",
        )

    def __init__(self) -> None:
        super().__init__()
        self.grid: np.ndarray | None = None
        self.A_grid: np.ndarray | None = None
        self.params: MUSIC.Params | None = None

    def configure(
        self,
        params: Params,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """预计算导向矢量网格。

        Args:
            params: MUSIC 参数
            array: 阵列描述
            ctx: 运行上下文
        """
        # 保存参数
        self.params = params

        # 生成角度网格
        self.grid = np.arange(
            params.grid_start,
            params.grid_stop + params.grid_step / 2,
            params.grid_step,
        )

        # 预计算导向矢量
        self.A_grid = array.steering(self.grid)

        ctx.log.info(
            f"MUSIC 配置完成：网格 [{params.grid_start}°, {params.grid_stop}°] "
            f"步长 {params.grid_step}°，共 {len(self.grid)} 个点"
        )

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。

        Args:
            obs: 观测数据
            ctx: 运行上下文

        Returns:
            估计结果
        """
        if self.params is None:
            raise RuntimeError("MUSIC 未配置，请先调用 configure()")

        params = self.params

        # 获取协方差
        R = obs.covariance()

        # 空间平滑
        if params.smoothing != "none":
            L = self._get_subarray_size(params, obs.M, obs.K)
            R = kit.spatial_smoothing(
                R,
                L=L,
                forward_backward=(params.smoothing == "fb"),
            )
        else:
            # 不平滑时也可以选择前后向平均（不改变维度）
            # 这里保持简单，不额外平均
            pass

        # 子空间分解
        _, Un, _, _ = kit.subspace_decomposition(R, obs.K)

        # 计算 MUSIC 谱
        spectrum = kit.music_spectrum(self.A_grid, Un)

        # 峰值搜索
        peak_angles, peak_values = kit.peak_search(
            spectrum,
            self.grid,
            K=obs.K,
            min_separation=params.grid_step * 0.5,  # 最小间隔为半个网格步长
        )

        # 构造结果
        result = Estimate(
            angles=peak_angles,
            spectrum=Spectrum(
                grid=self.grid,
                values=spectrum,
                kind="pseudo",
            ) if ctx.want_spectrum else None,
            info={
                "smoothing": params.smoothing,
                "subarray_size": self._get_subarray_size(params, obs.M, obs.K)
                if params.smoothing != "none"
                else None,
            },
        )

        return result

    def _get_subarray_size(self, params: Params, M: int, K: int) -> int:
        """确定子阵大小。

        Args:
            params: 参数
            M: 阵元数
            K: 信源数

        Returns:
            子阵阵元数 L
        """
        if params.subarray_size is not None:
            L = params.subarray_size
        else:
            # 自动选择：接口规范 13.2 节规定为 ceil(2M/3)
            L = int(np.ceil(2 * M / 3))

        # 验证范围：K < L <= M
        if L > M:
            L = M
        if L <= K:
            L = K + 1

        return L
