"""静态图渲染：确认浏览器中的导出脚本就绪后再提交图表。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

import plotly.graph_objects as go
import plotly.io as pio


async def _wait_for_renderer(tab: Any, timeout: float = 90) -> None:
    # Kaleido 1.5.1 的 load 事件可能早于目标页脚本完成；检查实际状态，不能固定 sleep。
    expression = """({
        ready: document.readyState === 'complete' &&
            typeof kaleido_scopes !== 'undefined' &&
            typeof kaleido_scopes.plotly === 'function' && typeof Plotly !== 'undefined',
        state: document.readyState,
        url: location.href
    })"""

    async def wait() -> None:
        while True:
            response = await tab.send_command(
                "Runtime.evaluate", params={"expression": expression, "returnByValue": True}
            )
            if "error" in response or "exceptionDetails" in response.get("result", {}):
                raise RuntimeError("图表渲染页状态检查失败，请检查 Chrome 和 Kaleido 安装。")
            value = response.get("result", {}).get("result", {}).get("value", {})
            if value.get("ready"):
                return
            await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(wait(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            "图表渲染脚本加载超时，请检查 Chrome、Kaleido 及配置的 MathJax 资源是否可用。"
        ) from exc


def render_image(
    fig: go.Figure,
    format: Literal["png", "svg", "pdf"],
    width: int | None = None,
    height: int | None = None,
    scale: float = 1,
) -> bytes:
    """等待脚本就绪并生成静态图，兼容已有异步事件循环的调用方。

    Args:
        fig: 待渲染的 Plotly 图表。
        format: PNG、SVG 或 PDF。
        width: 逻辑宽度，缺省使用图表或 Plotly 默认值。
        height: 逻辑高度，缺省使用图表或 Plotly 默认值。
        scale: 输出缩放倍数。

    Returns:
        完整的图片文件字节。
    """
    try:
        import kaleido
    except ImportError as exc:
        raise ImportError("静态图表导出需要 kaleido，请安装 doa-arena[plot]。") from exc

    async def render() -> bytes:
        # 每次调用独立管理浏览器生命周期，不修改 Kaleido 私有类或全局 Plotly 配置。
        async with kaleido.Kaleido(
            n=1, timeout=90, plotlyjs=pio.defaults.plotlyjs, mathjax=pio.defaults.mathjax
        ) as renderer:
            for tab in renderer.tabs.values():
                await _wait_for_renderer(tab)
            return await renderer.calc_fig(
                fig,
                opts={
                    "format": format,
                    "width": width
                    or fig.layout.width
                    or fig.layout.template.layout.width
                    or pio.defaults.default_width,
                    "height": height
                    or fig.layout.height
                    or fig.layout.template.layout.height
                    or pio.defaults.default_height,
                    "scale": scale,
                },
                topojson=pio.defaults.topojson,
            )

    # 与 Kaleido 同步接口一样在线程中运行事件循环；退出时回收线程和浏览器。
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(render())).result()
