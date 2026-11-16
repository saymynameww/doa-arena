"""插件基类定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

import numpy as np

from .capabilities import Capabilities
from .params import ParamsModel
from .types import ArrayDescriptor, Estimate, Observation, RunContext


class Algorithm(ABC):
    """算法插件基类。

    所有算法插件都必须继承此类并实现抽象方法。

    类属性（必须设置）：
        id: 算法唯一标识（小写、下划线分隔）
        name: 算法显示名称（中文）
        version: 算法版本（语义化版本）
        capabilities: 能力声明
        Params: 参数模型类

    类属性（可选）：
        api_version: 接口包主版本号，默认 1
        category: 算法类别，如 "subspace"、"beamforming"、"learning"
        description: 算法简介
        reference: 参考文献
    """

    # 必需类属性
    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[str]
    capabilities: ClassVar[Capabilities]
    Params: ClassVar[type[ParamsModel]]

    # 可选类属性
    api_version: ClassVar[int] = 1
    category: ClassVar[str] = "general"
    description: ClassVar[str] = ""
    reference: ClassVar[str] = ""

    def __init__(self) -> None:
        """初始化算法实例。

        子类可以覆盖此方法，但应调用 super().__init__()。
        """
        pass

    @classmethod
    def check(
        cls,
        params: ParamsModel,
        array: ArrayDescriptor,
        K: int | None,
    ) -> None:
        """静态兼容性检查（不实例化）。

        在配置校验时调用，检查参数和阵列是否兼容。

        Args:
            params: 算法参数
            array: 阵列描述
            K: 信源数

        Raises:
            ValueError: 配置不兼容时
        """
        # 默认实现：检查能力声明
        caps = cls.capabilities

        # 检查阵列类型
        if caps.array_types is not None:
            if array.type not in caps.array_types:
                raise ValueError(
                    f"{cls.name} 只支持阵列类型 {caps.array_types}，当前为 {array.type}"
                )

        # 检查 ULA
        if caps.requires_ula:
            if array.ula_spacing is None:
                raise ValueError(f"{cls.name} 需要均匀线阵（ULA）")

        # 检查信源数
        if caps.needs_K and K is None:
            raise ValueError(f"{cls.name} 需要已知信源数")

    def load(self, params: ParamsModel, ctx: RunContext) -> None:
        """加载重资源（每个进程一次）。

        用于加载模型权重等重资源。

        Args:
            params: 算法参数
            ctx: 运行上下文
        """
        pass

    def configure(
        self,
        params: ParamsModel,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """配置算法（参数或阵列变化时调用）。

        用于预计算导向矢量网格等。

        Args:
            params: 算法参数
            array: 阵列描述
            ctx: 运行上下文
        """
        pass

    @abstractmethod
    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计一次观测的角度（每次试验调用）。

        Args:
            obs: 观测数据
            ctx: 运行上下文

        Returns:
            估计结果
        """
        pass

    def estimate_batch(
        self,
        obs_list: Sequence[Observation],
        ctx: RunContext,
    ) -> list[Estimate]:
        """批量估计（可选）。

        如果声明 capabilities.batch = True，框架优先调用此方法。

        Args:
            obs_list: 观测列表
            ctx: 运行上下文

        Returns:
            估计结果列表
        """
        # 默认实现：逐个调用 estimate
        return [self.estimate(obs, ctx) for obs in obs_list]

    def close(self) -> None:
        """释放资源（实验结束时调用）。"""
        pass


class ModelAlgorithm(Algorithm):
    """学习型算法基类。

    为学习型算法提供额外的模型加载、设备管理等功能。

    子类只需实现：
    1. build_network() - 构建网络
    2. preprocess() - 预处理观测数据
    3. postprocess() - 后处理网络输出
    """

    def __init__(self) -> None:
        super().__init__()
        self.model: Any = None
        self.device_str: str = "cpu"

    @abstractmethod
    def build_network(self, params: ParamsModel, ctx: RunContext) -> Any:
        """构建网络结构。

        Args:
            params: 算法参数（包含模型路径等）
            ctx: 运行上下文

        Returns:
            网络实例（PyTorch nn.Module）
        """
        pass

    @abstractmethod
    def preprocess(self, obs: Observation) -> Any:
        """预处理观测数据为网络输入。

        Args:
            obs: 观测数据

        Returns:
            网络输入（如 torch.Tensor）
        """
        pass

    @abstractmethod
    def postprocess(
        self,
        network_output: Any,
        obs: Observation,
        ctx: RunContext,
    ) -> Estimate:
        """后处理网络输出为估计结果。

        Args:
            network_output: 网络输出
            obs: 观测数据
            ctx: 运行上下文

        Returns:
            估计结果
        """
        pass

    def load(self, params: ParamsModel, ctx: RunContext) -> None:
        """加载模型权重。"""
        import torch

        self.device_str = ctx.device

        # 构建网络
        self.model = self.build_network(params, ctx)

        # 加载权重
        model_path = getattr(params, "model_path", None)
        if model_path is not None:
            state_dict = torch.load(
                model_path,
                map_location=self.device_str,
                weights_only=True,  # 安全加载
            )
            self.model.load_state_dict(state_dict)

        # 设置为评估模式
        self.model.eval()
        self.model.to(self.device_str)

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计（调用预处理、网络推理、后处理）。"""
        import torch

        # 预处理
        net_input = self.preprocess(obs)

        # 推理
        with torch.no_grad():
            net_output = self.model(net_input)

        # 后处理
        return self.postprocess(net_output, obs, ctx)


class ArrayModel(ABC):
    """阵列插件基类。

    定义阵列几何和导向矢量计算。

    类属性：
        id: 阵列类型唯一标识
        name: 显示名称
        Params: 参数模型类
    """

    id: ClassVar[str]
    name: ClassVar[str]
    Params: ClassVar[type[ParamsModel]]

    @abstractmethod
    def positions(self, params: ParamsModel) -> np.ndarray:
        """计算阵元位置。

        Args:
            params: 阵列参数

        Returns:
            阵元位置，形状 (M, 3)，单位 λ
        """
        pass

    def steering(
        self,
        angles: np.ndarray,
        positions: np.ndarray,
    ) -> np.ndarray:
        """计算导向矢量。

        默认实现使用标准公式，子类可覆盖。

        Args:
            angles: 角度（度），形状 (K,)
            positions: 阵元位置，形状 (M, 3)

        Returns:
            导向矢量，形状 (M, K)
        """
        theta_rad = np.deg2rad(angles)
        u = np.stack(
            [
                np.sin(theta_rad),
                np.cos(theta_rad),
                np.zeros_like(theta_rad),
            ],
            axis=0,
        )
        phase = -2.0 * np.pi * (positions @ u)
        return np.exp(1j * phase)


class Impairment(ABC):
    """阵列误差插件基类。

    定义误差的采样和施加方式。

    类属性：
        id: 误差类型唯一标识
        name: 显示名称
        stage: 作用阶段
        Params: 参数模型类
    """

    id: ClassVar[str]
    name: ClassVar[str]
    stage: ClassVar[str]  # "positions" | "manifold" | "signal" | "output"
    Params: ClassVar[type[ParamsModel]]

    @abstractmethod
    def sample(self, rng: np.random.Generator, M: int, params: ParamsModel) -> Any:
        """采样误差实现。

        Args:
            rng: 随机数生成器
            M: 阵元数
            params: 误差参数

        Returns:
            误差实现（具体类型由子类定义）
        """
        pass

    @abstractmethod
    def apply(self, realization: Any, **kwargs: Any) -> Any:
        """施加误差。

        Args:
            realization: sample() 返回的误差实现
            **kwargs: 根据 stage 不同而不同

        Returns:
            施加误差后的结果
        """
        pass

    def describe(self, realization: Any) -> dict[str, Any]:
        """描述误差实现（可选）。

        Args:
            realization: sample() 返回的误差实现

        Returns:
            可序列化的描述字典
        """
        return {}


class Metric(ABC):
    """指标插件基类。

    类属性：
        id: 指标唯一标识
        name: 显示名称
        unit: 单位（如 "度"、"%"）
        lower_is_better: True 表示越小越好
        Params: 参数模型类（可选）
    """

    id: ClassVar[str]
    name: ClassVar[str]
    unit: ClassVar[str] = ""
    lower_is_better: ClassVar[bool] = True
    Params: ClassVar[type[ParamsModel] | None] = None

    @abstractmethod
    def compute(
        self,
        estimates: np.ndarray,
        truth: np.ndarray,
        matched: np.ndarray,
        **kwargs: Any,
    ) -> float | np.ndarray:
        """计算指标。

        Args:
            estimates: 估计角度，形状 (K̂,)
            truth: 真实角度，形状 (K,)
            matched: 匹配关系，形状 (K_matched,)，每行为 (est_idx, truth_idx)
            **kwargs: 额外参数

        Returns:
            标量或按信源的数组
        """
        pass


class AlgorithmSpec:
    """算法规格（用于脚本模式传入算法）。

    包装算法类和参数，用于 spec() 函数。
    """

    def __init__(
        self,
        algorithm_class: type[Algorithm],
        params: dict[str, Any] | ParamsModel | None = None,
        label: str | None = None,
    ) -> None:
        """初始化算法规格。

        Args:
            algorithm_class: 算法类
            params: 参数字典或参数模型实例
            label: 显示标签（可选）
        """
        self.algorithm_class = algorithm_class
        self.params = params or {}
        self.label = label or algorithm_class.name
