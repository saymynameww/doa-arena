"""插件基类定义。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

import numpy as np

from .capabilities import Capabilities
from .metrics import MatchedSet, MetricValue
from .model import ModelMeta
from .params import ModelPath, Param, ParamsModel
from .types import ArrayDescriptor, Estimate, Issue, Observation, RunContext


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
    capabilities: ClassVar[Capabilities] = Capabilities()
    Params: ClassVar[type[ParamsModel]] = ParamsModel

    # 可选类属性
    api_version: ClassVar[int] = 1
    category: ClassVar[str] = "general"
    description: ClassVar[str] = ""
    reference: ClassVar[str] = ""
    _once_params: dict[str, Any]
    _loaded_parameters: dict[str, Any]
    _current_mask: np.ndarray

    def estimate_once(self, trial: Any, **params: Any) -> Estimate:
        """接口规范 6.6 节：单次 CPU 调试，始终释放资源且不写工作目录。"""
        values = self.Params.model_validate({**getattr(self, "_once_params", {}), **params})
        ctx = RunContext(
            "cpu", logging.getLogger(self.id), True, None, trial.algorithm_rng(self.id)
        )
        try:
            issues = self.check(values, trial.array, trial.observation.K) or []
            errors = [issue.message for issue in issues if issue.level == "error"]
            if errors:
                raise ValueError("；".join(errors))
            self.load(values, ctx)
            self.configure(values, trial.array, ctx)
            return self.estimate(trial.observation, ctx)
        finally:
            self.close()

    @classmethod
    def spec(cls, label: str | None = None, **params: Any) -> AlgorithmSpec:
        """按接口规范 6.6 构造脚本算法描述。"""
        validated = cls.Params.model_validate(params)
        return AlgorithmSpec(cls, params=validated.model_dump(mode="json"), label=label)

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
    ) -> list[Issue]:
        """静态兼容性检查（不实例化）。

        在配置校验时调用，检查参数和阵列是否兼容。

        Args:
            params: 算法参数
            array: 阵列描述
            K: 信源数

        Returns:
            可定位的错误和警告列表。
        """
        # 默认实现：检查能力声明
        caps = cls.capabilities
        issues: list[Issue] = []

        # 检查阵列类型
        if caps.array_types is not None:
            if array.type not in caps.array_types:
                issues.append(
                    Issue(
                        "error",
                        f"{cls.name} 只支持阵列类型 {caps.array_types}，当前为 {array.type}",
                    )
                )

        # 检查 ULA
        if caps.requires_ula:
            if array.ula_spacing is None:
                issues.append(Issue("error", f"{cls.name} 需要均匀线阵（ULA）"))

        # 检查信源数
        if caps.needs_K and K is None:
            issues.append(Issue("error", f"{cls.name} 需要已知信源数"))
        if not caps.supports_masked_elements and not np.all(array.element_mask):
            issues.append(
                Issue("error", f"{cls.name} 不支持已知故障阵元，请关闭此算法或关闭算法已知选项")
            )
        if array.dims not in caps.dims:
            issues.append(Issue("error", f"{cls.name} 不支持当前角度维数"))
        return issues

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
        from dataclasses import replace

        return [
            self.estimate(obs, replace(ctx, rng=ctx.rng_for(i))) for i, obs in enumerate(obs_list)
        ]

    def close(self) -> None:
        """释放资源（实验结束时调用）。"""
        pass


class ModelAlgorithm(Algorithm):
    """接口规范第 7 章：模型元数据校验、设备管理与批量推理。"""

    category = "learning"
    capabilities = Capabilities(batch=True, parallel=False, uses_gpu=True)

    class Params(ParamsModel):
        """所有学习算法共有的参数。"""

        model: ModelPath = Param(..., label="模型包", json_schema_extra={"x-reload": True})
        device: Literal["auto", "cuda", "cpu"] = Param(
            "auto", label="推理设备", json_schema_extra={"x-reload": True}
        )
        batch_size: int = Param(256, ge=1, le=8192, label="推理批大小")

    def __init__(self) -> None:
        super().__init__()
        self.model: Any = None
        self.device_str = "cpu"
        self.meta: ModelMeta | None = None
        self.params: ParamsModel | None = None

    @abstractmethod
    def build_network(self, meta: ModelMeta, params: ParamsModel) -> Any:
        """根据元数据构造网络；子类在方法内导入 torch。"""
        raise NotImplementedError

    @abstractmethod
    def preprocess(
        self, obs_list: Sequence[Observation], meta: ModelMeta, params: ParamsModel
    ) -> Any:
        """将一批观测转换为网络输入张量。"""
        raise NotImplementedError

    @abstractmethod
    def postprocess(
        self,
        output: Any,
        obs_list: Sequence[Observation],
        meta: ModelMeta,
        params: ParamsModel,
        want_spectrum: bool,
    ) -> list[Estimate]:
        """将一批网络输出转换为相同数量的估计。"""
        raise NotImplementedError

    @classmethod
    def check_model(
        cls, meta: ModelMeta, params: ParamsModel, array: ArrayDescriptor, K: int | None
    ) -> list[Issue]:
        """子类可增加模型结构或信源数限制。"""
        return []

    @classmethod
    def check(cls, params: ParamsModel, array: ArrayDescriptor, K: int | None) -> list[Issue]:
        """只读取 JSON，检查算法、接口及训练阵列兼容性。"""
        issues = super().check(params, array, K)
        try:
            meta = ModelMeta.from_file(getattr(params, "model"))
            if meta.algorithm_id != cls.id:
                issues.append(Issue("error", "模型包所属算法不匹配，请选择此算法导出的模型"))
            if meta.array.get("type") != array.type or any(
                array.params.get(k) != v for k, v in meta.array.get("params", {}).items()
            ):
                issues.append(Issue("error", "评测阵列与模型训练阵列不一致，请选择匹配的模型"))
            if meta.trained_on.get("source") != "arena":
                issues.append(Issue("warning", "训练范围未知：模型使用外部数据集"))
            issues.extend(cls.check_model(meta, params, array, K))
        except (ValueError, OSError) as exc:
            issues.append(Issue("error", f"无法读取模型包：{exc}"))
        return issues

    def load(self, params: ParamsModel, ctx: RunContext) -> None:
        """核对哈希后安全加载 state_dict，使用指定设备进入评估模式。"""
        import torch

        self.meta = ModelMeta.from_file(getattr(params, "model"))
        self.meta.verify_weights()
        self._model_provenance = {
            "path": str(self.meta.path),
            "weights_sha256": self.meta.weights["sha256"],
            "model_name": self.meta.model_name,
        }
        requested = getattr(params, "device")
        self.device_str = (
            ("cuda" if torch.cuda.is_available() else "cpu") if requested == "auto" else requested
        )
        if self.device_str == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA 不可用，请将推理设备改为 CPU 或自动")
        self.model = self.build_network(self.meta, params)
        state = torch.load(
            self.meta.path / "model.pt", map_location=self.device_str, weights_only=True
        )
        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device_str)
        self.model.eval()
        self.params = params

    def configure(self, params: ParamsModel, array: ArrayDescriptor, ctx: RunContext) -> None:
        """更新轻量参数；模型与设备改变由 Runner 重新 load。"""
        self.params = params

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """单次估计使用同一批推理实现。"""
        return self.estimate_batch([obs], ctx)[0]

    def estimate_batch(self, obs_list: Sequence[Observation], ctx: RunContext) -> list[Estimate]:
        """按 batch_size 切分，在 inference_mode 下运行网络。"""
        import torch

        if self.model is None or self.meta is None or self.params is None:
            raise ValueError("模型尚未加载，请先调用 load")
        result = []
        batch_size = int(getattr(self.params, "batch_size"))
        with torch.inference_mode():
            for start in range(0, len(obs_list), batch_size):
                observations = obs_list[start : start + batch_size]
                inputs = self.preprocess(observations, self.meta, self.params).to(self.device_str)
                output = self.model(inputs)
                estimates = self.postprocess(
                    output, observations, self.meta, self.params, ctx.want_spectrum
                )
                if len(estimates) != len(observations):
                    raise ValueError("模型后处理结果数量必须等于输入观测数量")
                result.extend(estimates)
        return result

    def close(self) -> None:
        """释放网络引用及本算法使用的 CUDA 缓存。"""
        self.model = None
        self.meta = None
        self.params = None
        if self.device_str == "cuda":
            import torch

            torch.cuda.empty_cache()


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
    version: ClassVar[str] = "1.0.0"
    api_version: ClassVar[int] = 1
    dims: ClassVar[tuple[int, ...]] = (1,)

    @classmethod
    def check(cls, params: ParamsModel) -> list[Issue]:
        """返回阵列参数兼容性问题。"""
        return []

    def steering_derivative(self, angles: np.ndarray, positions: np.ndarray) -> np.ndarray:
        """默认平面波流形对弧度求导，使用传入的实际阵元位置。"""
        return ArrayDescriptor(self.id, {}, positions).steering_derivative(angles)

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
    version: ClassVar[str] = "1.0.0"
    api_version: ClassVar[int] = 1

    @classmethod
    def check(cls, params: ParamsModel, M: int) -> list[Issue]:
        """返回与阵元数量有关的误差参数问题。"""
        return []

    @abstractmethod
    def sample(self, rng: np.random.Generator, M: int) -> Mapping[str, np.ndarray]:
        """采样与误差强度无关的基础随机量。"""
        raise NotImplementedError

    @abstractmethod
    def apply(
        self, data: np.ndarray, draw: Mapping[str, np.ndarray], params: ParamsModel
    ) -> np.ndarray:
        """按误差参数将基础随机量施加到当前阶段数据。"""
        raise NotImplementedError

    def known_mask(
        self, draw: Mapping[str, np.ndarray], params: ParamsModel, M: int
    ) -> np.ndarray | None:
        """返回算法已知的有效阵元掩码；默认不公开误差位置。"""
        return None

    def describe(
        self, draw: Mapping[str, np.ndarray], params: ParamsModel, M: int
    ) -> Mapping[str, np.ndarray]:
        """返回本次误差实现的可保存描述。"""
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
    version: ClassVar[str] = "1.0.0"
    api_version: ClassVar[int] = 1
    name: ClassVar[str]
    unit: ClassVar[str] = ""
    lower_is_better: ClassVar[bool] = True
    Params: ClassVar[type[ParamsModel]] = ParamsModel
    higher_is_better: ClassVar[bool] = False
    log_axis: ClassVar[bool] = False

    @abstractmethod
    def compute(
        self,
        ms: MatchedSet,
        params: ParamsModel,
    ) -> MetricValue:
        """计算指标。

        Args:
            ms: 一个扫描点一个算法的全部匹配结果
            params: 指标参数

        Returns:
            汇总值与可选的逐源统计
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
