"""普通扫描入口的声明；仅发布编辑元数据，不修改实验参数。"""

from typing import Any


def declare_sweeps(schema: dict[str, Any]) -> None:
    """发布扫描分类、建议范围和同级字段生效条件，未声明字段不提供入口。"""

    def mark(
        fields: dict[str, Any],
        key: str,
        default: str,
        category: str = "scenario",
        when: dict[str, Any] | None = None,
    ) -> None:
        fields[key]["x-sweep"] = {
            "category": category,
            "default": default,
            "when": when or {},
        }

    defs = schema["$defs"]
    source = defs["SourcesConfig"]["properties"]
    mark(source, "K", "1:1:4")
    mark(source, "snr_db", "-10:5:20")
    mark(defs["ScenarioConfig"]["properties"], "snapshots", "10,20,50,100,200,500")
    angles = defs["AnglesConfig"]["properties"]
    mark(angles, "delta", "2:2:20", when={"mode": ["separation"]})
    mark(angles, "center", "-30:10:30", "advanced", {"mode": ["separation"]})
    mark(angles, "min_separation", "1:1:5", "advanced", {"mode": ["random"]})
    correlation = defs["CorrelationConfig"]["properties"]
    mark(correlation, "rho_mag", "0:0.1:0.9", when={"mode": ["partial"]})
    mark(correlation, "rho_phase_deg", "0:30:180", "advanced", {"mode": ["partial"]})
    mark(defs["SearchGrid"]["properties"], "grid_step", "0.05,0.1,0.2,0.5,1", "algorithm")
    for plugin in schema["x-arrays"]:
        if plugin["id"] == "ula":
            mark(plugin["schema"]["properties"], "M", "8:4:32")
            mark(plugin["schema"]["properties"], "d", "0.1:0.1:0.5")
    defaults = {
        "gain_phase": {"sigma_g": "0:0.02:0.1", "sigma_phi_deg": "0:2:10"},
        "position": {"sigma": "0:0.01:0.05"},
        "mutual_coupling": {"scale": "0:0.25:1.5"},
        "element_failure": {"count": "0:1:4"},
    }
    for plugin in schema["x-impairments"]:
        for key, default in defaults.get(plugin["id"], {}).items():
            mark(plugin["schema"]["properties"], key, default)
    for plugin in schema["x-algorithms"]:
        if plugin.get("type") == "external":
            continue  # 外部插件自己声明，不猜测其数值参数的实验意义。
        fields = plugin["schema"].get("properties", {})
        if plugin["id"] in {"cbf", "mvdr", "music"}:
            mark(fields, "grid_step", "0.05,0.1,0.2,0.5,1", "algorithm", {"grid_mode": ["custom"]})
            mark(
                fields,
                "local_step",
                "0.0001,0.001,0.01",
                "algorithm",
                {"peak_refinement": ["local_dense"]},
            )
        if plugin["id"] in {"cbf", "mvdr"}:
            mark(
                fields, "peak_threshold_db", "3,6,10,20", "algorithm", {"peak_mode": ["threshold"]}
            )
        if plugin["id"] == "mvdr":
            mark(fields, "loading", "0,0.001,0.01,0.1", "algorithm")
        if plugin["id"] in {"music", "root_music", "esprit"}:
            mark(fields, "subarray", "4:2:12", "algorithm", {"smoothing": ["forward", "fb"]})
    schema["x-sweep-categories"] = {
        "scenario": "场景扫描",
        "advanced": "高级场景研究",
        "algorithm": "算法参数对比",
    }
