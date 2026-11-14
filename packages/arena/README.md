# doa-arena

DOA估计算法竞技场 - 核心库

## 安装

完整安装（包含所有可选依赖）：
```bash
pip install -e "packages/arena[all]"
```

最小安装（仅核心功能）：
```bash
pip install -e packages/arena
```

分组安装：
```bash
pip install -e "packages/arena[torch]"     # 学习型算法支持
pip install -e "packages/arena[server]"    # Web服务
pip install -e "packages/arena[plot]"      # 图表导出
```

## 使用

### 脚本模式

```python
import arena

# 运行实验
result = arena.run(config)

# 生成数据
data = arena.generate(scenario_config)

# 加载历史结果
result = arena.load_result(experiment_id)
```

### 命令行

```bash
# 运行实验
arena run config.json

# 启动Web服务
arena serve

# 重建索引
arena index rebuild
```

## 文档

- 系统架构：`docs/02_系统架构设计.md`
- 算法接口：`docs/03_算法接口规范.md`
- 数据格式：`docs/04_数据格式规范.md`
