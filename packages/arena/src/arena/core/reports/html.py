"""HTML 报告生成。

生成自包含的 HTML 报告，包含图表和数据表格。
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from ..runner.results import ExperimentResult


def generate_html_report(
    result: ExperimentResult,
    output_path: Path | str,
    title: str | None = None,
) -> None:
    """生成 HTML 报告。

    Args:
        result: 实验结果
        output_path: 输出路径
        title: 报告标题，None 则使用实验名称
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 标题
    if title is None:
        title = result.config.get("name", "实验报告")

    # 生成图表
    from ..figures.presentation import build_figures
    from ..figures.render import render_image

    charts = build_figures(result)

    # 内嵌 SVG 可离线查看和打印，不依赖外部脚本。
    charts_html = {name: render_image(fig, "svg").decode("utf-8") for name, fig in charts.items()}

    # 生成 HTML
    html = _build_html(result, title, charts_html)

    # 写入
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_html(
    result: ExperimentResult,
    title: str,
    charts_html: dict[str, str],
) -> str:
    """构建 HTML 内容。"""
    from arena import __version__

    title = escape(title)
    config = {
        key: escape(value) if isinstance(value, str) else value
        for key, value in result.config.items()
    }
    metadata = result.metadata

    from ..figures.details import result_details

    details = result_details(result)
    columns = details["columns"]
    headings = "".join(f"<th>{escape(c['label'])} {escape(c['unit'])}</th>" for c in columns)
    metric_rows = []
    for row in details["rows"]:
        cells = "".join(f"<td>{_format_metric(row['metrics'].get(c['key']))}</td>" for c in columns)
        metric_rows.append(
            f"<tr><td>{row['point'] + 1}</td><td>{escape(str(row['x']))}</td>"
            f"<td>{escape(str(row['algorithm']))}</td>{cells}"
            f"<td>{row['n_used']}/{row['n_total']}</td><td>{len(row['errors'])}</td></tr>"
        )

    # 代码差异留在原始存档中；报告显示实验参数，避免补丁占据数十页。
    def without_patch(value: object) -> object:
        if isinstance(value, dict):
            return {k: without_patch(v) for k, v in value.items() if k != "patch"}
        if isinstance(value, list):
            return [without_patch(v) for v in value]
        return value

    configuration = escape(json.dumps(without_patch(result.config), ensure_ascii=False, indent=2))

    # 算法列表
    from ..metrics.summary import algorithm_labels

    algo_labels = algorithm_labels(result)

    # 实验信息表格
    info_rows = []
    info_rows.append(f"<tr><td>实验名称</td><td>{config.get('name', 'N/A')}</td></tr>")
    info_rows.append(f"<tr><td>实验类型</td><td>{config.get('type', 'N/A')}</td></tr>")
    info_rows.append(f"<tr><td>试验次数</td><td>{config.get('trials', 'N/A')}</td></tr>")
    info_rows.append(f"<tr><td>算法数量</td><td>{len(config.get('algorithms', []))}</td></tr>")
    info_rows.append(f"<tr><td>扫描点数</td><td>{metadata.get('num_points', 'N/A')}</td></tr>")

    elapsed = metadata.get("elapsed_seconds", 0)
    info_rows.append(f"<tr><td>总耗时</td><td>{elapsed:.2f} 秒</td></tr>")

    info_table = "\n".join(info_rows)

    # 生成时间
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # HTML 模板
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>

    <style>
        @page {{ size: A4 landscape; margin: 12mm; }}
        @media print {{
            body {{ background: white !important; margin: 0 !important; }}
            .container {{ max-width: none !important; padding: 0 !important;
                          box-shadow: none !important; }}
            .print-button {{ display: none; }}
            .chart {{ break-inside: avoid; }}
            thead {{ display: table-header-group; }}
            th {{ color: black !important; background: white !important; }}
            h2, h3 {{ break-after: avoid; }}
            tr {{ break-inside: avoid; }}
        }}
        pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
        svg {{ max-width: 100%; height: auto; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                "Helvetica Neue", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart {{
            margin: 30px 0;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #888;
            font-size: 0.9em;
        }}
        .algorithms {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 10px 0;
        }}
        .algorithm-tag {{
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {title}</h1>
        <button class="print-button" onclick="window.print()">打印 / 保存为 PDF</button>

        <h2>实验信息</h2>
        <table>
            {info_table}
        </table>

        <h2>算法列表</h2>
        <div class="algorithms">
            {
        "".join(f'<span class="algorithm-tag">{escape(label)}</span>' for label in algo_labels)
    }
        </div>

        <h2>图表</h2>

        {
        "".join(
            f'<div class="chart"><h3>{_chart_title(name)}</h3>{html}</div>'
            for name, html in charts_html.items()
        )
    }

        <h2>指标汇总</h2>
        <p>— 表示无可用值；纳入统计次数按所选指标口径解释。</p>
        <table><thead><tr><th>扫描点</th><th>扫描值</th><th>算法</th>{headings}
        <th>RMSE 纳入/总次数</th><th>错误次数</th></tr></thead>
        <tbody>{"".join(metric_rows)}</tbody></table>
        <h2>配置摘要与完整参数</h2>
        <p>未提交的代码补丁保留在原始实验存档中，此处省略补丁正文。</p>
        <pre>{configuration}</pre>

        <div class="footer">
            <p>生成时间：{gen_time}</p>
            <p>DOA 估计算法竞技场 Arena v{__version__}</p>
        </div>
    </div>
</body>
</html>"""

    return html


def _format_metric(value: object) -> str:
    """保持可读精度，原始精度仍保存在结果文件中。"""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return escape(str(value))


def _chart_title(name: str) -> str:
    """图表标题映射。"""
    titles = {
        "rmse_curve": "RMSE 曲线",
        "success_rate_curve": "成功率曲线",
        "time_curve": "计算时间曲线",
        "estimates_scatter": "估计角度散点图",
    }
    return titles.get(name, name)
