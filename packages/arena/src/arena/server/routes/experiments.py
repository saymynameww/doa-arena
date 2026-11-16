"""实验相关路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ...core.config import ExperimentConfig
from ..tasks import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _task_or_404(task_id: str):
    task = get_task_manager().tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/experiments/run")
async def run_experiment(
    config: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """运行实验。

    Args:
        config: 实验配置（JSON）
        background_tasks: 后台任务

    Returns:
        任务信息
    """
    try:
        # 解析配置
        exp_config = ExperimentConfig(**config)
        exp_config.validate_experiment()

    except Exception as e:
        logger.error(f"配置校验失败: {e}")
        raise HTTPException(status_code=400, detail=f"配置错误: {e}")

    # 创建任务
    task_manager = get_task_manager()
    task_id = task_manager.create_task(exp_config)

    # 后台运行
    background_tasks.add_task(task_manager.run_task, task_id)

    return {
        "task_id": task_id,
        "status": "created",
        "message": "实验已提交",
    }


@router.get("/experiments/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """查询任务状态。

    Args:
        task_id: 任务 ID

    Returns:
        任务状态
    """
    task_manager = get_task_manager()
    status = task_manager.get_task_status(task_id)

    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return status


@router.get("/experiments/tasks/{task_id}/progress")
async def stream_progress(task_id: str):
    """实时进度推送（SSE）。

    Args:
        task_id: 任务 ID

    Returns:
        SSE 流
    """
    task_manager = get_task_manager()

    # 检查任务是否存在
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        """SSE 事件生成器。"""
        queue = await task_manager.subscribe_progress(task_id)

        try:
            while True:
                # 获取进度消息
                message = await queue.get()

                # 格式化为 SSE
                import json

                data = json.dumps(message)
                yield f"data: {data}\n\n"

                # 如果任务完成，结束流
                if message["status"] in ["completed", "failed", "cancelled"]:
                    break

                # 避免过于频繁
                await asyncio.sleep(0.1)

        finally:
            await task_manager.unsubscribe_progress(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/experiments/tasks")
async def list_tasks() -> dict[str, Any]:
    """列出所有任务。

    Returns:
        任务列表
    """
    task_manager = get_task_manager()
    tasks = task_manager.list_tasks()

    return {"tasks": tasks}


@router.delete("/experiments/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict[str, Any]:
    """取消任务。

    Args:
        task_id: 任务 ID

    Returns:
        取消结果
    """
    task_manager = get_task_manager()
    task = task_manager.tasks.get(task_id)
    if task and task.status in {"completed", "failed", "cancelled"} and task.result_path:
        trash_dir = task_manager.output_dir / ".trash"
        trash_dir.mkdir(exist_ok=True)
        if task.result_path.exists():
            task.result_path.replace(trash_dir / task.result_path.name)
        task_manager.tasks.pop(task_id, None)
        task_manager._save_index()
        return {"message": "实验已移入回收站"}

    success = task_manager.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或已完成")

    return {"message": "任务已取消"}


@router.post("/experiments/tasks/{task_id}/copy")
async def copy_task(task_id: str) -> dict[str, Any]:
    """复制任务配置，返回新的待运行任务。"""
    task = _task_or_404(task_id)
    new_id = get_task_manager().create_task(task.config.model_copy(deep=True))
    return {"task_id": new_id, "status": "created"}


@router.post("/experiments/tasks/{task_id}/rerun")
async def rerun_task(task_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """使用原配置创建并启动新任务。"""
    task = _task_or_404(task_id)
    task_manager = get_task_manager()
    new_id = task_manager.create_task(task.config.model_copy(deep=True))
    background_tasks.add_task(task_manager.run_task, new_id)
    return {"task_id": new_id, "status": "created"}


@router.get("/experiments/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> dict[str, Any]:
    """获取任务结果路径。

    Args:
        task_id: 任务 ID

    Returns:
        结果路径
    """
    task = _task_or_404(task_id)

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")

    return {
        "task_id": task_id,
        "result_path": str(task.result_path),
        "files": [
            "config.json",
            "meta.json",
            "results.npz",
            "summary.json",
        ],
    }


@router.get("/experiments/tasks/{task_id}/charts")
async def get_task_charts(task_id: str) -> dict[str, Any]:
    """读取实验汇总并转换为前端图表数据。"""
    task = _task_or_404(task_id)
    if task.status != "completed" or task.result_path is None:
        raise HTTPException(status_code=400, detail="任务未完成")

    summary_path = task.result_path / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="汇总结果不存在")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    points = summary.get("points", [])
    labels = summary.get("algorithms", [])
    if not labels:
        labels = sorted({label for point in points for label in point.get("algorithms", {})})
    x = [
        point.get("sweep_value") if point.get("sweep_value") is not None else point["point_idx"]
        for point in points
    ]
    charts = []
    for metric, title, y_title in (
        ("rmse_mean", "RMSE", "RMSE (°)"),
        ("success_rate", "成功率", "成功率"),
        ("avg_time_ms", "运行时间", "时间 (ms)"),
    ):
        data = []
        for label in labels:
            data.append(
                {
                    "x": x,
                    "y": [
                        point.get("algorithms", {}).get(label, {}).get(metric) for point in points
                    ],
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": label,
                }
            )
        charts.append(
            {
                "title": title,
                "data": data,
                "layout": {
                    "title": {"text": title},
                    "xaxis": {"title": "扫描点"},
                    "yaxis": {"title": y_title},
                },
            }
        )
    return {"charts": charts}


@router.get("/experiments/tasks/{task_id}/export/{fmt}")
async def export_task(task_id: str, fmt: str) -> FileResponse:
    """导出真实实验结果文件。"""
    task = _task_or_404(task_id)
    if task.status != "completed" or task.result_path is None or task.result is None:
        raise HTTPException(status_code=400, detail="任务未完成或结果不可导出")

    exports_dir = task.result_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    output = exports_dir / f"experiment_{task_id}.{fmt}"
    if fmt == "json":
        summary_path = task.result_path / "summary.json"
        summary = (
            json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        )
        output.write_text(
            json.dumps(
                {
                    "config": task.result.config,
                    "metadata": task.result.metadata,
                    "summary": summary,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    elif fmt == "npz":
        source = task.result_path / "results.npz"
        if not source.exists():
            raise HTTPException(status_code=404, detail="原始结果不存在")
        shutil.copyfile(source, output)
    elif fmt in {"csv", "mat", "tex"}:
        from ...core.export import export_to_csv, export_to_latex, export_to_mat

        exporters = {"csv": export_to_csv, "mat": export_to_mat, "tex": export_to_latex}
        try:
            exporters[fmt](task.result, output)
        except ImportError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
    elif fmt == "html":
        from ...core.reports.html import generate_html_report

        generate_html_report(task.result, output)
    elif fmt in {"png", "svg", "pdf"}:
        from ...core.figures import ChartGenerator
        from ...core.figures.export import export_figure

        charts = ChartGenerator(task.result).create_all_charts()
        if not charts:
            raise HTTPException(status_code=400, detail="当前实验没有可导出的图表")
        first_chart = next(iter(charts.values()))
        try:
            export_figure(first_chart, output, format=fmt)
        except ImportError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
    elif fmt == "py":
        output.write_text(
            "import arena\n"
            f"config = {json.dumps(task.result.config, ensure_ascii=False, indent=2)}\n"
            "result = arena.run(config)\n",
            encoding="utf-8",
        )
    else:
        raise HTTPException(status_code=400, detail=f"不支持导出格式：{fmt}")
    return FileResponse(output, filename=output.name)
