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
    Issue,
    Observation,
    Param,
    ParamsModel,
    RunContext,
    Spectrum,
    SpectrumSearchParams,
    kit,
)


class MUSIC(Algorithm):
    """MUSIC（Multiple Signal Classification）算法。

    基于子空间分解的经典 DOA 估计算法。
    """

    id: ClassVar[str] = "music"
    name: ClassVar[str] = "MUSIC"
    version: ClassVar[str] = "1.1.0"
    category: ClassVar[str] = "subspace"
    description: ClassVar[str] = "基于子空间分解的经典算法，通过搜索噪声子空间的零点估计角度"

    capabilities: ClassVar[Capabilities] = Capabilities(
        needs_K=True,
        coherent="with_smoothing",  # 相干信源需要空间平滑
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(SpectrumSearchParams):
        """MUSIC 参数。"""

        smoothing: Literal["none", "forward", "fb"] = Param(
            "none",
            label="空间平滑",
            description="forward=前向, fb=前后向",
        )
        subarray: int | None = Param(
            None,
            ge=2,
            label="子阵阵元数",
            none_label="自动",
            description="空间平滑时的子阵大小，None 表示自动选择",
        )

    @classmethod
    def check(cls, params: ParamsModel, array: ArrayDescriptor, K: int | None) -> list[Issue]:
        """空间平滑需要完整均匀线阵，并在运行前校验孔径。"""
        issues = super().check(params, array, K)
        p = cls.Params.model_validate(params)
        if p.scan_min >= p.scan_max:
            issues.append(Issue("error", "搜索起始角度必须小于终止角度", "scan_min"))
        if p.smoothing != "none":
            if array.ula_spacing is None or not np.all(array.element_mask):
                issues.append(
                    Issue("error", "空间平滑需要完整均匀线阵，请关闭平滑或已知故障", "smoothing")
                )
            elif K is not None:
                try:
                    kit.checked_subarray(array.M, K, p.smoothing, p.subarray)
                except ValueError as exc:
                    issues.append(Issue("error", str(exc), "subarray"))
        return issues

    def __init__(self) -> None:
        super().__init__()
        self.grid: np.ndarray | None = None
        self.A_grid: np.ndarray | None = None
        self.params: MUSIC.Params | None = None

    def configure(
        self,
        params: ParamsModel,
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
        params = self.Params.model_validate(params)
        self.params = params

        # 生成角度网格
        self.grid = kit.search_grid(
            params.scan_min, params.scan_max, params.grid_step, params.legacy_grid
        )
        self.array = array

        # 预计算导向矢量
        self.element_mask = array.element_mask
        self.A_grid = array.steering(self.grid)[self.element_mask]

        ctx.log.info(
            f"MUSIC 配置完成：网格 [{params.scan_min}°, {params.scan_max}°] "
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

        assert self.grid is not None and self.A_grid is not None
        if obs.K is None or not 1 <= obs.K < obs.M:
            raise ValueError("该算法需要已知且小于阵元数的正整数信源数")
        params = self.params

        if not np.all(self.element_mask):
            obs = Observation(X=obs.X[self.element_mask], K=obs.K)

        if obs.K is None or not 1 <= obs.K < obs.M:
            raise ValueError("有效阵元数必须大于信源数")

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
            # 空间平滑后，需要使用子阵导向矢量（前 L 个阵元）
            A_grid_to_use = self.A_grid[:L, :]
        else:
            A_grid_to_use = self.A_grid

        # 子空间分解
        _, Un, _, _ = kit.subspace_decomposition(R, obs.K)

        # 计算 MUSIC 谱
        spectrum = kit.music_spectrum(A_grid_to_use, Un)
        spectrum /= spectrum.max()

        # 峰值搜索
        peak_angles, _ = kit.peak_search(
            spectrum,
            self.grid,
            K=obs.K,
            min_separation=params.grid_step * 0.5,  # 最小间隔为半个网格步长
        )

        def evaluate(angles: np.ndarray) -> np.ndarray:
            steering = self.array.steering(angles)[self.element_mask]
            return kit.music_spectrum(steering[: Un.shape[0]], Un)

        peak_angles = kit.refine_spectrum_peaks(
            spectrum,
            self.grid,
            peak_angles,
            self.params.peak_refinement,
            evaluate,
            self.params.local_step,
        )

        # 构造结果
        result = Estimate(
            angles=peak_angles,
            spectrum=Spectrum(
                grid=self.grid,
                values=spectrum,
                kind="pseudo",
            )
            if ctx.want_spectrum
            else None,
            info={
                "peak_refinement": params.peak_refinement,
                "n_peaks_found": len(peak_angles),
                "search_grid": [params.scan_min, params.scan_max, params.grid_step],
                "smoothing": params.smoothing,
                "subarray": self._get_subarray_size(params, obs.M, obs.K)
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
        return kit.checked_subarray(M, K, params.smoothing, params.subarray)
