"""配置与插件参数 Schema 路由。"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ...core.config import ExperimentConfig
from ..contracts import ScenarioPreview
from .algorithms import list_algorithms

router = APIRouter()


@router.post("/schema/normalize", response_model=ExperimentConfig)
async def normalize_configuration(config: dict[str, Any]) -> ExperimentConfig:
    """规范化草稿和旧模板，不执行环境检测、算法计算或创建实验。"""
    try:
        return ExperimentConfig.model_validate(config)
    except ValidationError as exc:
        errors = [
            {"path": ".".join(str(part) for part in item["loc"]) or "配置", "message": item["msg"]}
            for item in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise HTTPException(status_code=400, detail={"errors": errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/schema/experiment")
async def experiment_schema() -> dict[str, Any]:
    """发布真实模型、插件参数及显示元数据，前端不维护参数清单。"""
    schema = ExperimentConfig.model_json_schema()
    from ...core.figures.identity import style_catalog

    schema["x-chart-styles"] = style_catalog()
    for definition, field in (
        ("ArrayConfig", "origin"),
        ("ImpairmentConfig", "origin"),
        ("AlgorithmConfig", "origin"),
        ("MetricsConfig", "origins"),
    ):
        schema["$defs"][definition]["properties"][field]["x-hidden"] = True
    for definition, labels in {
        "SourcesConfig": {
            "K": "信源数 K",
            "signal": "信源波形",
            "angles": "角度",
            "snr_db": "SNR（dB）",
            "correlation": "相关性",
        },
        "AnglesConfig": {
            "mode": "角度模式",
            "values": "角度值（度）",
            "range_deg": "随机角度范围（度）",
            "delta": "角度间隔（度）",
        },
        "CorrelationConfig": {
            "mode": "相关模式",
            "rho_mag": "相关系数幅度",
            "phases_deg": "相干相位（度）",
        },
    }.items():
        for key, label in labels.items():
            schema["$defs"][definition]["properties"][key]["x-label"] = label
    for definition, mapping in {
        "AnglesConfig": {
            "fixed": "固定角度",
            "random": "范围内随机",
            "separation": "中心 ± 间隔/2",
        },
        "CorrelationConfig": {"none": "不相干", "partial": "部分相关", "coherent": "相干"},
    }.items():
        schema["$defs"][definition]["properties"]["mode"]["x-enum-labels"] = mapping
    for key, mode in {
        "values": "fixed",
        "range_deg": "random",
        "min_separation": "random",
        "delta": "separation",
        "center": "separation",
    }.items():
        schema["$defs"]["AnglesConfig"]["properties"][key]["x-visible-when"] = {"mode": mode}
    for key, mode in {
        "rho_mag": "partial",
        "rho_phase_deg": "partial",
        "phases_deg": "coherent",
    }.items():
        schema["$defs"]["CorrelationConfig"]["properties"][key]["x-visible-when"] = {"mode": mode}
    schema["$defs"]["SourcesConfig"]["properties"]["signal"]["x-enum-labels"] = {
        "gaussian": "复高斯信号"
    }
    for key, label in (("angles", "角度"), ("correlation", "相关性")):
        schema["$defs"]["SourcesConfig"]["properties"][key]["x-flatten"] = True
        definition = "AnglesConfig" if key == "angles" else "CorrelationConfig"
        schema["$defs"][definition]["properties"]["mode"]["x-label"] = label
    # 显示元数据与配置值分离，中文化不改变历史实验及脚本语义。
    advanced_fields = {
        "chunk_size": (
            "试验分块大小",
            "每块处理的试验次数；影响进度保存和取消响应粒度，批量推理可能有浮点级差异。",
        ),
        "max_consecutive_errors": (
            "连续错误上限",
            "同一算法在一个扫描点连续失败达到上限后，跳过该点剩余试验。",
        ),
        "source_count": (
            "信源数来源",
            "选择交给算法的信源数；使用真值或从接收数据估计，会改变算法的已知条件。",
        ),
        "save_spectra": ("保存空间谱", "控制空间谱的保存范围；全部保存会增加磁盘占用。"),
        "save_observations": ("保存接收数据", "控制是否保存阵列接收数据矩阵 X，便于后续检查。"),
        "workers": ("并行进程数", "同时执行试验的工作进程数；增加会占用更多 CPU 和内存。"),
        "common_random_numbers": (
            "公共随机数",
            "开启时，各扫描点同一试验编号使用共同的随机数，减少点间比较的随机波动。",
        ),
        "warmup": (
            "算法预热",
            "正式试验前先运行一次估计，丢弃预热结果；预热耗时不计入单次估计耗时。",
        ),
        "save_estimates": (
            "保存估计值",
            "保存逐次试验的估计角度；关闭后仍计算汇总指标，但无法查看完整逐次估计。",
        ),
    }
    for key, (label, help_text) in advanced_fields.items():
        schema["$defs"]["ExperimentOptions"]["properties"][key].update(
            {"x-label": label, "x-help": help_text}
        )
    for key, label, help_text in (
        ("seed", "随机种子", "相同配置、种子和运行环境可复现实验；改变种子会改变随机数据。"),
        (
            "noise_power",
            "噪声功率",
            "设置基准噪声功率，信号功率按 SNR 相应缩放；通常保持默认值 1。",
        ),
    ):
        schema["$defs"]["ScenarioConfig"]["properties"][key].update(
            {"x-label": label, "x-help": help_text}
        )
    for key, choices in {
        "source_count": {
            "true": ("真实信源数", "直接将仿真中的真实信源数交给算法。"),
            "mdl": ("最小描述长度准则", "通过最小描述长度准则（MDL）从接收数据估计信源数。"),
            "aic": ("赤池信息准则", "通过赤池信息准则（AIC）从接收数据估计信源数。"),
        },
        "save_spectra": {
            "auto": ("自动保存", "仅单次实验保存空间谱；蒙特卡罗和参数扫描不保存。"),
            "all": ("全部保存", "保存每次试验可用的空间谱，可能产生较大文件。"),
            "none": ("不保存", "不保存空间谱数组；需要空间谱的指标仍正常计算。"),
        },
        "save_observations": {
            "auto": ("自动保存", "仅单次实验保存接收数据 X，其他实验可按种子重新生成。"),
            "none": ("不保存", "不保存接收数据矩阵 X。"),
        },
    }.items():
        field = schema["$defs"]["ExperimentOptions"]["properties"][key]
        field["x-enum-labels"] = {value: item[0] for value, item in choices.items()}
        field["x-enum-descriptions"] = {value: item[1] for value, item in choices.items()}
    schema["x-default"] = ExperimentConfig.model_validate({}).model_dump(mode="json")
    plugins = await list_algorithms()
    from .settings import SETTINGS_PATH, _read_json

    device = _read_json(SETTINGS_PATH, {}).get("default_device", "auto")
    for plugin in plugins["algorithms"]:
        properties = plugin["schema"].get("properties", {})
        if "device" in properties and device in properties["device"].get("enum", []):
            properties["device"]["default"] = device
            plugin["defaults"]["device"] = device
    schema["x-arrays"] = plugins["arrays"]
    schema["x-impairments"] = plugins["impairments"]
    schema["x-algorithms"] = plugins["algorithms"]
    schema["x-sweep-paths"] = [
        {"path": path, "label": label, "unit": unit}
        for path, label, unit in [
            ("scenario.sources.snr_db", "SNR", "dB"),
            ("scenario.snapshots", "快拍数", ""),
            ("scenario.sources.K", "信源数 K", ""),
        ]
    ]
    schema["x-metrics"] = [
        {"id": key, "name": label}
        for key, label in [
            ("rmse", "RMSE"),
            ("success_rate", "成功率"),
            ("resolution", "分辨概率"),
            ("time", "耗时"),
            ("crb", "CRB 参考线"),
        ]
    ]
    existing_metrics = {item["id"] for item in schema["x-metrics"]}
    for plugin in plugins["metrics"]:
        identifier = "resolution" if plugin["id"] == "resolution_prob" else plugin["id"]
        if identifier not in existing_metrics:
            schema["x-metrics"].append({"id": identifier, "name": plugin["name"]})
        import json

        prefix = "metric_" + plugin["id"].replace("/", "_") + "_"
        parameters = json.loads(
            json.dumps(plugin["schema"]).replace("#/$defs/", "#/$defs/" + prefix)
        )
        enum_labels = {
            "stat": {"median": "中位数", "mean": "均值"},
            "criterion": {"halfgap": "误差小于信源间隔的一半", "spectrum": "空间谱双峰"},
        }
        for key, labels in enum_labels.items():
            if key in parameters.get("properties", {}):
                parameters["properties"][key]["x-enum-labels"] = labels
        for key, value in parameters.pop("$defs", {}).items():
            schema["$defs"][prefix + key] = value
        if parameters.get("properties"):
            schema["$defs"]["MetricParameters"]["properties"][plugin["id"]] = {
                **parameters,
                "x-label": plugin["name"],
            }
    schema["$defs"]["ArrayConfig"]["properties"]["carrier_hz"]["x-label"] = "载频（Hz）"
    from ..sweep_schema import declare_sweeps

    declare_sweeps(schema)
    return schema


@router.post("/schema/preview", response_model=ScenarioPreview)
async def scenario_preview(config: dict[str, Any]) -> dict[str, Any]:
    """参数编辑时的核心预览，不执行算法或创建实验。"""
    from ...core.operations import invoke

    parsed = ExperimentConfig.model_validate(config)
    plugins = await list_algorithms()
    array = next(
        (item for item in plugins["arrays"] if item["id"] == parsed.scenario.array.type), None
    )
    if array is None:
        raise HTTPException(status_code=400, detail="阵列插件未注册，请刷新插件来源")
    parsed.scenario.array.origin = array["origin"]
    for impairment in parsed.scenario.impairments:
        plugin = next((p for p in plugins["impairments"] if p["id"] == impairment.type), None)
        if plugin is not None:
            impairment.origin = plugin["origin"]
    try:
        return await asyncio.to_thread(
            invoke, "preview", {"config": parsed.model_dump(mode="json")}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
