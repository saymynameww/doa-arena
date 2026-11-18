"""静态导出的浏览器就绪竞态回归。"""

import asyncio
import struct
import xml.etree.ElementTree as ET

import plotly.graph_objects as go
import pytest

from arena.core.figures.export import export_figure
from arena.core.figures.render import _wait_for_renderer


@pytest.mark.slow
@pytest.mark.parametrize("format", ["png", "svg", "pdf"])
def test_export_waits_for_delayed_renderer(format, tmp_path, monkeypatch):
    """模拟过早的 load 通知：浏览器已返回，但导出函数尚未就绪。"""
    from kaleido._kaleido_tab._tab import _KaleidoTab

    original = _KaleidoTab.navigate

    async def delayed(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        # 先等待真实脚本，随后人为延迟其可用性，稳定重现原故障窗口。
        await _wait_for_renderer(self.tab)
        await self.tab.send_command(
            "Runtime.evaluate",
            params={
                "expression": """(() => {
                    const saved = window.kaleido_scopes;
                    window.kaleido_scopes = undefined;
                    setTimeout(() => { window.kaleido_scopes = saved; }, 750);
                })()"""
            },
        )

    monkeypatch.setattr(_KaleidoTab, "navigate", delayed)
    fig = go.Figure(go.Scatter(x=[0, 1, 2], y=[0, 1, 4], name="测试曲线"))
    fig.update_layout(title="导出验收", showlegend=True)
    output = tmp_path / "中文路径" / f"curve.{format}"
    export_figure(fig, output, format=format, width=640, height=480)
    data = output.read_bytes()
    if format == "png":
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (2000, 1500)
    elif format == "svg":
        root = ET.fromstring(data)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert "测试曲线" in "".join(root.itertext())
        assert root.findall(".//{http://www.w3.org/2000/svg}path")
    else:
        from pypdf import PdfReader

        reader = PdfReader(output)
        assert len(reader.pages) == 1
        assert float(reader.pages[0].mediabox.width) == pytest.approx(480, abs=1)
        assert len(reader.pages[0].get_contents().get_data()) > 100


def test_renderer_timeout_is_actionable():
    class UnreadyTab:
        async def send_command(self, *args, **kwargs):
            return {"result": {"result": {"value": {"ready": False}}}}

    with pytest.raises(RuntimeError, match=r"加载超时.*MathJax"):
        asyncio.run(_wait_for_renderer(UnreadyTab(), timeout=0.01))


def test_renderer_protocol_error_is_not_swallowed():
    class BrokenTab:
        async def send_command(self, *args, **kwargs):
            return {"error": {"message": "Session closed"}}

    with pytest.raises(RuntimeError, match="状态检查失败"):
        asyncio.run(_wait_for_renderer(BrokenTab()))
