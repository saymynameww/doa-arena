"""核心数据类型定义。

所有类型都是不可变的dataclass，数组为只读。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class Issue:
    """静态兼容性问题，param 用于定位表单字段。"""

    level: Literal["error", "warning"]
    message: str
    param: str | None = None


@dataclass(frozen=True)
class ArrayDescriptor:
    """标称阵列描述（不含误差）。

    Attributes:
        type: 阵列插件 id，如 "ula"
        params: 阵列插件参数，如 {"M": 16, "d": 0.5}
        positions: 阵元位置，形状 (M, 3)，单位 λ，只读
        element_mask: 形状 (M,) bool，False 表示算法已知该阵元故障
    """

    type: str
    params: Mapping[str, Any]
    positions: np.ndarray
    element_mask: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=bool))
    model: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """后处理：设置默认mask、转换数组为只读。"""
        # 设置默认 mask（全部有效）
        if self.element_mask.size == 0:
            object.__setattr__(self, "element_mask", np.ones(self.M, dtype=bool))

        # 确保数组只读
        if not self.positions.flags.writeable:
            pass  # 已经是只读
        else:
            pos = self.positions.copy()
            pos.flags.writeable = False
            object.__setattr__(self, "positions", pos)

        if not self.element_mask.flags.writeable:
            pass
        else:
            mask = self.element_mask.copy()
            mask.flags.writeable = False
            object.__setattr__(self, "element_mask", mask)

        # 形状检查
        if self.positions.ndim != 2 or self.positions.shape[1] != 3:
            raise ValueError(f"positions 必须是形状 (M, 3)，实际为 {self.positions.shape}")
        if self.element_mask.shape != (self.M,):
            raise ValueError(
                f"element_mask 必须是形状 ({self.M},)，实际为 {self.element_mask.shape}"
            )

    @property
    def dims(self) -> int:
        """当前阵列支持的角度维数。"""
        dims = getattr(self.model, "dims", (1,))
        return dims[0] if isinstance(dims, tuple) else dims

    @property
    def M(self) -> int:
        """阵元数。"""
        return self.positions.shape[0]

    @property
    def ula_spacing(self) -> float | None:
        """ULA 间距（单位 λ）。

        若所有阵元位于 x 轴且等间距，返回间距 d；否则返回 None。
        """
        # 检查是否在 x 轴上
        if not np.allclose(self.positions[:, 1:], 0.0):
            return None

        # 检查是否等间距
        x = self.positions[:, 0]
        if self.M < 2:
            return None

        diffs = np.diff(x)
        if not np.allclose(diffs, diffs[0]):
            return None

        return float(diffs[0])

    def steering(self, angles: ArrayLike) -> np.ndarray:
        """计算导向矢量。

        Args:
            angles: 角度（度），形状 (K,)

        Returns:
            导向矢量矩阵，形状 (M, K)，complex128
        """
        angles = np.asarray(angles, dtype=np.float64)
        if angles.ndim != 1:
            raise ValueError(f"angles 必须是一维数组，实际维度 {angles.ndim}")
        if self.model is not None:
            result = np.asarray(self.model.steering(angles, self.positions))
            result.flags.writeable = False
            return result

        # 角度转弧度
        theta_rad = np.deg2rad(angles)

        # 方向单位矢量：一维 DOA 在 x-y 平面
        # u(θ) = (sin θ, cos θ, 0)
        u = np.stack(
            [np.sin(theta_rad), np.cos(theta_rad), np.zeros_like(theta_rad)], axis=0
        )  # (3, K)

        # 导向矢量：a(θ) = exp(-j·2π·p·u)
        # positions: (M, 3), u: (3, K) -> inner: (M, K)
        phase = -2.0 * np.pi * (self.positions @ u)
        a = np.exp(1j * phase)

        a.flags.writeable = False
        return a

    def steering_derivative(self, angles: ArrayLike) -> np.ndarray:
        """计算导向矢量对角度的导数（每弧度）。

        Args:
            angles: 角度（度），形状 (K,)

        Returns:
            导数矩阵，形状 (M, K)，complex128
        """
        angles = np.asarray(angles, dtype=np.float64)
        if self.model is not None:
            return np.asarray(self.model.steering_derivative(angles, self.positions))
        theta_rad = np.deg2rad(angles)

        # d(u)/d(θ) = (cos θ, -sin θ, 0)
        du_dtheta = np.stack(
            [np.cos(theta_rad), -np.sin(theta_rad), np.zeros_like(theta_rad)], axis=0
        )  # (3, K)

        # d(a)/d(θ) = -j·2π·p·(du/dθ)·a(θ)
        a = self.steering(angles)
        da_dtheta = -1j * 2.0 * np.pi * (self.positions @ du_dtheta) * a

        da_dtheta.flags.writeable = False
        return da_dtheta


@dataclass(frozen=True)
class Observation:
    """一次试验的观测数据。

    Attributes:
        X: 接收数据，形状 (M, N)，complex128，只读
        K: 信源数；None 表示未知（算法需要自己估计）
        kind: 数据类型，V1 只有 "narrowband"
        meta: 元信息（算法可以合法知道的），如 {"snapshots": N}
    """

    X: np.ndarray
    K: int | None = None
    kind: Literal["narrowband"] = "narrowband"
    meta: Mapping[str, Any] = field(default_factory=dict)

    _covariance: np.ndarray | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """后处理：确保 X 只读。"""
        if not self.X.flags.writeable:
            pass
        else:
            X = self.X.copy()
            X.flags.writeable = False
            object.__setattr__(self, "X", X)

        # 形状检查
        if self.X.ndim != 2:
            raise ValueError(f"X 必须是二维数组，实际维度 {self.X.ndim}")

        if not np.iscomplexobj(self.X):
            raise ValueError("X 必须是复数数组")

    @property
    def M(self) -> int:
        """阵元数。"""
        return self.X.shape[0]

    @property
    def N(self) -> int:
        """快拍数。"""
        return self.X.shape[1]

    def covariance(self) -> np.ndarray:
        """样本协方差矩阵 R̂ = X·X^H / N。

        首次调用时计算并缓存。

        Returns:
            协方差矩阵，形状 (M, M)，complex128，只读
        """
        if self._covariance is None:
            R = (self.X @ self.X.conj().T) / self.N
            R.flags.writeable = False
            object.__setattr__(self, "_covariance", R)
        assert self._covariance is not None
        return self._covariance


@dataclass(frozen=True)
class Spectrum:
    """空间谱。

    Attributes:
        grid: 角度网格（度），形状 (G,)，升序排列
        values: 谱值（线性值，非负），形状 (G,)
        kind: 谱类型
    """

    grid: np.ndarray
    values: np.ndarray
    kind: Literal["power", "pseudo", "probability"] = "pseudo"

    def __post_init__(self) -> None:
        """后处理：转换为只读数组。"""
        for name in ["grid", "values"]:
            arr = getattr(self, name)
            if not arr.flags.writeable:
                continue
            arr = arr.copy()
            arr.flags.writeable = False
            object.__setattr__(self, name, arr)

        # 检查
        if self.grid.ndim != 1 or self.values.ndim != 1:
            raise ValueError("grid 和 values 必须是一维数组")
        if self.grid.shape != self.values.shape:
            raise ValueError(
                f"grid 和 values 形状必须相同，实际为 {self.grid.shape} vs {self.values.shape}"
            )


@dataclass(frozen=True)
class Estimate:
    """估计结果。

    Attributes:
        angles: 估计角度（度），形状 (K̂,)，顺序任意
        spectrum: 空间谱（可选）
        info: 附加信息（可选），必须可 JSON 序列化
    """

    angles: np.ndarray
    spectrum: Spectrum | None = None
    info: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """后处理：转换 angles 为只读数组。"""
        angles = np.asarray(self.angles, dtype=np.float64)
        if angles.ndim != 1:
            raise ValueError(f"angles 必须是一维数组，实际维度 {angles.ndim}")

        angles.flags.writeable = False
        object.__setattr__(self, "angles", angles)

    @property
    def K_hat(self) -> int:
        """估计的信源数。"""
        return len(self.angles)

    @classmethod
    def from_angles(
        cls,
        angles: ArrayLike,
        spectrum: Spectrum | None = None,
        **info: Any,
    ) -> Estimate:
        """便利构造函数。

        Args:
            angles: 估计角度
            spectrum: 空间谱（可选）
            **info: 附加信息

        Returns:
            Estimate 实例
        """
        return cls(angles=np.asarray(angles, dtype=float), spectrum=spectrum, info=info)


@dataclass
class RunContext:
    """运行上下文。

    由框架创建和维护，插件不得自己构造。

    Attributes:
        device: 计算设备，"cpu" 或 "cuda" / "cuda:0"
        log: 日志器，写入实验目录的 log.txt
        want_spectrum: 当前调用是否需要返回空间谱
        workspace: 当前工作目录路径
        rng: 当前试验专用的随机数生成器
    """

    device: str
    log: logging.Logger
    want_spectrum: bool
    workspace: Path | None
    rng: np.random.Generator
    _batch_rngs: tuple[np.random.Generator, ...] | None = field(default=None, repr=False)

    def rng_for(self, i: int) -> np.random.Generator:
        """批量调用中第 i 个观测的随机数生成器。

        Args:
            i: 观测索引（从 0 开始）

        Returns:
            该观测专用的随机数生成器
        """
        if self._batch_rngs is not None:
            from copy import deepcopy

            return deepcopy(self._batch_rngs[i])
        # 从当前 rng 派生子生成器
        # 使用固定方式派生，保证可复现
        parent = getattr(self.rng.bit_generator, "seed_seq", None)
        if parent is None:
            parent = getattr(self.rng.bit_generator, "_seed_seq")
        seed_sequence = np.random.SeedSequence(
            entropy=parent.entropy, spawn_key=(*parent.spawn_key, i)
        )
        return np.random.Generator(np.random.PCG64(seed_sequence))
