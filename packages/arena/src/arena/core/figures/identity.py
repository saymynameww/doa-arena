"""配置卡、结果与导出共享的算法视觉身份。"""

from typing import Any


def style_catalog() -> dict[str, Any]:
    """返回可用的视觉样式及其中文标签。"""
    return {
        "colors": ["#1677ff", "#fa8c16", "#13a86b", "#8b5cf6", "#e34b72", "#0891b2"],
        "dashes": ["solid", "dash", "dot", "dashdot"],
        "symbols": ["circle", "square", "diamond", "triangle-up", "cross", "x"],
    }


def algorithm_style(index: int) -> dict[str, str]:
    """按实例顺序分配三重视觉编码。"""
    catalog = style_catalog()
    return {
        key: catalog[plural][index % len(catalog[plural])]
        for key, plural in (("color", "colors"), ("dash", "dashes"), ("symbol", "symbols"))
    }


def apply_styles(figure: Any, labels: list[str], overrides: dict[str, Any] | None = None) -> None:
    """为图表应用与页面一致的样式，保留不足样本的空心标记。"""
    settings = overrides or {}
    if not isinstance(settings, dict) or not isinstance(settings.get("algorithms", {}), dict):
        raise ValueError("图表样式及算法样式必须为 JSON 对象")
    font = settings.get("font_size")
    if font is not None:
        if not isinstance(font, int | float) or not 8 <= font <= 32:
            raise ValueError("字号必须在 8–32 之间")
        figure.update_layout(font_size=font)
    for trace in figure.data:
        label = trace.legendgroup or trace.name
        if label not in labels:
            continue
        custom = settings.get("algorithms", {}).get(label, {})
        if not isinstance(custom, dict):
            raise ValueError("单个算法样式必须为 JSON 对象")
        visual = {
            **algorithm_style(labels.index(label)),
            **custom,
        }
        trace.update(line={"color": visual["color"], "dash": visual["dash"]})
        previous = trace.marker.symbol
        symbol = visual["symbol"]
        markers = (
            [symbol + "-open" if str(s).endswith("-open") else symbol for s in previous]
            if isinstance(previous, list | tuple)
            else symbol
        )
        trace.update(marker={"color": visual["color"], "symbol": markers})
