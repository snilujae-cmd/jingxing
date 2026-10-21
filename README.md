# 景行智调 · 方案 B 正式展示版

南京钟山风景区接驳车科研情景仿真。根网址进入独立门户，再选择游客出行服务或智能调度管理。页面展示的是研究模型和已完成仿真结果，不提供景区实时车辆定位、官方班次或实际调度指令。

## 本轮页面

- 平台首页：流徽榭实景背景，游客端和管理端两个入口。
- 游客端：三个直接切换的功能按钮；线路查询与仿真推荐在首位，保留回放、候车、趋势、景点照片、原始地图及已发布的三策略比较。
- 管理端：实景登录页和六模块工作台；每个受保护子页面都有可见的工作台返回与跨页导航。
- 智能调度：仍以原仿真引擎运行单策略或同场景三策略；图表、指标、运行编号与共享状态均由真实结果生成。

本轮保留 `admin_auth.py`、`core/`、四份 CSV 的格式、研究线路站序、`run_id`、自动共享发布及原子读取校验。其他历史说明文件随稳定基线保留；其旧页面描述以本文件和 [方案 B 交接说明](docs/方案B_变更测试与部署交接_20261020.md) 为准。

## 本地运行

需要 Python 3.12 或更新版本。在项目根目录安装固定依赖并启动：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

游客端不需要账号。管理凭据继续由原有 Streamlit Secrets 的 `[admin]` 节或环境变量 `JINGXING_ADMIN_USERNAME`、`JINGXING_ADMIN_PASSWORD` 提供；源码不包含真实凭据。未配置时管理端关闭。运行结果默认写入当前实例的 `data/shared/current_run.zip`；多个实例共享需由部署方配置共同存储。

## 交付与边界

- [逐文件变更、测试与部署/回滚交接](docs/方案B_变更测试与部署交接_20261020.md)
- [新增品牌照片来源](assets/brand/README_sources.md)
- [既有景点与地图素材来源](assets/README_sources.md)

本版在用户上传的 `jingxing-main (1)(6).zip` 独立副本上完成，没有推送 GitHub、覆盖 `main`、修改线上 Secrets 或替换线上共享结果。正式上线前，由部署负责人核对远端代码差异、图片使用范围与运行存储方式。
