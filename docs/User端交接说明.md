# User 端同学交接说明

## 交接物与使用方式

“完整源码 ZIP”和“User 端协作完整源码 ZIP”包含同一套可运行项目文件。后者单独提供给游客端同学，保留入口、Admin、核心模块、数据、图片及测试，使其能独立启动完整应用；目录结构没有拆散，也没有用代码片段替代文件。User 同学以本说明划定的页面范围开展协作，最终由整合负责人统一合入。

不要在原稳定目录直接解压覆盖。新建文件夹解压，确认根目录有 `app.py`、`requirements.txt`、`views/`、`core/`、`data/`、`assets/`、`.streamlit/config.toml`。首次安装和启动按根目录 README 操作。

## 文件范围

| 归属 | 文件或目录 | 交接要求 |
| --- | --- | --- |
| User 专用 | `views/user.py` | 首页、三标签页、图片与只读比较展示的完整页面 |
| User 图片 | `utils/media.py`、`assets/manifest.json`、`assets/README_sources.md`、`assets/user/` 七张图片 | 成组保留；不能仅复制页面而遗漏资源与工具 |
| 全站共用 | `utils/style.py`、`app.py` | 字体/色彩/导航/登录布局由整合负责人统一维护；User 调整不能使 Admin 隐藏或鉴权失效 |
| B 功能共用 | `comparison_data.py`、`shared_run_store.py` | 与 User 页面配套，负责只读快照读取及数据一致性校验；不在 User 页面重新计算三策略 |
| Admin 配套 | `views/4_Admin_Smart_Dispatch.py` | 为 B 方案提供已发布比较；其他 Admin 页面本轮也有视觉调整，见逐文件清单 |
| 测试 | `tests/test_app_ui.py`、`tests/test_media_assets.py`、`tests/test_comparison_publishing.py` 及原全部测试 | 跟随完整包保留，便于复验 |
| 基线运行支持 | `admin_auth.py`、`scenario_state.py`、`route_recommendation.py`、`user_data_adapter.py`、`core/`、`data/`、依赖及主题 | 完整包含，本轮未改动；不要因不属于 User 页面而删除 |

## 照片和线路图

- `liuhuixie.webp`：首页主视觉，同时用于线路景点卡。
- `sports_park.webp`、`linggu.webp`、`sun_yat_sen_memorial.webp`：研究线路景点卡。
- `meiling_palace.webp`、`observatory.webp`：“景区其他游览参考”折叠区域，明确不属于当前 A/B 研究站点序列。
- `sightseeing_routes.jpg`：线路查询主区域，保留 1448 × 1024 原图和原比例，提供原图下载及 Streamlit 图片放大入口。

所有照片位于 `assets/user/`。保留素材水印，来源与再发布授权仍待确认。图片显示不改变线路站点、候车、车辆或推荐逻辑。需要替换照片时更新 `assets/manifest.json` 的路径、来源、尺寸、哈希及许可状态。

## 替换到团队项目的顺序

1. 团队负责人先记录当前远端稳定提交，并保留本地未提交改动。此包的本地基线并未被确认等于当前远端 `main`。
2. 从最新稳定版创建独立整合分支，逐文件比较本包与团队现有文件。同一文件已有其他同学改动时合并保留，禁止整目录覆盖。
3. 先加入 `assets/`、`utils/media.py`、`comparison_data.py`，再合并 `shared_run_store.py` 与 `views/user.py`。
4. 由负责人合并 `app.py`、`utils/style.py` 和 Admin 调度发布调用；未接入 Admin 发布时游客应看到“尚无已发布比较”的提示。
5. 不修改核心算法、CSV 表头、真实 Secrets 或原站点序列。发现需要调整业务逻辑时，先列明原因与影响，再交负责人处理。
6. 本地验收后把差异和报告交还负责人。未经项目负责人确认，不推送 `main`、不更新 Cloud。

## User 同学本地测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

按以下步骤记录“通过 / 失败 / 未验证”和浏览器、时间、截图：

1. 新游客会话默认打开游客端，首页照片不变形，地图可放大/下载；桌面与约 390px 手机宽度分别查看。小屏查看原图时可以放大，不要求把所有线路文字压在小卡片中。
2. 选择不同起终点，确认原 A/B 路线与推荐出现；科研仿真说明可见。
3. 回放时间变化时，站点队列、车辆状态、候车和运行编号同步；趋势图来自所选运行。
4. 管理员在测试环境运行并发布三策略；另开无痕游客会话，选择共享仿真并刷新，逐项核对比较编号、场景、种子、三个运行编号、策略、全部关键指标与队列曲线。游客没有运行或发布按钮。
5. 再发布不同种子的一组比较；游客刷新后整组编号及数据同时切换。随后发布单次运行，旧比较必须清除。
6. 在本地验收副本临时改名一张照片，确认出现缺图提示且查询正常，再还原。不要在稳定目录或公网删图。
7. 旧四 CSV ZIP 上传仍可使用；没有比较元数据时不拼造三策略结果。

完整自动化证据、当前环境限制和公网未验证项见 [测试与验收报告](测试与验收报告.md)。
