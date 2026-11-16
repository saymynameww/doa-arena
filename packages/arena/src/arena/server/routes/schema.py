"""配置与插件参数 Schema 路由。"""

from typing import Any

from fastapi import APIRouter

from ...core.config import ExperimentConfig
from .algorithms import list_algorithms

router = APIRouter()


@router.get("/schema/experiment")
async def experiment_schema() -> dict[str, Any]:
    """发布真实模型、插件参数及显示元数据，前端不维护参数清单。"""
    schema = ExperimentConfig.model_json_schema()
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
    schema["x-default"] = ExperimentConfig.model_validate({}).model_dump(mode="json")
    plugins = await list_algorithms()
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
        for key, value in parameters.pop("$defs", {}).items():
            schema["$defs"][prefix + key] = value
        if parameters.get("properties"):
            schema["$defs"]["MetricParameters"]["properties"][plugin["id"]] = {
                **parameters,
                "x-label": plugin["name"],
            }
    schema["$defs"]["ArrayConfig"]["properties"]["carrier_hz"]["x-label"] = "载频（Hz）"
    return schema
