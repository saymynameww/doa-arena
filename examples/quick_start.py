"""快速开始示例。

演示如何使用脚本模式运行实验并生成报告。
"""

from pathlib import Path

from arena import AlgorithmConfig, ExperimentConfig, ExperimentType, run_experiment
from arena.core.config import SweepConfig
from arena.core.export import export_to_csv, export_to_latex
from arena.core.figures import ChartGenerator
from arena.core.reports import generate_html_report

# 1. 配置实验
config = ExperimentConfig(
    name="快速开始示例",
    type=ExperimentType.SWEEP,
    trials=20,  # 每个扫描点 20 次试验
    algorithms=[
        AlgorithmConfig(id="music", label="MUSIC"),
        AlgorithmConfig(id="esprit", label="ESPRIT"),
    ],
    sweep=SweepConfig(
        path="scenario.sources.snr_db",
        values=[0, 5, 10, 15, 20],
        label="SNR",
        unit="dB",
    ),
)

print("配置：")
print(f"  实验名称: {config.name}")
print(f"  实验类型: {config.type}")
print(f"  试验次数: {config.trials}")
print(f"  算法数量: {len(config.algorithms)}")
print(f"  扫描点数: {len(config.sweep.values)}")
print()

# 2. 运行实验
print("开始运行实验...")
result = run_experiment(config)
print(f"实验完成！总耗时: {result.metadata['elapsed_seconds']:.2f} 秒")
print()

# 3. 生成图表
print("生成图表...")
gen = ChartGenerator(result)
charts = gen.create_all_charts()
print(f"生成了 {len(charts)} 个图表:")
for name in charts.keys():
    print(f"  - {name}")
print()

# 4. 导出数据
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

print("导出数据...")
export_to_csv(result, output_dir / "results.csv")
print(f"CSV: {output_dir / 'results.csv'}")

export_to_latex(result, output_dir / "results.tex", caption="实验结果")
print(f"LaTeX: {output_dir / 'results.tex'}")
print()

# 5. 生成 HTML 报告
print("生成 HTML 报告...")
generate_html_report(result, output_dir / "report.html", title="快速开始示例")
print(f"报告: {output_dir / 'report.html'}")
print()

print("=" * 60)
print("全部完成！")
print(f"输出目录: {output_dir.absolute()}")
print()
print("下一步:")
print("  1. 在浏览器中打开 output/report.html 查看完整报告")
print("  2. 查看 output/results.csv 获取数据")
print("  3. 使用 output/results.tex 插入 LaTeX 论文")
print("=" * 60)
