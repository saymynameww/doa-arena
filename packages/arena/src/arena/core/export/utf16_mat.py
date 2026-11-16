"""以 MAT v5 miUTF16 保存字符，避免中文的字节数与字符维度不匹配。"""

from pathlib import Path
from typing import Any

import numpy as np
from scipy.io.matlab._mio5 import MatFile5Writer, VarWriter5
from scipy.io.matlab._mio5_params import miUTF16, mxCHAR_CLASS


class UTF16Writer(VarWriter5):
    """仅替换 SciPy 字符数组编码，其余矩阵使用原实现。"""

    def write_char(self, arr: np.ndarray, codec: str = "ascii") -> None:
        """按 UTF-16 代码单元设置维度，兼容中文及补充平面字符。"""
        strings = [
            str(item) if not isinstance(item, bytes) else item.decode(codec)
            for item in arr.reshape(-1)
        ]
        encoded = [np.frombuffer(item.encode("utf-16-le"), dtype="<u2") for item in strings]
        width = max((len(item) for item in encoded), default=0)
        shape = (*arr.shape, width)
        if len(shape) < 2:
            shape = (1, width)
        values = np.zeros((len(encoded), width), dtype="<u2")
        for index, item in enumerate(encoded):
            values[index, : len(item)] = item
        self.write_header(shape, mxCHAR_CLASS)
        self.write_element(values.reshape(shape), mdtype=miUTF16)


def write_mat(path: Path, data: dict[str, Any]) -> None:
    """顶层只保存 arena 结构体，不全局修改 SciPy。"""
    with path.open("wb") as stream:
        writer = MatFile5Writer(
            stream, unicode_strings=True, long_field_names=True, oned_as="column"
        )
        writer.write_file_header()
        UTF16Writer(writer).write_top(data, b"arena", False)
