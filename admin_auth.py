"""Authentication boundary for the Streamlit Admin pages and shared publishing."""

from __future__ import annotations

import hmac
import os
import secrets
from collections.abc import Mapping

import streamlit as st


_SESSION_KEY = "_jingxing_admin_auth_tag"
_SERVER_KEY = secrets.token_bytes(32)


def _credentials() -> tuple[str, str] | None:
    """Use one complete secrets section, or fall back to environment variables."""
    try:
        section = st.secrets.get("admin")
    except FileNotFoundError:
        section = None

    if section is not None:
        if not isinstance(section, Mapping):
            return None
        username = section.get("username")
        password = section.get("password")
    else:
        username = os.environ.get("JINGXING_ADMIN_USERNAME")
        password = os.environ.get("JINGXING_ADMIN_PASSWORD")

    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password.strip():
        return None
    return username, password


def admin_configured() -> bool:
    return _credentials() is not None


def _auth_tag(username: str, password: str) -> bytes:
    data = f"{len(username)}:{username}{password}".encode("utf-8")
    return hmac.digest(_SERVER_KEY, data, "sha256")


def is_admin() -> bool:
    credentials = _credentials()
    saved = st.session_state.get(_SESSION_KEY)
    return (
        credentials is not None
        and isinstance(saved, bytes)
        and hmac.compare_digest(saved, _auth_tag(*credentials))
    )


def login_admin(username: str, password: str) -> bool:
    credentials = _credentials()
    if credentials is None:
        st.session_state.pop(_SESSION_KEY, None)
        return False
    expected_username, expected_password = credentials
    valid_username = hmac.compare_digest(username, expected_username)
    valid_password = hmac.compare_digest(password, expected_password)
    if valid_username and valid_password:
        st.session_state[_SESSION_KEY] = _auth_tag(*credentials)
        return True
    st.session_state.pop(_SESSION_KEY, None)
    return False


def logout_admin() -> None:
    st.session_state.pop(_SESSION_KEY, None)
    for key in ("last_result", "result", "comparison", "experiments", "shared_publish_error"):
        st.session_state.pop(key, None)


def assert_admin() -> None:
    """Guard server-side operations that change the shared public result."""
    if not is_admin():
        raise PermissionError("Admin authentication is required")


def require_admin_page() -> None:
    """Deny a separately opened Admin view before it renders or runs actions."""
    if not is_admin():
        st.error("此页面仅管理员可访问。请先在网站入口登录。")
        st.stop()
