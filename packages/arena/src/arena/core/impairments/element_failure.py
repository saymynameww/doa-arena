"""阵元故障插件。

部分阵元故障（输出置零或仅含噪声）。
"""

from collections.abc import Mapping
from typing import ClassVar, Literal

import numpy as np

from arena_api import Impairment, Param, ParamsModel


class ElementFailure(Impairment):
    """阵元故障。

    指定或随机选择部分阵元作为故障阵元，其输出置零或仅含噪声。
    """

    id: ClassVar[str] = "element_failure"
    name: ClassVar[str] = "阵元故障"
    version: ClassVar[str] = "1.0.0"

    class Params(ParamsModel):
        """阵元故障参数。"""

        indices: list[int] | None = Param(
            None,
            label="故障阵元索引",
            none_label="随机选择",
            description="指定故障阵元（0-based），None 表示随机选择",
        )
        count: int = Param(
            1,
            ge=0,
            le=15,
            label="故障阵元数",
            description="随机选择时的数量",
        )
        mode: Literal["zero", "noise_only"] = Param(
            "zero",
            label="故障模式",
            description="zero=输出置零, noise_only=仅含噪声（无信号）",
        )
        known: bool = Param(
            False,
            label="算法已知",
            description="算法是否知道故障位置",
        )

    @classmethod
    def stage_for(cls, params: Params) -> Literal["signal", "output"]:
        """根据模式返回阶段。

        Args:
            params: 参数

        Returns:
            "signal" (noise_only) 或 "output" (zero)
        """
        if params.mode == "noise_only":
            return "signal"
        else:
            return "output"

    def sample(
        self,
        rng: np.random.Generator,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """抽取标准化随机量。

        生成全部 M-1 个候选阵元（排除第 0 个）的随机排列。

        Args:
            rng: 随机数生成器
            M: 阵元数

        Returns:
            随机排列 "permutation" (M-1,)
        """
        # 候选阵元：1, 2, ..., M-1（排除第 0 个参考阵元）
        candidates = np.arange(1, M)

        # 随机排列
        permutation = rng.permutation(candidates)

        return {"permutation": permutation}

    def apply(
        self,
        data: np.ndarray,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
    ) -> np.ndarray:
        """应用阵元故障。

        Args:
            data: 数据，形状 (M, N)
            draw: 标准化随机量
            params: 参数

        Returns:
            修改后的数据，形状 (M, N)
        """
        params = self.Params.model_validate(params)
        _M, _N = data.shape
        result = data.copy()

        # 确定故障阵元
        if params.indices is not None:
            # 使用指定索引
            failure_indices = np.array(params.indices)
        else:
            # 从排列中取前 count 个
            permutation = draw["permutation"]
            failure_indices = permutation[: params.count]

        # 应用故障
        if params.mode == "zero":
            # 置零模式：输出置零
            result[failure_indices, :] = 0.0
        else:
            # 仅噪声模式：signal 阶段，无噪数据（A·S）置零
            # 后续会加噪声，所以这里只需置零
            result[failure_indices, :] = 0.0

        return result

    def known_mask(
        self,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
        M: int,
    ) -> np.ndarray | None:
        """返回算法已知的故障掩码。

        Args:
            draw: 误差实现
            params: 参数
            M: 阵元数

        Returns:
            (M,) 布尔数组，True 表示正常，False 表示故障；
            None 表示算法不知道
        """
        params = self.Params.model_validate(params)
        if not params.known:
            return None

        # 算法知道故障位置
        mask = np.ones(M, dtype=bool)

        if params.indices is not None:
            failure_indices = np.array(params.indices)
        else:
            permutation = draw["permutation"]
            failure_indices = permutation[: params.count]

        mask[failure_indices] = False

        return mask

    def describe(
        self,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """描述故障阵元。

        Args:
            draw: 误差实现
            params: 参数
            M: 阵元数

        Returns:
            故障阵元索引 "failure_indices" (count,)
        """
        params = self.Params.model_validate(params)
        if params.indices is not None:
            failure_indices = np.array(params.indices)
        else:
            permutation = draw["permutation"]
            failure_indices = permutation[: params.count]

        return {"failure_indices": failure_indices}
