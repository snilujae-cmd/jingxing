# 景行智调｜Admin + User 本地整合版

本目录以 2026-10-17 收到的 Admin 修复版和 User 联调版为基础。唯一入口是 `app.py`。**游客无需登录即可直接访问 User 端**，可查看演示数据或已发布的最新共享仿真；**Admin 页面及运行仿真、发布或覆盖共享结果等管理操作需要先用账号和密码登录**。`views/` 是整合副本，不会修改原始包。

## 本地启动

建议使用 Python 3.11 或 3.12。在本目录执行：

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Windows 也可在安装依赖后运行 `run_windows.bat`。若 `python` 命令不可用，请用已安装 Python 的完整路径替换。网页默认在 `http://localhost:8501` 打开；首页为 User 游客端。

## 配置 Admin 凭据

部署者必须通过以下任一方式提供**完整的一组**管理员账号和密码，应用代码中没有预设账号或密码：

1. 在 Streamlit secrets 中设置 `admin` 节。例如，本地创建 `.streamlit/secrets.toml`，填写实际凭据：

   ```toml
   [admin]
   username = "<管理员账号>"
   password = "<管理员密码>"
   ```

   托管部署时应在平台的 Streamlit secrets 设置中填写相同内容。不要将实际凭据提交到版本库；本目录的 `.gitignore` 已排除 `.streamlit/secrets.toml`。

2. 或在启动应用的进程环境中同时设置 `JINGXING_ADMIN_USERNAME` 和 `JINGXING_ADMIN_PASSWORD`。本地 PowerShell 示例：

   ```powershell
   $env:JINGXING_ADMIN_USERNAME = Read-Host '管理员账号'
   $securePassword = Read-Host '管理员密码' -AsSecureString
   $env:JINGXING_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
   python -m streamlit run app.py
   ```

若存在 `[admin]` secrets 节，应用优先使用该节，**不会**以环境变量补齐该节中缺失的字段。secrets 节或环境变量中的账号、密码任一缺失或为空时，Admin 登录关闭，管理页面与操作均拒绝访问；User 端仍可使用。更改凭据后，既有管理员会话需重新登录。

游客打开网站即进入 User 页面；管理员从顶部「管理员登录 / 退出」进入登录页，输入配置的账号和密码后可看到 Admin 页面。管理员用同一入口退出，退出后回到 User 页面。请在部署平台将 secrets 和共享结果文件的读取权限限定为需要它们的应用进程。

## 管理端与游客端联动

1. 已登录的管理员在 Admin「客流场景」设定参数，在「智能调度」运行策略。
2. 成功运行后，Admin 保留本会话结果，并将同一次运行的四份 CSV 原子写入 `data/shared/current_run.zip`。再次发布会覆盖该最新共享结果。
3. User 的「最新共享仿真」读取该完整 ZIP；其他浏览器会话在同一服务器上打开页面或点击「刷新共享结果」后也可读取。User 仍可选内置演示样例或上传 Admin 导出的 ZIP。

共享文件路径可通过环境变量 `JINGXING_SHARED_RUN_PATH` 改为**可写的绝对路径**。默认路径适用于单个本地服务器的跨会话访问。多实例部署必须让所有实例共用持久存储，或将共享结果迁移到数据库、对象存储等统一后端；否则不同实例可能读到不同结果。临时云环境重启后，本地文件可能丢失。此文件机制只共享最新一次仿真，不提供历史版本或并发发布协调。

## 游客端数据含义

- 直达线路比较只读取当前选定仿真中**同起点、同终点、同方向且已完成**的乘客记录；没有完整记录时不填时间。页面按下一名符合条件的乘客从回放时刻到下车的间隔排序。
- 候车栏显示后续同 OD 乘客的**上车记录间隔**，不是新游客的候车预测、车辆到站 ETA 或座位保证。
- 暂不支持换乘。返程道路、站序和路段真实时间尚待核验。车辆位置是仿真最近站点快照，不是 GPS。
- 所有车队规模、客流、道路折返和速度均为研究型情景假设，不代表景区实时或实测运营数据。

## 验证与后续工作

本次在 Windows 沙箱中使用 Python 3.12.14 和 Streamlit 1.66.0 运行 `python -B -m unittest discover -s tests -v`，**35 项测试全部通过（0 失败）**。测试覆盖凭据缺失和错误、secrets 优先级、登录退出与凭据轮换、游客默认导航、七个 Admin 页面的入口拦截、未授权发布拒绝，以及原有仿真与共享结果读写测试。

本次尝试了 Streamlit AppTest 页面烟测，但该沙箱在创建本地套接字和事件循环时停滞，尚未执行到应用页面；本地服务启动及浏览器交互因此**未完成验证**。实际部署后应手动检查游客首页、管理员登录与退出、直接输入 Admin 页面地址、运行仿真，以及另一浏览器读取最新共享结果。早期整合版曾记录过 23 项测试和本地双浏览器联动，那是访问控制改造前的历史记录。

本版尚未在不同物理设备或多服务器环境验证。MPC 发车成本权衡、全站点实测校准、真正的未来候车预测和全面视觉改版仍待后续验收与优化。
