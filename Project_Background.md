# DOA算法竞技场 项目背景与决策记录

> 本文档记录项目关键决策、经验总结和注意事项，供后续参考。不包含详细设计，详细设计见 `D:\DOA_Estimation_Research\Arena\docs\`。

## 一、项目定位

**核心价值**：一个让各种DOA估计算法（传统+学习型）在同一套仿真条件下公平比较的工具。

- 算法作者只写 `estimate()` 函数（输入接收数据，输出角度），其余全自动。
- 保证训练数据和测试数据用同一套信号模型（学习型算法评测可信的前提）。
- 每次实验自动记录：配置、种子、代码commit、未提交改动、模型哈希。

**不是什么**：不是算法开发平台。竞技场是工具，算法代码在课题仓库里独立演进，互不干扰。

## 二、关键设计决策与理由

| 决策 | 理由 | 后果 |
|---|---|---|
| 工具和研究代码分离（`Arena\` vs `Projects\fewshot-doa\`） | 版本独立演进；算法改了不影响工具，工具升级不影响算法 | 算法接入必须通过标准接口，不能直接改竞技场代码 |
| 参数表单自动生成（Pydantic → JSON Schema → 前端表单） | 加算法参数时前端零改动 | 参数类型受限于能转成Schema的类型 |
| Web和脚本共用计算核心；Web服务不做任何计算 | 两种用法结果逐位相同；只需验证一套代码 | Web服务不能为了UI便利自己算指标 |
| 实验结果全部存本地文件（JSON/npz），不用数据库 | 便于备份、放进Git、不依赖竞技场也能读 | 搜索慢（实验数量不多时可接受） |
| 图表用Plotly（后端生成） | Web和脚本的图一模一样；导出PDF不需要前端参与 | 前端不能自己改图表样式 |
| 随机数完全由种子派生，禁止全局随机数API | 实验可复现；并行/串行结果相同；同一次试验所有算法用同一份数据 | 代码中不能用 `np.random.seed()` / `random` 模块 |
| 内置算法实现方式写死在文档里（接口规范第13章） | 防止随意改动，让基线变强或变弱 | 改基线需要修改文档并说明原因 |

## 三、目录结构（已建立）

```
D:\DOA_Estimation_Research\
├── Arena\              竞技场工具（git仓库，main分支，首次提交 d725b5e）
│   ├── AGENTS.md       开发约定（AI自动读取）
│   ├── CLAUDE.md       一行：@AGENTS.md
│   ├── pyproject.toml  工具配置
│   └── docs\           6份设计文档 + 可点击原型
├── Notes\              Obsidian笔记
├── Projects\           课题仓库（一课题一仓库）
│   └── fewshot-doa\    （尚未建立）
└── Papers\             论文（每篇一目录）
```

**规矩**：
- 路径全英文，不放进OneDrive（避免同步冲突锁文件）。
- Zotero保持原位 `D:\01_工作\01_课题\00_Zotero`。
- 旧的会话目录 `D:\01_工作\01_课题\...\Claude\docs\` 是设计阶段临时目录，**以Arena\docs\为准**，会话目录文件已过时。

## 四、课题仓库结构建议

```
fewshot-doa\
├── algorithms\                一个算法一个子目录
│   ├── cnn_grid\
│   │   ├── arena_plugin.py    竞技场入口
│   │   ├── net.py             网络结构
│   │   ├── train.py           训练脚本（调用arena.datasets生成数据）
│   │   └── README.md          思路、论文、当前最优模型
│   ├── common\                共用代码（无arena_plugin.py）
│   └── _draft\                试验中的想法（以_开头会被跳过）
├── configs\
│   ├── datasets\              训练数据配置
│   └── experiments\           实验配置（按论文图表命名，如fig3_snr_sweep.yaml）
├── scripts\                   一张图或一组实验一个脚本（run_fig3.py）
├── notebooks\                 临时探索
├── tests\                     关键算法的测试
├── runs\                      训练日志和检查点（不进Git）
├── arena_ws\                  工作目录（实验结果、数据集、模型包）
├── requirements.txt
└── README.md
```

**使用规则**：
- `algorithms\` 第一层不要放 `.py` 文件（会被当成算法导入）。
- 改进算法不要复制目录（`cnn_grid_v2`这样会乱）；小改用Git + 更新version，只有算法本质变了才新建目录。
- 网络结构只写一份，train.py和arena_plugin.py都从net.py导入。
- 训练产物留在 `runs\`，只把选定的模型导出到 `arena_ws\models\`。
- 配置和脚本按论文图表命名，便于复现。

## 五、开发约定（2026-10-30确认）

| 方面 | 约定 |
|---|---|
| 分支模型 | 每个里程碑一个分支 `milestone/m1-core`，完成后写报告，**由用户验收后合并**，AI不得自行合并 |
| 提交信息 | `feat(algorithms): 新增TLS-ESPRIT`（英文类型前缀 + 中文描述） |
| 注释 | 中文；变量名、文件名英文 |
| 工具 | ruff（格式化+检查）、mypy（类型）、pytest（测试）、pre-commit（提交前检查） |
| 硬性规则 | 13条（计算只在核心库、前端不写死算法名、禁止全局随机数、torch.load必须weights_only=True等），部分由工具直接拦截 |

详见 `Arena\AGENTS.md`。

## 六、新电脑使用方法

```bash
# 1. 克隆竞技场
git clone https://github.com/saymynameww/doa-arena.git
cd doa-arena
pip install -e packages/arena_api -e "packages/arena[server]"

# 2. 克隆课题仓库
cd D:\Research\Projects
git clone <your-project-repo>
cd fewshot-doa

# 3. 启动（在课题仓库根目录）
# 方式待定：可能是 python -m arena.server，或另外的命令
```

**跨平台注意**：
- 核心库和数据生成已按跨平台设计（Python 3.10+，Windows/Linux/macOS）。
- 训练在Linux（AutoDL），评测在Windows（本机RTX 4060 Laptop 8GB）。
- 模型包（state_dict）和数据（npz）跨平台兼容。

## 七、会话工作方式

**设计阶段（本会话）**：在 `D:\01_工作\...\Claude` 讨论需求、写设计文档、建仓库。已完成。

**开发阶段（新会话）**：
- 工作目录：`D:\DOA_Estimation_Research\Arena\`
- 启动时自动读取 `CLAUDE.md` → `AGENTS.md`
- 按里程碑开发，每个里程碑写报告交用户验收
- 不要读本会话记录（设计文档更准确）

**研究阶段（第三个会话）**：
- 工作目录：`D:\DOA_Estimation_Research\Projects\fewshot-doa\`
- 写算法、训练、跑实验
- 把 `Arena\` 加为可访问目录

**原则**：一个仓库一个会话；交接靠文档和代码，不靠对话记录。

## 八、已知风险与应对

| 风险 | 应对 |
|---|---|
| 内置基线算法实现有误 | 接口规范13.4节的验收测试；Root-MUSIC/ESPRIT符号已实测 |
| 训练和测试信号模型不一致 | 训练脚本也用arena.datasets；模型包记录GENERATOR_VERSION；超出训练范围时警告 |
| 外部算法依赖冲突 | V1要求同一conda环境；接口预留了独立进程方式（V2） |
| Windows导出PDF工具兼容性 | M3第一件事就验证 |
| 硬盘故障丢数据 | 代码在GitHub；Notes\和arena_ws\大文件需另外备份 |

完整风险列表：架构第14章。

## 九、未来扩展预留

V1不做但设计上预留的功能（加这些功能时，已写好的算法插件不需要修改）：
- 二维DOA、宽带、近场
- 面阵、圆阵、稀疏阵
- 少样本适配/元学习的测试前微调
- 两变量同时扫描（热力图）
- MATLAB算法、独立环境中的算法

## 十、里程碑（M1-M7）

| 里程碑 | 能做什么 | 验收重点 |
|---|---|---|
| M1 计算核心 | 命令行跑算法，输出指标和图（无可用入口，只有测试） | MUSIC/ESPRIT贴近CRB；相干信源测试；1000次×5算法<1分钟 |
| M2 实验执行与脚本 | Python脚本跑完整实验 | 自己写算法接入；同种子结果相同 |
| M3 图表与导出 | 导出PDF/.mat/LaTeX | PDF能否直接放进论文；.mat在MATLAB中能否打开（含中文名） |
| M4 Web服务 | 后台就绪 | 网页和脚本同一配置结果一致 |
| M5 前端 | 网页完成全部操作 | 对照原型；不看文档能否配出实验 |
| M6 学习型算法 | AutoDL训练、本机评测 | 实际走一遍；训练范围提示是否出现 |
| M7 场景集与排行榜 | 一键跑标准场景 | P1功能，可推迟 |

详见：架构第12章。

---

**最后更新**：2026-11-07  
**仓库首次提交**：2026-10-30（d725b5e）  
**GitHub地址**：https://github.com/saymynameww/doa-arena（待推送）
