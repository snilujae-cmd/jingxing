"""Access-control checks for the public User page and privileged Admin actions."""

import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import admin_auth
from shared_run_store import publish_result


ROOT = Path(__file__).resolve().parents[1]
ADMIN_VIEWS = sorted((ROOT / "views").glob("*_Admin_*.py"))


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.secrets = {}
        self.addCleanup(patch.stopall)
        patch.object(admin_auth.st, "session_state", self.state).start()
        patch.object(admin_auth.st, "secrets", self.secrets).start()
        patch.dict(os.environ, {
            "JINGXING_ADMIN_USERNAME": "",
            "JINGXING_ADMIN_PASSWORD": "",
        }).start()

    def test_missing_credentials_fail_closed(self):
        self.assertFalse(admin_auth.admin_configured())
        self.assertFalse(admin_auth.login_admin("operator", "correct-password"))
        self.assertFalse(admin_auth.is_admin())
        with self.assertRaises(PermissionError):
            admin_auth.assert_admin()

    def test_partial_or_blank_secrets_do_not_fall_back_to_environment(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "env-password"
        for section in ({"username": "operator"},
                        {"username": "operator", "password": "   "},
                        "invalid section"):
            with self.subTest(section=section):
                self.secrets["admin"] = section
                self.assertFalse(admin_auth.admin_configured())
                self.assertFalse(admin_auth.login_admin("operator", "env-password"))
                self.assertFalse(admin_auth.is_admin())

    def test_environment_credentials_and_wrong_login(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "correct-password"
        self.assertTrue(admin_auth.admin_configured())
        self.assertFalse(admin_auth.login_admin("other", "correct-password"))
        self.assertFalse(admin_auth.login_admin("operator", "wrong-password"))
        self.assertFalse(admin_auth.is_admin())
        self.assertTrue(admin_auth.login_admin("operator", "correct-password"))
        self.assertTrue(admin_auth.is_admin())
        admin_auth.assert_admin()
        self.assertFalse(admin_auth.login_admin("operator", "wrong-password"))
        self.assertFalse(admin_auth.is_admin())

    def test_complete_secrets_take_precedence_over_environment(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "env-user"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "env-password"
        self.secrets["admin"] = {
            "username": "secret-user", "password": "secret-password",
        }
        self.assertFalse(admin_auth.login_admin("env-user", "env-password"))
        self.assertTrue(admin_auth.login_admin("secret-user", "secret-password"))
        self.assertTrue(admin_auth.is_admin())

    def test_password_rotation_and_logout_revoke_access(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "original-password"
        self.assertTrue(admin_auth.login_admin("operator", "original-password"))
        self.assertTrue(admin_auth.is_admin())
        os.environ["JINGXING_ADMIN_PASSWORD"] = "rotated-password"
        self.assertFalse(admin_auth.is_admin())
        with self.assertRaises(PermissionError):
            admin_auth.assert_admin()
        self.assertTrue(admin_auth.login_admin("operator", "rotated-password"))
        for key in ("last_result", "result", "comparison", "experiments",
                    "shared_publish_error"):
            self.state[key] = "private result"
        admin_auth.logout_admin()
        self.assertFalse(admin_auth.is_admin())
        for key in ("last_result", "result", "comparison", "experiments",
                    "shared_publish_error"):
            self.assertNotIn(key, self.state)

    def test_other_session_does_not_inherit_login(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "correct-password"
        self.assertTrue(admin_auth.login_admin("operator", "correct-password"))
        with patch.object(admin_auth.st, "session_state", {}):
            self.assertFalse(admin_auth.is_admin())
        self.assertTrue(admin_auth.is_admin())

    def test_unauthorized_publish_fails_before_creating_parent_or_exporting(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            parent = Path(temp) / "must-not-be-created"
            target = parent / "current_run.zip"
            with patch("shared_run_store.zip_content") as export:
                with self.assertRaises(PermissionError):
                    publish_result({}, target)
            export.assert_not_called()
            self.assertFalse(parent.exists())
            self.assertFalse(target.exists())

    def test_authenticated_publish_writes_shared_result(self):
        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "correct-password"
        self.assertTrue(admin_auth.login_admin("operator", "correct-password"))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            target = Path(temp) / "shared" / "current_run.zip"
            with patch("shared_run_store.zip_content", return_value=b"test ZIP contents") as export:
                self.assertEqual(publish_result({"run_id": "example"}, target), target)
            export.assert_called_once()
            self.assertEqual(target.read_bytes(), b"test ZIP contents")

    def test_admin_page_guard_stops_guest(self):
        class PageStopped(Exception):
            pass

        with patch.object(admin_auth.st, "error") as error, \
                patch.object(admin_auth.st, "stop", side_effect=PageStopped):
            with self.assertRaises(PageStopped):
                admin_auth.require_admin_page()
        error.assert_called_once()

    def test_direct_admin_page_prompts_for_login_and_stops_before_content(self):
        class PageStopped(Exception):
            pass

        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "test-password"
        with patch.object(admin_auth.st, "title"), \
                patch.object(admin_auth.st, "info") as info, \
                patch.object(admin_auth.st, "form") as form, \
                patch.object(admin_auth.st, "text_input", return_value=""), \
                patch.object(admin_auth.st, "form_submit_button", return_value=False), \
                patch.object(admin_auth.st, "stop", side_effect=PageStopped):
            with self.assertRaises(PageStopped):
                admin_auth.require_admin_page()
        form.assert_called_once_with("admin_page_login", clear_on_submit=True)
        info.assert_called_once()
        self.assertFalse(admin_auth.is_admin())

    def test_direct_admin_page_login_continues_on_same_page(self):
        class PageRerun(Exception):
            pass

        os.environ["JINGXING_ADMIN_USERNAME"] = "operator"
        os.environ["JINGXING_ADMIN_PASSWORD"] = "test-password"
        with patch.object(admin_auth.st, "title"), \
                patch.object(admin_auth.st, "info"), \
                patch.object(admin_auth.st, "form"), \
                patch.object(admin_auth.st, "text_input", side_effect=["operator", "test-password"]), \
                patch.object(admin_auth.st, "form_submit_button", return_value=True), \
                patch.object(admin_auth.st, "rerun", side_effect=PageRerun), \
                patch.object(admin_auth.st, "stop") as stop:
            with self.assertRaises(PageRerun):
                admin_auth.require_admin_page()
        stop.assert_not_called()
        self.assertTrue(admin_auth.is_admin())
        admin_auth.require_admin_page()


class PageBoundaryTests(unittest.TestCase):
    def _navigation_for(self, authorized):
        current_page = Mock()
        with patch("admin_auth.is_admin", return_value=authorized), \
                patch("streamlit.set_page_config"), \
                patch("utils.style.load_css"), \
                patch("streamlit.Page", side_effect=lambda target, **kw: (target, kw)), \
                patch("streamlit.navigation", return_value=current_page) as navigation:
            runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
        current_page.run.assert_called_once()
        return navigation.call_args.args[0]

    def test_guest_navigation_registers_hidden_admin_views(self):
        pages = self._navigation_for(False)
        self.assertEqual([page[0] for page in pages["User 游客端"]], ["views/user.py"])
        self.assertTrue(pages["User 游客端"][0][1]["default"])
        self.assertEqual(len(pages["Admin 管理端"]), 7)
        self.assertTrue(all(page[1]["visibility"] == "hidden" for page in pages["Admin 管理端"]))
        self.assertIn("管理员账号", pages)

    def test_authenticated_navigation_registers_all_admin_views(self):
        pages = self._navigation_for(True)
        self.assertEqual(len(pages["Admin 管理端"]), 7)
        self.assertEqual(
            {page[0] for page in pages["Admin 管理端"]},
            {f"views/{path.name}" for path in ADMIN_VIEWS},
        )
        self.assertTrue(all(page[1]["visibility"] == "visible" for page in pages["Admin 管理端"]))
        self.assertTrue(pages["User 游客端"][0][1]["default"])

    def test_every_admin_view_calls_guard_before_rendering_or_running(self):
        class PageDenied(Exception):
            pass

        self.assertEqual(len(ADMIN_VIEWS), 7)
        with patch("core.simulation.run_simulation") as simulation, \
                patch("shared_run_store.publish_result") as publish, \
                patch("admin_auth.require_admin_page", side_effect=PageDenied) as guard:
            for view in ADMIN_VIEWS:
                with self.subTest(view=view.name):
                    with self.assertRaises(PageDenied):
                        runpy.run_path(str(view), run_name="__main__")
        self.assertEqual(guard.call_count, len(ADMIN_VIEWS))
        simulation.assert_not_called()
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
