> **历史版集成说明**：此文件是原有团队记录，其中可能含旧结构和开发状态。
> **请以 `README_修复版使用说明.md` 与本次修复报告为准**；本修复版 `app.py` 已采用单网站Admin/User双菜单。

> ⚠️ 该文件来自同学原始代码包，部分“已集成”描述与原始代码不一致。**2026-10-17修复后请优先看 `README_修复版使用说明.md`，以及实际运行的回归测试。**

# 景行智调｜可调车队+滚动优化：开发对接说明

**建议：先在本地备份安同学的源项目，再以本ZIP里的 `jingxing/` 为测试副本。不要直接覆盖线上仓库。**

## 最简运行

打开终端，进入解压后的 `jingxing` 目录：

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

无 Streamlit 时仍可测试算法：

```bash
python scripts/compare_strategies.py --a 10 --b 6 --rate 200 --minutes 240 --seed 42 --out comparison_demo.csv
```

**推荐Python 3.11或其他经项目组实际测试的版本**；最终应按队友部署环境填写准确版本。`requirements.txt` 仍沿用现有依赖，没有引入大型优化框架。

## 文件该放哪里、为什么？

| 文件 | 修改类型 | 原因 |
|---|---|---|
| `core/optimizer.py` | **新增** | 数学决策层：预测未来期望客流、用束搜索比较可行发车组合、输出当前车辆ID。与页面解耦，后期可以单独迭代算法。 |
| `core/simulation.py` | **修改** | 事实运行层：在仿真时钟触发 `optimized_check`，把当前队列、车队状态及已知的车辆事件交给优化器；然后用原来的 `dispatch()` 真正发车。保留 `fixed/dynamic` 对照。 |
| `pages/4_Admin_Smart_Dispatch.py` | **修改** | 用户交互层：A/B车辆数不再写死，三种策略选择、可选优化参数、同客流公平对比都从这里传进引擎。 |
| `pages/1_Admin_Dashboard.py` | **修改** | 展示层：读当前车队配置，不再常年显示固定的5+3。 |
| `pages/6_Admin_Experiment_Analysis.py` | **修改** | 记录层：记录A/B车数、车型容量、速度与优化参数，方便复现实验，避免拿不同车队做错误对比。 |
| `tests/test_optimizer.py` | **新增** | 自动验证车队可变、零车、零客流、守恒、相同随机客流、优化器不偷看未来游客到达事件等。 |
| `scripts/compare_strategies.py` | **新增** | 无需打开网站就可以生成三策略同场景CSV，便于调试、PPT实验图和答辩复现。 |
| `05_数学模型_动态调度方案.md` | **新增** | 变量、目标函数、约束、算法逻辑及实验边界；供数学建模和竞赛作品说明使用。 |

**未修改** `data/stations.py`、`data/routes.py`、`data/segments.py`、`data/vehicles.py` 和User端。因为车辆数量是模型参数，不应该由修改线路来实现；原线路和距离数据已经具备可读性。默认5+3仍是演示**起始值**，进入页面后可立即更改。若后续Admin/User共用后端，请让User端使用同一次仿真结果的实际数据，避免两端各自编造状态。

## 新的调用关系

`页面设置车队 fleet + 客流 scenario + 优化参数` → `core.simulation.run_simulation(params, strategy, seed)` → `core.optimizer.propose_departures(...)`（仅optimized策略）→ `simulation.dispatch()` → 返回监测指标 → `pages/5`监测、`pages/6`保存实验。

具体需要在 `core/simulation.py` 新增的连接点是：

```python
from core.optimizer import propose_departures

# 已有主循环中，每隔 decision_interval_min 生成 optimized_check 事件
# 事件触发时只把“已观察到”的站点和车辆状态传给优化器
selected = propose_departures(
    now=t, stations=stations, vehicles=vehicles, events=events,
    last_departure=last_departure, params=params, route_weights=route_weights
)
# 让原仿真引擎执行真正合法的dispatch，而不是优化器直接篡改乘客数据
```

注意：这段是接口示意，完整代码在 `core/simulation.py`，不用重复粘贴。

## 车队数量改动对原代码的实际影响

1. **有影响的部分**：车辆对象创建、端点初始分布、调度候选数、容量、排队与实验结果；Admin需动态读取车队。已在此测试版修改。
2. **不需要修改的部分**：景区线路拓扑与路段长度、乘客OD基本模型、网页主程序app.py、User端的页面结构。
3. **对比要求**：要比较算法效果，三种策略必须使用**同一车队**；要研究多少辆车更合适，应在另一个“车队规模敏感性”实验中逐组改变车队数量。
4. **不能宣称的内容**：8/16/24辆均为假设车队；没有证据证明景区真实使用这些车数。增加车数可能降低等待但增加成本，不能把它当成算法的免费收益。
5. **性能**：算法束搜索的候选以线路方向而不是车辆ID排列，避免车辆数增大时平方级增长；若使用几十辆以上、600分钟以上的模拟，建议先降低束宽或缩短预测期，云端耗时依环境而异。

## 已做的验证 / 需要队友验证

- 通过Python离散事件核心测试与新增优化测试；不同规模车队跑通；固定/阈值/优化三策略使用相同客流签名；车队守恒与零车、零客流测试通过。
- **未完成** Streamlit网页全流程及Streamlit Community Cloud在线部署测试（当前执行环境没有Streamlit），必须由安同学在其开发环境测试并核对结果。
- 束搜索产生的是近似较优方案，当前可以跑实验，但不能声称已经证明全局最优或达到景区真实改善率。
- 如果后续加上分线路首末班、跨线应急、真实返程路径、时段限制，需在 `core/simulation.py` 的发车合法性检查和 `core/optimizer.py` 的候选合法性中**同时修改**。
