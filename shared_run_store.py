"""Share the most recently published simulation on one Streamlit server.

The complete four-CSV ZIP is replaced atomically so readers never combine
different runs. For multiple server instances, point all instances at a
shared mounted path or replace this backend with a database/object store.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

from admin_auth import assert_admin
from core.exporter import zip_content
from user_data_adapter import RunData, load_run_zip


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "shared" / "current_run.zip"
ENV_PATH = "JINGXING_SHARED_RUN_PATH"


def shared_run_path() -> Path:
    configured = os.environ.get(ENV_PATH)
    return Path(configured).expanduser() if configured else DEFAULT_PATH


def publish_result(result: dict, path: str | Path | None = None) -> Path:
    """Atomically publish one complete Admin result and return its path."""
    assert_admin()
    target = Path(path) if path is not None else shared_run_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = zip_content(result)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".current_run_", suffix=".zip.tmp",
            dir=target.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_shared_run(stations: pd.DataFrame, path: str | Path | None = None) -> RunData | None:
    """Return the latest complete result, or None before the first publish."""
    target = Path(path) if path is not None else shared_run_path()
    if not target.is_file():
        return None
    run = load_run_zip(target.read_bytes(), stations)
    run.source_label = "同一站点共享的Admin最新仿真"
    return run
