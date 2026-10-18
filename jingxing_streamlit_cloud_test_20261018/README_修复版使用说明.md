# 景行智调 Admin 修复版（2026-10-17）

> **只对上传的 `jingxing(2).zip` 做了修复，不是完整Admin+User最终合并版。** 这是研究性仿真原型，不是景区真实调度方案，也不能拿模型数据宣称真实改善幅度。

## 这次已经修复的内容

1. `core/simulation.py`：重建了有明确OD、分路线分方向排队、先下后上、载客容量、终点折返的事件仿真；不再给每个站点重复乘以全景区到达率；不再瞬间瞬移回起点。
2. `core/optimizer.py`：滚动预测优化算法接入实际的发车和车队事件，沿用现有束搜索近似 MPC，不假装已经求得全局最优。
3. `core/demand.py`：同一份可解释客流假设同时用于仿真输入和优化器预测；将Admin客流场景的平峰/上午/下午、潮汐、突发开关接入引擎。
4. `pages/4_Admin_Smart_Dispatch.py`：三策略按钮真实执行，三策略比较统一随机种子与客流；调整A/B车数、容量、速度等参数；消除了“滚动优化自动回退到动态”的假接入；等待P95是实际分位数而非最大值；服务率改为0~100%显示。
5. `pages/5` 和 `pages/6`：统一读取 `last_result`，修复“4号页面跑完、5号/6号页面看不到结果”的问题；保存实验可复现标识。
6. `core/exporter.py`：同一次仿真可导出 `od_flow.csv`、`station_state.csv`、`vehicle_state.csv`、`passenger_results.csv`；都含 `run_id`，三策略对比允许用 `demand_signature` 验证客流一致。
7. `.streamlit/config.toml`：修正之前 `config.tom1` 的文件名笔误。
8. 新增回归测试、离线数据导出命令、示例联调CSV，未删除原有算法。

## 如何在 Windows 上运行

解压项目，进入 `jingxing` 文件夹，在此处打开VS Code终端：

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

打开网站顶部「Admin 管理端」菜单，选择「客流场景」→「智能调度」→选择**滚动预测优化**→「运行所选策略」；之后到「仿真监测」「实验分析」查看结果，也能在调度页面下载联调CSV ZIP。

**在没有安装 Streamlit 的执行环境中，本次仅验证了算法和Python语法，并未完成Streamlit真实浏览器交互或云端部署验收。** 前端同学须在其电脑跑上述命令，再逐页点击、检查异常。

## 无需启动网页也能验证算法

```powershell
python scripts/compare_strategies.py --a 5 --b 3 --rate 120 --minutes 120 --seed 42 --out comparison.csv
python scripts/export_user_data.py --a 5 --b 3 --rate 120 --minutes 120 --seed 42 --strategy optimized --outdir outputs/demo
```

### 结果字段解释

- `avg_wait` / `p95_wait`：仅**已上车游客**完整候车时间的平均值及P95；避免将未上车的游客误当作0分钟。
- `avg_observed_wait_all`：所有已到达者**截至仿真结束**的平均观测候车时间；未上车者的最终等待仍未知。
- `total_arrivals = served + unserved`；`served = completed + onboard_end`；`service_rate` 在Python内是0到1之间的比例，UI显示时乘100。
- `arrival_rate`：A+B两线合计、正在等待接驳车的游客**基础到达率（人/小时）**，不是全景区客流量，更不是每个站点的流量。
- `station_state` 和 `vehicle_state` 默认5分钟快照，时间字段 `time_min`；`od_flow` 按15分钟到达窗口，字段 `window_start_min`。

## CSV字段契约（本次生成版）

| 文件 | 表头 |
|---|---|
| `od_flow.csv` | `run_id,window_start_min,route_id,origin_station_id,origin_route_station_seq,destination_station_id,destination_route_station_seq,passengers` |
| `station_state.csv` | `run_id,time_min,station_id,route_station_seq,route_id,direction,queue_length,oldest_wait_min` |
| `vehicle_state.csv` | `run_id,time_min,vehicle_id,route_id,station_id,route_station_seq,direction,status,load,capacity` |
| `passenger_results.csv` | `run_id,passenger_id,route_id,origin_station_id,origin_route_station_seq,destination_station_id,destination_route_station_seq,direction,arrival_time_min,board_time_min,alight_time_min,wait_min,status` |

`route_station_seq` 当前沿用A0~A4、B0~B3用于代码内部的**线路站序键**。`station_id` 统一为物理站编号：A0=N01，A1=N02，A2/B1=N03，A3/B2=N04，A4/B3=N05，B0=N06。**物理站编号目前是此修复版提出的暂定映射；必须与昨天已有的CSV主数据表逐项核对，不能直接断言N01～N06已经与队友的最终表完全一致。** 两条线路共享物理站但乘车队列仍按线路、方向独立统计。

**注意：之前生成的三个CSV不在这次上传的Admin ZIP内。** 本次只实现了完整的新输出接口，没有比对昨天三个文件的真实列名/取值编码。请不要拿此CSV直接覆盖User队友已有文件；先按照列名及站点映射核对对接，再决定字段适配器。

## 待办与模型边界

- **已搭建一个网站、两个顶层菜单的架构**：`app.py` 使用 `st.navigation(..., position="top")` 提供 Admin / User 两组入口；Admin原页面全部保留；`User` 当前仅为读取本会话仿真结果的占位页，**并非队友实际User端代码已完成整合**。收到User端代码后替换 `pages/User_Placeholder.py`，同时引入数据库/API实现不同浏览器用户共享结果；不能把 `st.session_state` 当跨用户数据库。
- 数据真实性：线路/路段数据沿用原项目，B线部分长度仍是假设或待核实；返程沿原路、各路段双向可通行仅是模型假设；车辆位置采用到站事件近似，非GPS轨迹。
- 调度公平比较：三策略具有相同的客流、参数及初始车队，但实际发车次数与运营成本可能不同。优化器使用束搜索+期望客流预测，不是数学上的全局最优。
- 预测与展示：不提供真实游客实时ETA；导出的`station_state`是观察排队快照，`vehicle_state`是离散站点级车辆状态；User端推荐时需另外完成可验证的预计等待与出行路线估计，不能将快照当实时预测。
- 目前未实现跨线路调拨、站点异质速度、运营首末班约束、真实经营成本/充电等，仅供比赛原型。
