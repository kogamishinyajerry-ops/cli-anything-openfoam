# cli-anything-cfd — Claude Code 项目指南

## 概述

这是一个标准化 CLI 工具集合（CLI Harness），为工业 CFD/CAE/量化/游戏开发工具提供统一的 Click CLI 界面。

## 已安装的工具 (31个)

安装后可通过 `cli-anything-<name>` 命令调用，或直接用 Python 导入 `cli_anything.<name>` 模块。

### CFD/CAE 工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **OpenFOAM** | `cli-anything-openfoam` | CFD 求解器（blockMesh, snappyHexMesh,icoFoam等） |
| **GMSH** | `cli-anything-gmsh` | 网格生成（.geo → .msh） |
| **ParaView** | `cli-anything-paraview` | CFD 可视化后处理 |
| **SU2** | `cli-anything-su2` | CFD 求解器（超声速/跨音速） |
| **STAR-CCM+** | `cli-anything-starccm` | Siemens CFD 工具（多物理场） |
| **ANSYS Fluent** | `cli-anything-fluent` | Fluent CFD 求解器 |
| **XFOIL** | `cli-anything-xfoil` | 翼型分析 |
| **Tecplot** | `cli-anything-tecplot` | 数据可视化 |
| **VisIt** | `cli-anything-visit` | 科学可视化 |
| **Calculix** | `cli-anything-calculix` | FEM 结构分析（Abaqus兼容） |
| **Elmer** | `cli-anything-elmer` | FEM 多物理场求解器 |
| **FreeCAD** | `cli-anything-freecad` | CAD/FEM 建模 |
| **DAKOTA** | `cli-anything-dakota` | 优化与不确定性分析 |

###  HPC/集群工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **Slurm/PBS** | `cli-anything-slurm` | 集群调度器（sbatch/squeue/scancel + PBS equivalent） |

### 量化/金融工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **Backtrader** | `cli-anything-backtrader` | Python 回测引擎 |
| **VectorBT** | `cli-anything-vectorbt` | 向量化回测（布林带/SMA/RSI） |
| **Alpaca+IB** | `cli-anything-broker` | 股票/加密货币交易（Alpaca + Interactive Brokers） |
| **QuantConnect** | `cli-anything-quantconnect` | LEAN 量化平台（回测/实盘/优化） |
| **TimescaleDB** | `cli-anything-timescaledb` | 时序数据库（SQL分析） |

### 3D/资产工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **Blender** | `cli-anything-blender` | 3D 建模/渲染（Python脚本） |
| **Assimp** | `cli-anything-assimp` | 3D模型格式转换（OBJ/FBX/glTF/USD等） |
| **glTF** | `cli-anything-gltf` | glTF 2.0 验证/转换（JSON ↔ GLB二进制） |
| **USD** | `cli-anything-usd` | Pixar USD 场景描述（usdcat/usdchecker） |
| **Godot** | `cli-anything-godot` | 游戏引擎 |

### DevOps/工具链

| 工具 | 命令 | 用途 |
|------|------|------|
| **Fastlane** | `cli-anything-fastlane` | iOS/Android CI/CD（test/build/beta/release） |
| **Perforce** | `cli-anything-perforce` | Helix Core p4 版本控制 |

### LLM/AI 工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **RAGAs** | `cli-anything-ragas` | RAG 评估指标 |
| **LM-Eval** | `cli-anything-lm-eval` | LLM 基准测试 |
| **Promptfoo** | `cli-anything-promptfoo` | Prompt 测试/对比 |
| **Composio** | `cli-anything-composio` | AI Agent 工具集成 |

### 其他工具

| 工具 | 命令 | 用途 |
|------|------|------|
| **Ink** | `cli-anything-ink` | Ink 脚本语言（交互式叙事） |

## 调用原则

**当你需要使用这些工具时，应该主动调用它们**，而不是每次让用户提醒。

例如：
- 用户提到"用OpenFOAM做CFD仿真" → 调用 `cli-anything-openfoam` 相关命令
- 用户提到"回测一个双均线策略" → 调用 `cli-anything-vectorbt` 或 `cli-anything-backtrader`
- 用户提到"blender渲染" → 调用 `cli-anything-blender`
- 用户提到"提交到perforce" → 调用 `cli-anything-perforce`

## 技术栈

- **CLI框架**: Click 8.0+
- **Python**: >=3.9
- **测试**: pytest（mock模式通过 `{TOOL}_MOCK=1` 环境变量）
- **模式**: `utils/{tool}_backend.py` (核心逻辑) + `{tool}_cli.py` (Click接口)

## 安装

```bash
pip install -e .
```

## 测试

```bash
python3 -m pytest cli_anything/ -q
```
