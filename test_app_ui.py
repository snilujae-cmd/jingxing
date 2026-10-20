"""Real Streamlit AppTest interactions; these are not browser layout tests.

Credentials and shared storage are isolated per test. The callable account page
is selected by its registered URL hash because AppTest.switch_page only accepts
file-backed pages. No real secrets, deployment, or stable shared data are used.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

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

    def admin_comparison_table(self, app):
        return next(element.value for element in app.dataframe
                    if "全体观测候车均值(min)" in element.value.columns)

    def assert_visitor_trend(self, app, line_call, run):
        """The only visitor plot must show station queues from the selected run."""
        self.assertEqual([tab.label for tab in app.tabs],
                         ["线路查询", "仿真回放与候车", "排队趋势"])
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertEqual(line_call.call_count, 1)
        args, kwargs = line_call.call_args
        self.assertEqual((kwargs["x"], kwargs["y"], kwargs["color"]),
                         ("仿真时刻（分钟）", "排队人数", "线路与站点"))
        shown = args[0]
        self.assertEqual(set(shown.columns), {"仿真时刻（分钟）", "线路与站点", "排队人数"})
        observed = {}
        for row in shown.to_dict("records"):
            key = (float(row["仿真时刻（分钟）"]), str(row["线路与站点"]))
            self.assertNotIn(key, observed)
            observed[key] = float(row["排队人数"])
        expected = run.station_state.groupby(
            ["time_min", "route_id", "station_name"])["waiting_total"].sum()
        expected_points = {(float(t), f"{r}线·{s}") for t, r, s in expected.index}
        expected_labels = {label for _, label in expected_points}
        expected_times = {float(time_min) for time_min in run.station_state["time_min"].dropna()}
        self.assertEqual({label for _, label in observed}, expected_labels)
        self.assertEqual({time_min for time_min, _ in observed}, expected_times)
        for (time_min, route_id, station_name), count in expected.items():
            key = (float(time_min), f"{route_id}线·{station_name}")
            self.assertIn(key, observed)
            self.assertAlmostEqual(observed[key], float(count))
        for key, count in observed.items():
            if key not in expected_points:
                self.assertEqual(count, 0.0)

        visible = self.text(app)
        self.assertIn("本图展示科研仿真场景下的站点排队变化", visible)
        self.assertIn("不代表景区实时排队状态或官方实时运营数据", visible)
        self.assertNotIn(run.run_id, visible)
        for management_term in ("三策略", "策略比较", "比较编号", "随机种子", "P95",
                                "上车服务率", "期末未上车", "发车趟数"):
            self.assertNotIn(management_term, visible)
        management_columns = {"策略", "全体观测候车均值（分钟）", "已上车 P95 候车（分钟）",
                              "上车服务率（%）", "期末未上车（人）", "发车趟数"}
        self.assertFalse(any(management_columns.intersection(frame.value.columns)
                             for frame in app.dataframe))
        self.assertEqual(len(app.json), 0)

    def test_default_visitor_query_and_replay_controls(self):
        app = self.app()
        self.no_exception(app)
        self.assertEqual(app.title[0].value, "景行智调·游客出行助手")
        self.assertEqual([tab.label for tab in app.tabs],
                         ["线路查询", "仿真回放与候车", "排队趋势"])
        self.assertEqual(app.radio(key="user_data_source").value, "内置演示样例")
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.assertEqual(len(app.image), 8)  # hero, map, four route cards, two optional reference photos
        self.assertIn("景区其他游览参考", [item.label for item in app.expander])
        self.assertIn("美龄宫、紫金山天文台不在本系统 A/B 研究站序内", self.text(app))
        self.assertIn("不代表景区真实实时运营数据", self.text(app))
        self.widget(app.selectbox, "起点").select("N03 灵谷景区")
        self.widget(app.selectbox, "终点").select("N03 灵谷景区").run()
        self.assertIn("起点和终点相同", self.text(app))
        self.widget(app.selectbox, "终点").select("N05 孙中山纪念馆").run()
        self.no_exception(app)
        query = next(frame.value for frame in app.dataframe if "记录情况" in frame.value.columns)
        self.assertEqual(set(query["线路"]), {"A", "B"})
        self.widget(app.select_slider, "选择仿真回放时刻").set_value(0.0).run()
        self.widget(app.button, "查询后续上车记录").click().run()
        self.no_exception(app)
        self.assertTrue(any("同OD上车记录间隔(分钟)" in frame.value.columns for frame in app.dataframe))
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertIn("本图展示科研仿真场景下的站点排队变化", self.text(app))
        self.assertNotIn("三策略", self.text(app))

    def test_uploaded_four_csv_zip_remains_single_run(self):
        app = self.app()
        app.radio(key="user_data_source").set_value("上传Admin导出的ZIP").run()
        uploaded_data = zip_content(self.comparison_a[0])
        with patch.object(px, "line", wraps=px.line) as line_call:
            app.file_uploader[0].upload("existing_four_csv.zip", uploaded_data,
                                        "application/zip").run()
        self.no_exception(app)
        self.assertEqual(app.radio(key="user_data_source").value, "上传Admin导出的ZIP")
        self.assert_visitor_trend(app, line_call, load_run_zip(uploaded_data, self.stations))

    def test_independent_visitor_refresh_replaces_selected_run(self):
        first = self.publish(self.comparison_a)
        with patch.object(px, "line", wraps=px.line) as first_line:
            app = self.app()
        self.no_exception(app)
        self.assertNotIn("last_result", app.session_state)
        self.assertEqual(app.radio(key="user_data_source").value, "最新共享仿真")
        self.assert_visitor_trend(app, first_line, first.run)
        self.assertNotIn(first.comparison["comparison_id"], self.text(app))
        second = self.publish(self.comparison_b)
        with patch.object(px, "line", wraps=px.line) as second_line:
            self.widget(app.button, "刷新共享结果").click().run()
        self.no_exception(app)
        self.assertEqual(app.radio(key="user_data_source").value, "最新共享仿真")
        self.assert_visitor_trend(app, second_line, second.run)
        self.assertNotIn(second.comparison["comparison_id"], self.text(app))
        with patch("shared_run_store.assert_admin"):
            publish_result(self.comparison_a[0], self.shared_path)
        single = load_shared_bundle(self.stations, self.shared_path)
        self.assertIsNone(single.comparison)
        with patch.object(px, "line", wraps=px.line) as single_line:
            self.widget(app.button, "刷新共享结果").click().run()
        self.no_exception(app)
        self.assert_visitor_trend(app, single_line, single.run)

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
        # The account page is a callable, registered at /admin-login.
        app._page_hash = calc_hash("admin-login")
        app.run()
        self.widget(app.button, "退出管理员登录").click().run()
        self.no_exception(app)
        self.assertNotIn("_jingxing_admin_auth_tag", app.session_state)
        self.assertEqual(app.title[0].value, "景行智调·游客出行助手")
        app.switch_page("views/4_Admin_Smart_Dispatch.py").run()
        self.assertIn("此页面仅管理员可访问", self.text(app))
        self.assertFalse(any(button.label == "📊 同场景比较三策略" for button in app.button))

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
        self.assertEqual(set(self.admin_comparison_table(admin)["运行编号"]),
                         {item["run_id"] for item in admin.session_state["comparison"]})
        shared = load_shared_bundle(self.stations, self.shared_path)
        self.assertIsNone(shared.comparison_error)
        self.assertIsNotNone(shared.comparison)
        with patch.object(px, "line", wraps=px.line) as visitor_line:
            visitor = self.app()
        self.no_exception(visitor)
        self.assertNotIn("_jingxing_admin_auth_tag", visitor.session_state)
        self.assertNotIn("last_result", visitor.session_state)
        self.assert_visitor_trend(visitor, visitor_line, shared.run)
        self.assertNotIn(shared.comparison["comparison_id"], self.text(visitor))

    def test_bad_comparison_and_missing_images_preserve_single_run_ui(self):
        buffer = BytesIO(zip_content(self.comparison_a[0]))
        with ZipFile(buffer, "a") as archive:
            archive.writestr("comparison.json", b"{invalid")
        self.shared_path.write_bytes(buffer.getvalue())
        shared = load_shared_bundle(self.stations, self.shared_path)
        self.assertIsNotNone(shared.comparison_error)
        with patch("utils.media.asset_download", return_value=None), \
                patch.object(px, "line", wraps=px.line) as visitor_line:
            app = self.app()
            self.no_exception(app)
            self.assertIn("暂不可用，线路查询和仿真功能仍可使用", self.text(app))
            self.assertEqual(len(app.image), 0)
            self.assert_visitor_trend(app, visitor_line, shared.run)
            self.assertNotIn("比较结果校验未通过", self.text(app))
            self.assertTrue(any("记录情况" in frame.value.columns for frame in app.dataframe))


if __name__ == "__main__":
    unittest.main(verbosity=2)
