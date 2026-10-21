"""Real Streamlit AppTest interactions; these are not browser layout tests.

Credentials and shared storage are isolated per test. Portal and login pages
are file-backed so AppTest can follow the same navigation as users. No real
secrets, deployment, or stable shared data are used.
"""
from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
from streamlit.testing.v1 import AppTest

from core.exporter import zip_content
from core.simulation import run_simulation
from shared_run_store import load_shared_bundle, publish_result
from user_data_adapter import load_run_zip


class AppUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        params = {
            "duration_min": 60, "arrival_rate": 60, "scenario_type": "平峰",
            "fleet": {"A": 1, "B": 1}, "speed_kmh": 15,
            "decision_interval_min": 15, "prediction_horizon_min": 15, "beam_width": 2,
            "snapshot_interval_min": 5,
        }
        cls.comparison_a = [run_simulation(params, strategy, seed=31)
                            for strategy in ("fixed", "dynamic", "optimized")]
        cls.comparison_b = [run_simulation(params, strategy, seed=32)
                            for strategy in ("fixed", "dynamic", "optimized")]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ui_isolated_", dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.shared_path = Path(self.temp.name) / "current_run.zip"
        self.environment = patch.dict(os.environ, {"JINGXING_SHARED_RUN_PATH": str(self.shared_path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
        app.secrets["admin"] = {"username": "isolated-ui-admin", "password": "temporary-test-only"}
        return app.run()

    def no_exception(self, app):
        self.assertEqual(len(app.exception), 0, [item.message for item in app.exception])

    @staticmethod
    def text(app):
        return "\n".join(str(element.value) for kind in
                         ("title", "subheader", "caption", "markdown", "info", "success", "warning", "error")
                         for element in app.get(kind))

    @staticmethod
    def widget(widgets, label):
        return next(widget for widget in widgets if widget.label == label)

    def visitor_app(self):
        app = self.app()
        self.no_exception(app)
        self.assertIn("智慧接驳 · 畅游钟山", self.text(app))
        self.assertEqual({button.label for button in app.button},
                         {"进入游客端 →", "进入管理端 →"})
        self.widget(app.button, "进入游客端 →").click().run()
        self.no_exception(app)
        self.assertEqual(app.title[0].value, "景行智调 · 游客出行助手")
        return app

    def publish(self, results):
        with patch("shared_run_store.assert_admin"):
            publish_result(results[0], self.shared_path, comparison_results=results)
        return load_shared_bundle(self.stations, self.shared_path)

    def login_direct(self, app):
        app.switch_page("views/4_Admin_Smart_Dispatch.py").run()
        self.widget(app.text_input, "账号").set_value("isolated-ui-admin")
        self.widget(app.text_input, "密码").set_value("temporary-test-only")
        self.widget(app.button, "登录").click().run()
        self.no_exception(app)
        self.assertIn("_jingxing_admin_auth_tag", app.session_state)

    def comparison_table(self, app):
        return next(element.value for element in app.dataframe
                    if "全体观测候车均值（分钟）" in element.value.columns)

    def assert_visitor_trend_matches_run(self, line_call, run):
        """Preserve the original queue-series check for an imported Admin ZIP."""
        calls = [call for call in line_call.call_args_list
                 if call.kwargs.get("color") == "线路与站点"]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual((kwargs["x"], kwargs["y"], kwargs["color"]),
                         ("仿真时刻（分钟）", "排队人数", "线路与站点"))
        shown = args[0]
        self.assertEqual(set(shown.columns), {"仿真时刻（分钟）", "线路与站点", "排队人数"})
        observed = {(float(row["仿真时刻（分钟）"]), str(row["线路与站点"])):
                    float(row["排队人数"]) for row in shown.to_dict("records")}
        self.assertEqual(len(observed), len(shown))
        expected = run.station_state.groupby(
            ["time_min", "route_id", "station_name"])["waiting_total"].sum()
        expected_times = {float(time_min) for time_min in run.station_state["time_min"].dropna()}
        expected_labels = {f"{route_id}线·{station_name}" for _, route_id, station_name in expected.index}
        self.assertEqual({time_min for time_min, _ in observed}, expected_times)
        self.assertEqual({label for _, label in observed}, expected_labels)
        for (time_min, route_id, station_name), count in expected.items():
            self.assertAlmostEqual(observed[(float(time_min), f"{route_id}线·{station_name}")],
                                   float(count))
        expected_points = {(float(t), f"{r}线·{s}") for t, r, s in expected.index}
        for key, count in observed.items():
            if key not in expected_points:
                self.assertEqual(count, 0.0)

    def test_portal_visitor_query_and_three_real_modules(self):
        app = self.visitor_app()
        self.assertEqual(len(app.tabs), 0)
        self.assertTrue({"线路查询与推荐", "仿真回放与候车", "候车趋势与研究展示"}
                        <= {button.label for button in app.button})
        self.assertEqual(app.radio(key="user_data_source").value, "内置演示样例")
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.assertEqual(len(app.image), 7)  # map, four route cards, two optional reference photos
        self.assertIn("景区其他游览参考", [item.label for item in app.expander])
        self.assertIn("美龄宫、紫金山天文台不在本系统 A/B 研究站序内", self.text(app))
        self.assertIn("不代表景区真实实时运营数据", self.text(app))
        self.widget(app.selectbox, "出发站点").select("N03 灵谷景区")
        self.widget(app.selectbox, "目的站点").select("N03 灵谷景区").run()
        self.widget(app.button, "查看推荐路线").click().run()
        self.assertIn("出发站点和目的站点相同", self.text(app))
        self.widget(app.selectbox, "出发站点").select("N01 地铁钟灵街站")
        self.widget(app.selectbox, "目的站点").select("N06 紫金·钟爱里").run()
        self.widget(app.button, "查看推荐路线").click().run()
        self.assertIn("当前研究线路中没有支持该起终点的直达方案。", self.text(app))
        self.widget(app.selectbox, "出发站点").select("N03 灵谷景区")
        self.widget(app.selectbox, "目的站点").select("N05 孙中山纪念馆").run()
        self.widget(app.button, "查看推荐路线").click().run()
        self.no_exception(app)
        query = next(frame.value for frame in app.dataframe if "记录情况" in frame.value.columns)
        self.assertEqual(set(query["线路"]), {"A 线", "B 线"})
        self.assertIn("不代表实时到站时间、实际车次或乘车保证", self.text(app))
        self.widget(app.button, "仿真回放与候车").click().run()
        self.assertIn("看看这一刻的接驳情况", self.text(app))
        self.widget(app.select_slider, "选择仿真回放时刻").set_value(0.0).run()
        self.widget(app.button, "查询后续上车记录").click().run()
        self.no_exception(app)
        self.assertTrue(any("同OD上车记录间隔(分钟)" in frame.value.columns for frame in app.dataframe))
        self.widget(app.button, "候车趋势与研究展示").click().run()
        self.assertIn("各站点排队是怎样变化的？", self.text(app))
        self.assertTrue(app.get("plotly_chart"))

    def test_uploaded_four_csv_zip_remains_single_run(self):
        app = self.visitor_app()
        app.radio(key="user_data_source").set_value("上传Admin导出的ZIP").run()
        contents = zip_content(self.comparison_a[0])
        app.file_uploader[0].upload("existing_four_csv.zip", contents,
                                    "application/zip").run()
        self.no_exception(app)
        self.assertIn(self.comparison_a[0]["run_id"], self.text(app))
        self.widget(app.select_slider, "选择仿真回放时刻").set_value(60.0).run()
        self.widget(app.button, "查看推荐路线").click().run()
        self.assertIn("当前仿真没有足够的同起终点完整记录", self.text(app))
        with patch.object(px, "line", wraps=px.line) as line_call:
            self.widget(app.button, "候车趋势与研究展示").click().run()
        self.assert_visitor_trend_matches_run(line_call, load_run_zip(contents, self.stations))
        self.assertIn("演示样例与上传的单次仿真 ZIP 不提供已发布比较", self.text(app))
        self.assertFalse(any("全体观测候车均值（分钟）" in frame.value.columns for frame in app.dataframe))
        self.assertTrue(app.get("plotly_chart"))

    def test_independent_visitor_refresh_replaces_entire_comparison(self):
        first = self.publish(self.comparison_a)
        app = self.visitor_app()
        self.no_exception(app)
        self.assertNotIn("last_result", app.session_state)
        self.assertEqual(app.radio(key="user_data_source").value, "最新共享仿真")
        self.widget(app.button, "候车趋势与研究展示").click().run()
        self.assertIn(first.comparison["comparison_id"], self.text(app))
        self.assertIn("北京时间", self.text(app))
        self.assertIn("A+B 两线基准到达率 60 人/小时", self.text(app))
        self.assertEqual(set(self.comparison_table(app)["运行编号"]),
                         {item["run_id"] for item in self.comparison_a})
        second = self.publish(self.comparison_b)
        self.widget(app.button, "刷新共享结果").click().run()
        self.no_exception(app)
        self.assertIn(second.comparison["comparison_id"], self.text(app))
        self.assertNotIn(first.comparison["comparison_id"], self.text(app))
        self.assertIn(self.comparison_b[0]["run_id"], self.text(app))
        table = self.comparison_table(app)
        self.assertEqual(set(table["运行编号"]), {item["run_id"] for item in self.comparison_b})
        for result in self.comparison_b:
            shown = table.loc[table["运行编号"].eq(result["run_id"])].iloc[0]
            self.assertAlmostEqual(shown["全体观测候车均值（分钟）"], round(result["avg_observed_wait_all"], 2))
            self.assertEqual(shown["期末未上车（人）"], result["unserved"])
        metadata = next(json.loads(item.value) for item in app.json
                        if "comparison_id" in json.loads(item.value))
        self.assertEqual(metadata["seed"], 32)
        self.assertEqual(metadata["params"], second.comparison["params"])
        self.assertEqual(metadata["published_at"], second.comparison["published_at"])
        with patch("shared_run_store.assert_admin"):
            publish_result(self.comparison_a[0], self.shared_path)
        self.widget(app.button, "刷新共享结果").click().run()
        self.no_exception(app)
        self.assertIn("当前共享结果没有已发布的三策略比较", self.text(app))
        self.assertFalse(any("全体观测候车均值（分钟）" in frame.value.columns for frame in app.dataframe))

    def test_admin_wrong_login_correct_login_all_pages_and_logout(self):
        app = self.app()
        app.switch_page("views/4_Admin_Smart_Dispatch.py").run()
        self.no_exception(app)
        self.assertIn("此页面仅管理员可访问", self.text(app))
        self.assertFalse(any(button.label == "📊 同场景比较三策略" for button in app.button))
        self.widget(app.text_input, "账号").set_value("isolated-ui-admin")
        self.widget(app.text_input, "密码").set_value("wrong-test-password")
        self.widget(app.button, "登录").click().run()
        self.assertIn("账号或密码错误", self.text(app))
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.widget(app.text_input, "账号").set_value("isolated-ui-admin")
        self.widget(app.text_input, "密码").set_value("temporary-test-only")
        self.widget(app.button, "登录").click().run()
        self.no_exception(app)
        self.assertIn("_jingxing_admin_auth_tag", app.session_state)
        for page in (
            "0_Admin_Home.py", "1_Admin_Dashboard.py", "2_Admin_Vehicle_Route.py",
            "3_Admin_Demand_Scenario.py", "4_Admin_Smart_Dispatch.py",
            "5_Admin_Simulation_Monitor.py", "6_Admin_Experiment_Analysis.py",
        ):
            with self.subTest(page=page):
                app.switch_page("views/" + page).run()
                self.no_exception(app)
                self.assertNotIn("此页面仅管理员可访问", self.text(app))
        app.switch_page("views/admin_login.py").run()
        self.widget(app.button, "退出管理员登录").click().run()
        self.no_exception(app)
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.assertIn("智慧接驳 · 畅游钟山", self.text(app))
        app.switch_page("views/4_Admin_Smart_Dispatch.py").run()
        self.assertIn("此页面仅管理员可访问", self.text(app))
        self.assertFalse(any(button.label == "📊 同场景比较三策略" for button in app.button))

    def test_portal_manager_login_opens_six_module_workbench(self):
        app = self.app()
        self.widget(app.button, "进入管理端 →").click().run()
        self.no_exception(app)
        self.assertIn("管理员登录", self.text(app))
        self.widget(app.text_input, "管理员账号").set_value("isolated-ui-admin")
        self.widget(app.text_input, "登录密码").set_value("wrong-test-password")
        self.widget(app.button, "登录管理工作台 →").click().run()
        self.assertIn("账号或密码不正确，请重新输入。", self.text(app))
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.widget(app.text_input, "管理员账号").set_value("isolated-ui-admin")
        self.widget(app.text_input, "登录密码").set_value("temporary-test-only")
        self.widget(app.button, "登录管理工作台 →").click().run()
        self.no_exception(app)
        self.assertIn("_jingxing_admin_auth_tag", app.session_state)
        self.assertIn("景行智调 · 智能调度管理中心", self.text(app))
        for module in ("调度控制台", "车辆与线路", "客流场景", "智能调度", "仿真监测", "实验分析"):
            self.assertIn(module, self.text(app))

    def test_scenario_editor_to_admin_comparison_to_independent_visitor(self):
        admin = self.app()
        self.login_direct(admin)
        admin.switch_page("views/3_Admin_Demand_Scenario.py").run()
        self.widget(admin.radio, "客流模式").set_value("上午高峰")
        self.widget(admin.slider, "基准到达率（人/小时）").set_value(60)
        self.widget(admin.number_input, "仿真时长（分钟）").set_value(60)
        self.widget(admin.number_input, "随机种子").set_value(77)
        admin.run()
        self.no_exception(admin)
        self.assertEqual(admin.session_state["scenario"]["type"], "上午高峰")
        self.assertEqual(admin.session_state["scenario"]["arrival_rate"], 60)
        admin.switch_page("views/4_Admin_Smart_Dispatch.py").run()
        self.assertIn("已读取客流场景：上午高峰", self.text(admin))
        self.widget(admin.number_input, "A线车辆数").set_value(1)
        self.widget(admin.number_input, "B线车辆数").set_value(1)
        self.widget(admin.slider, "决策间隔（分钟）").set_value(15)
        self.widget(admin.slider, "预测窗口（分钟）").set_value(15)
        self.widget(admin.slider, "束搜索宽度").set_value(2)
        self.widget(admin.button, "📊 同场景比较三策略").click().run()
        self.no_exception(admin)
        self.assertEqual(len(admin.session_state["comparison"]), 3)
        for result in admin.session_state["comparison"]:
            self.assertEqual(result["params"]["scenario_type"], "上午高峰")
            self.assertEqual(result["params"]["arrival_rate"], 60)
            self.assertEqual(result["params"]["duration_min"], 60)
            self.assertEqual(result["seed"], 77)
        shared = load_shared_bundle(self.stations, self.shared_path)
        self.assertIsNone(shared.comparison_error)
        visitor = self.visitor_app()
        self.no_exception(visitor)
        self.assertNotIn("_jingxing_admin_auth_tag", visitor.session_state)
        self.assertNotIn("last_result", visitor.session_state)
        self.widget(visitor.button, "候车趋势与研究展示").click().run()
        self.assertIn(shared.comparison["comparison_id"], self.text(visitor))
        self.assertEqual(set(self.comparison_table(visitor)["运行编号"]),
                         {item["run_id"] for item in admin.session_state["comparison"]})

    def test_bad_comparison_and_missing_images_preserve_single_run_ui(self):
        buffer = BytesIO(zip_content(self.comparison_a[0]))
        with ZipFile(buffer, "a") as archive:
            archive.writestr("comparison.json", b"{invalid")
        self.shared_path.write_bytes(buffer.getvalue())
        with patch("utils.media.asset_download", return_value=None):
            app = self.visitor_app()
            self.no_exception(app)
            self.assertIn("已发布比较结果校验未通过", self.text(app))
            self.assertIn("暂不可用，线路查询和仿真功能仍可使用", self.text(app))
            self.assertEqual(len(app.image), 0)
            self.assertIn(self.comparison_a[0]["run_id"], self.text(app))
            self.widget(app.button, "查看推荐路线").click().run()
            self.assertTrue(any("记录情况" in frame.value.columns for frame in app.dataframe))
            self.widget(app.button, "候车趋势与研究展示").click().run()
            self.assertTrue(app.get("plotly_chart"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
